"""
LangGraph-based Teaching Agent - Production-Grade Agentic System
Uses LangGraph for state management, Redis checkpointing, and tool-based agents
"""

import json
from typing import Annotated, TypedDict, Literal, Optional
from typing_extensions import TypedDict
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

# LangGraph v1.0+ API: create_agent from langchain.agents
from langchain.agents import create_agent

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


# ============================================================================
# STATE SCHEMA
# ============================================================================

class TeachingState(TypedDict):
    """
    State schema for the teaching agent graph
    
    LangGraph will automatically persist this to Redis via checkpointing
    """
    # Conversation history
    messages: Annotated[list, add_messages]
    
    # Session metadata
    session_id: str
    user_id: str
    course_id: int
    module_index: int
    sub_topic_index: int
    
    # Teaching progress
    current_segment: int
    total_segments: int
    teaching_content: str
    
    # Metrics
    questions_asked: int
    interruptions: int
    
    # Current intent/action
    current_intent: Optional[str]
    last_user_input: Optional[str]
    
    # Flags
    is_teaching: bool
    waiting_for_continue: bool


# ============================================================================
# TOOLS
# ============================================================================

@tool
def retrieve_course_content(course_id: int, module_index: int, sub_topic_index: int) -> str:
    """
    Retrieve course content from the JSON file for a specific module and sub-topic.
    
    Args:
        course_id: Course identifier
        module_index: Module index (0-based)
        sub_topic_index: Sub-topic index (0-based)
    
    Returns:
        Course content as a string
    """
    import os
    import json
    import config
    
    try:
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            return "Error: Course content not found"
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        course_data = None
        if isinstance(data, dict) and 'course_title' in data:
            course_data = data
        elif isinstance(data, list):
            for course in data:
                if str(course.get("course_id", "")) == str(course_id):
                    course_data = course
                    break
        
        if not course_data:
            return "Error: Course not found"
        
        modules = course_data.get("modules", [])
        if module_index >= len(modules):
            return f"Error: Module {module_index} not found"
        
        module = modules[module_index]
        sub_topics = module.get("sub_topics", [])
        
        if sub_topic_index >= len(sub_topics):
            return f"Error: Sub-topic {sub_topic_index} not found"
        
        sub_topic = sub_topics[sub_topic_index]
        content = sub_topic.get('content', '')
        
        if not content:
            content = f"Topic: {sub_topic['title']}, Module: {module['title']}"
        
        return content[:8000]  # Limit content length
        
    except Exception as e:
        return f"Error retrieving content: {str(e)}"


@tool
def query_conversation_history(session_id: str, user_id: str, limit: int = 10) -> str:
    """
    Query conversation history from the database for context.
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        limit: Number of recent messages to retrieve
    
    Returns:
        Conversation history as formatted string
    """
    try:
        from services.session_manager import get_session_manager
        import config
        
        session_manager = get_session_manager(redis_url=config.REDIS_URL)
        history = session_manager.get_conversation_history(
            user_id=user_id,
            session_id=session_id,
            limit=limit
        )
        
        if not history:
            return "No conversation history found"
        
        formatted_history = []
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            formatted_history.append(f"{role}: {content}")
        
        return "\n".join(formatted_history)
        
    except Exception as e:
        return f"Error querying history: {str(e)}"


@tool  
def save_teaching_metrics(
    session_id: str,
    user_id: str,
    questions_asked: int,
    interruptions: int,
    current_segment: int,
    total_segments: int
) -> str:
    """
    Save teaching session metrics to database for analytics.
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        questions_asked: Number of questions asked
        interruptions: Number of interruptions
        current_segment: Current segment number
        total_segments: Total number of segments
    
    Returns:
        Success message
    """
    try:
        from services.session_manager import get_session_manager
        import config
        
        session_manager = get_session_manager(redis_url=config.REDIS_URL)
        
        # Store metrics in session metadata
        metrics = {
            "questions_asked": questions_asked,
            "interruptions": interruptions,
            "current_segment": current_segment,
            "total_segments": total_segments,
            "progress_percent": (current_segment / total_segments * 100) if total_segments > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        # You can extend this to save to PostgreSQL for long-term analytics
        return f"Metrics saved: {json.dumps(metrics)}"
        
    except Exception as e:
        return f"Error saving metrics: {str(e)}"


# ============================================================================
# AGENT NODES
# ============================================================================

def classify_intent(state: TeachingState) -> TeachingState:
    """
    Classify user intent from their last message.
    Uses LLM to determine intent type.
    """
    messages = state["messages"]
    if not messages or not isinstance(messages[-1], HumanMessage):
        return state
    
    user_input = messages[-1].content
    
    # Intent classification prompt
    classification_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an intent classifier for an interactive teaching system.
        
Classify the user's input into ONE of these intents:
- "continue": User wants to resume/continue the lesson (keywords: continue, resume, go on, next, proceed, keep going)
- "pause": User wants to pause (keywords: pause, stop, wait, hold on)
- "question": User is asking a question (keywords: what, why, how, can you, explain, tell me, or ends with ?)
- "clarify": User wants more explanation (keywords: clarify, elaborate, more details, confused)
- "example": User wants an example (keywords: example, show me, demonstrate, instance)
- "repeat": User wants content repeated (keywords: repeat, again, one more time)
- "summary": User wants a summary (keywords: summary, summarize, recap, review)

Respond with ONLY the intent name, nothing else."""),
        ("user", "{input}")
    ])
    
    # Use the LLM to classify
    llm = ChatOpenAI(model="gpt-4", temperature=0)
    chain = classification_prompt | llm
    
    try:
        result = chain.invoke({"input": user_input})
        intent = result.content.strip().lower()
        
        # Validate intent
        valid_intents = ["continue", "pause", "question", "clarify", "example", "repeat", "summary"]
        if intent not in valid_intents:
            intent = "question"  # Default to question
        
        state["current_intent"] = intent
        state["last_user_input"] = user_input
        
    except Exception as e:
        print(f"Intent classification error: {e}")
        state["current_intent"] = "question"
    
    return state


def teach_content(state: TeachingState) -> TeachingState:
    """
    Generate teaching content using pedagogical prompts.
    Streams teaching content chunk by chunk.
    """
    teaching_content = state.get("teaching_content", "")
    current_segment = state.get("current_segment", 0)
    
    if not teaching_content:
        # Retrieve content using tool
        content = retrieve_course_content.invoke({
            "course_id": state["course_id"],
            "module_index": state["module_index"],
            "sub_topic_index": state["sub_topic_index"]
        })
        state["teaching_content"] = content
        teaching_content = content
    
    # Create pedagogical teaching prompt
    teaching_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert professor delivering an interactive lesson.

Your teaching style is:
- **Engaging**: Use storytelling, real-world examples, and relatable analogies
- **Socratic**: Ask thought-provoking questions to engage critical thinking
- **Adaptive**: Adjust explanations based on student understanding
- **Clear**: Break complex concepts into digestible pieces
- **Encouraging**: Provide positive reinforcement and build confidence

Current Progress: Segment {current_segment} of {total_segments}

Deliver this content in a conversational, engaging manner as if you're teaching a student in a classroom.
Keep segments concise (2-3 minutes of speaking).
Use the "explain like I'm learning this for the first time" approach."""),
        ("user", "Please teach me about:\n\n{content}")
    ])
    
    llm = ChatOpenAI(model="gpt-4", temperature=0.7, streaming=True)
    chain = teaching_prompt | llm
    
    try:
        result = chain.invoke({
            "content": teaching_content,
            "current_segment": current_segment,
            "total_segments": state.get("total_segments", 1)
        })
        
        state["messages"].append(AIMessage(content=result.content))
        state["is_teaching"] = True
        state["current_segment"] = current_segment + 1
        
    except Exception as e:
        print(f"Teaching error: {e}")
        state["messages"].append(AIMessage(content="I encountered an error while teaching. Let's continue..."))
    
    return state


def answer_question(state: TeachingState) -> TeachingState:
    """
    Answer student question using RAG + pedagogical approach.
    Uses conversation history and course content as context.
    """
    messages = state["messages"]
    user_question = state.get("last_user_input", "")
    
    if not user_question and messages:
        user_question = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    
    # Get conversation history for context
    history_context = query_conversation_history.invoke({
        "session_id": state["session_id"],
        "user_id": state["user_id"],
        "limit": 5
    })
    
    # Get course content for context
    course_context = state.get("teaching_content", "")
    
    # Pedagogical answer prompt
    answer_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert professor answering a student's question during a lesson.

Your approach:
- **Directly address** the question first
- **Connect** the answer to the broader lesson context
- **Provide examples** to illustrate the concept
- **Check understanding** by relating to what you've already taught
- **Be encouraging** - there are no "dumb questions"
- **Keep it concise** - 1-2 minutes of speaking maximum

Context from lesson:
{course_context}

Recent conversation:
{history_context}

Answer the question naturally and pedagogically."""),
        ("user", "{question}")
    ])
    
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    chain = answer_prompt | llm
    
    try:
        result = chain.invoke({
            "question": user_question,
            "course_context": course_context[:2000],
            "history_context": history_context
        })
        
        state["messages"].append(AIMessage(content=result.content))
        state["questions_asked"] = state.get("questions_asked", 0) + 1
        state["waiting_for_continue"] = True
        
    except Exception as e:
        print(f"Answer error: {e}")
        state["messages"].append(AIMessage(content="Let me try to help with that..."))
    
    return state


def handle_continue(state: TeachingState) -> TeachingState:
    """
    Handle continue intent - resume teaching.
    """
    state["waiting_for_continue"] = False
    state["is_teaching"] = True
    state["messages"].append(AIMessage(content="Let's continue with the lesson..."))
    return state


def handle_pause(state: TeachingState) -> TeachingState:
    """
    Handle pause intent.
    """
    state["is_teaching"] = False
    state["waiting_for_continue"] = True
    state["messages"].append(AIMessage(content="Paused. Say 'continue' when you're ready to resume."))
    return state


# ============================================================================
# ROUTING FUNCTIONS (Conditional Edges)
# ============================================================================

def route_by_intent(state: TeachingState) -> Literal["continue", "pause", "answer", "teach"]:
    """
    Route to appropriate node based on classified intent.
    """
    intent = state.get("current_intent", "question")
    
    if intent == "continue":
        return "continue"
    elif intent == "pause":
        return "pause"
    elif intent in ["question", "clarify", "example", "summary"]:
        return "answer"
    else:
        # Default to teaching for repeat or unknown
        return "teach"


def should_continue_teaching(state: TeachingState) -> Literal["classify_intent", END]:
    """
    Determine if we should continue the teaching loop or end.
    """
    current_segment = state.get("current_segment", 0)
    total_segments = state.get("total_segments", 1)
    waiting_for_continue = state.get("waiting_for_continue", False)
    
    # If we've completed all segments and user said continue, end
    if current_segment >= total_segments and not waiting_for_continue:
        return END
    
    # Otherwise, wait for next user input
    return "classify_intent"


# ============================================================================
# BUILD THE GRAPH
# ============================================================================

async def create_teaching_agent(redis_url: str) -> StateGraph:
    """
    Create the LangGraph teaching agent with async Redis checkpointing.
    Compatible with LangGraph v1.0.5 and LangChain v1.2.
    
    Args:
        redis_url: Redis connection string (e.g., 'redis://localhost:6379')
    
    Returns:
        Compiled StateGraph
    """
    # Initialize async Redis checkpointer - proper async context manager pattern
    checkpointer = await AsyncRedisSaver.from_conn_string(redis_url).__aenter__()
    try:
        await checkpointer.asetup()  # Required in v1.0+ to create Redis indices
        print("✅ Async Redis checkpointer initialized (indices created)")
    except Exception as e:
        print(f"⚠️ Redis checkpointer setup warning: {e}")
        # Continue anyway - may already be set up
    
    # Initialize workflow with state schema
    workflow = StateGraph(TeachingState)
    
    # Add nodes
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("teach", teach_content)
    workflow.add_node("answer", answer_question)
    workflow.add_node("handle_continue", handle_continue)
    workflow.add_node("handle_pause", handle_pause)
    
    # Define edges
    workflow.add_edge(START, "teach")  # Start with teaching
    
    # After teaching, wait for user input
    workflow.add_conditional_edges(
        "teach",
        should_continue_teaching,
        {
            "classify_intent": "classify_intent",
            END: END
        }
    )
    
    # Route based on intent
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "continue": "handle_continue",
            "pause": "handle_pause",
            "answer": "answer",
            "teach": "teach"
        }
    )
    
    # After handling continue, go back to teaching
    workflow.add_edge("handle_continue", "teach")
    
    # After pause, wait for next input
    workflow.add_edge("handle_pause", "classify_intent")
    
    # After answering, wait for next input
    workflow.add_edge("answer", "classify_intent")
    
    # Compile with Redis checkpointer for persistence
    graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=[],  # No human-in-the-loop interrupts for now
        interrupt_after=[]
    )
    
    return graph


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def initialize_teaching_session(
    graph,
    session_id: str,
    user_id: str,
    course_id: int,
    module_index: int,
    sub_topic_index: int,
    total_segments: int = 10
) -> dict:
    """
    Initialize a new teaching session with LangGraph.
    
    Returns:
        Initial state dict
    """
    initial_state = {
        "messages": [
            SystemMessage(content="Interactive teaching session started.")
        ],
        "session_id": session_id,
        "user_id": user_id,
        "course_id": course_id,
        "module_index": module_index,
        "sub_topic_index": sub_topic_index,
        "current_segment": 0,
        "total_segments": total_segments,
        "teaching_content": "",
        "questions_asked": 0,
        "interruptions": 0,
        "current_intent": None,
        "last_user_input": None,
        "is_teaching": False,
        "waiting_for_continue": False
    }
    
    return initial_state


async def process_user_input_async(
    graph,
    user_input: str,
    thread_id: str
) -> dict:
    """
    Process user input through the LangGraph agent.
    
    Args:
        graph: Compiled LangGraph
        user_input: User's text input
        thread_id: Thread ID for checkpointing (usually session_id)
    
    Returns:
        Updated state
    """
    # Create config with thread_id for checkpointing
    config = {"configurable": {"thread_id": thread_id}}
    
    # Add user message to state
    input_state = {
        "messages": [HumanMessage(content=user_input)]
    }
    
    # Invoke graph (async)
    result = await graph.ainvoke(input_state, config=config)
    
    return result
