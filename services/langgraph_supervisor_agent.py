"""
LangGraph Supervisor Multi-Agent System for Teaching
Uses supervisor pattern for intelligent routing between specialized agents
"""

import json
from typing import Annotated, TypedDict, Literal, Optional, Sequence
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

# LangGraph v1.0+ API: create_react_agent moved to langchain.agents
from langchain.agents import create_agent

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


# ============================================================================
# SHARED STATE SCHEMA
# ============================================================================

class SupervisorState(TypedDict):
    """
    Shared state across all agents in the supervisor system
    """
    # Conversation history
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
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
    assessments_completed: int
    
    # Routing
    next_agent: Optional[str]  # Which agent to route to next
    last_agent: Optional[str]  # Which agent was last active
    
    # Flags
    is_teaching: bool
    waiting_for_continue: bool
    assessment_mode: bool


# ============================================================================
# TOOLS FOR SUB-AGENTS
# ============================================================================

@tool
def retrieve_course_content(course_id: int, module_index: int, sub_topic_index: int) -> str:
    """
    Retrieve course content from JSON file.
    """
    import os
    import config
    
    try:
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            return "Error: Course content not found"
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
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
        
        return content[:8000]
        
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def query_conversation_history(session_id: str, user_id: str, limit: int = 10) -> str:
    """
    Query recent conversation history for context.
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
            return "No history found"
        
        formatted = []
        for msg in history:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)
        
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def save_assessment_result(
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    is_correct: bool,
    score: float
) -> str:
    """
    Save assessment/quiz results to database.
    """
    try:
        result = {
            "session_id": session_id,
            "user_id": user_id,
            "question": question,
            "answer": answer,
            "is_correct": is_correct,
            "score": score,
            "timestamp": datetime.now().isoformat()
        }
        # In production, save to PostgreSQL
        return f"Assessment saved: {score}% correct"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def generate_quiz_question(topic: str, difficulty: str = "medium") -> str:
    """
    Generate a quiz question based on topic and difficulty.
    """
    # In production, use LLM or question bank
    return f"Quiz question for {topic} (difficulty: {difficulty})"


# ============================================================================
# SPECIALIZED SUB-AGENTS
# ============================================================================

def create_teaching_agent(llm: ChatOpenAI) -> StateGraph:
    """
    Specialized agent for delivering teaching content.
    Focused on pedagogical delivery, pacing, and engagement.
    """
    teaching_prompt = """You are an expert teaching agent.

Your role:
- Deliver course content in an engaging, pedagogical manner
- Use storytelling, examples, and analogies
- Break complex concepts into digestible pieces
- Maintain appropriate pacing (2-3 minute segments)
- Ask thought-provoking questions to engage students
- Adapt explanations based on student understanding

Keep responses conversational and encouraging."""

    teaching_tools = [retrieve_course_content, query_conversation_history]
    
    # LangGraph v1.0+ API
    agent = create_agent(
        llm,
        tools=teaching_tools,
        system_prompt=teaching_prompt
    )
    
    return agent


def create_qa_agent(llm: ChatOpenAI) -> StateGraph:
    """
    Specialized agent for answering student questions.
    Expert at explanations, clarifications, and examples.
    """
    qa_prompt = """You are an expert Q&A agent.

Your role:
- Answer student questions clearly and directly
- Provide relevant examples and analogies
- Connect answers to broader lesson context
- Check for understanding
- Encourage curiosity (no "dumb questions")
- Keep answers concise (1-2 minutes)

Use conversation history and course content for context."""

    qa_tools = [retrieve_course_content, query_conversation_history]
    
    # LangGraph v1.0+ API
    agent = create_agent(
        llm,
        tools=qa_tools,
        system_prompt=qa_prompt
    )
    
    return agent


def create_assessment_agent(llm: ChatOpenAI) -> StateGraph:
    """
    Specialized agent for assessments, quizzes, and knowledge checks.
    Focuses on evaluation and feedback.
    """
    assessment_prompt = """You are an expert assessment agent.

Your role:
- Generate appropriate quiz questions
- Evaluate student answers
- Provide constructive feedback
- Adapt difficulty based on performance
- Track learning progress
- Encourage improvement

Be supportive and educational in your feedback."""

    assessment_tools = [
        generate_quiz_question,
        save_assessment_result,
        query_conversation_history
    ]
    
    # LangGraph v1.0+ API
    agent = create_agent(
        llm,
        tools=assessment_tools,
        system_prompt=assessment_prompt
    )
    
    return agent


def create_navigation_agent(llm: ChatOpenAI) -> StateGraph:
    """
    Specialized agent for course navigation, progress tracking, and session management.
    """
    navigation_prompt = """You are a course navigation assistant.

Your role:
- Help students navigate course content
- Track progress through modules
- Handle pause/resume requests
- Provide course overview and roadmap
- Manage bookmarks and saved positions
- Suggest next steps

Be helpful and organized."""

    navigation_tools = [query_conversation_history]
    
    # LangGraph v1.0+ API
    agent = create_agent(
        llm,
        tools=navigation_tools,
        system_prompt=navigation_prompt
    )
    
    return agent


# ============================================================================
# WRAP SUB-AGENTS AS TOOLS
# ============================================================================

@tool
def route_to_teaching_agent(request: str) -> str:
    """
    Route to teaching agent for content delivery.
    
    Use when:
    - User wants to continue learning
    - User says "continue", "next", "teach me"
    - Starting a new lesson or module
    - Delivering core teaching content
    
    Input: Natural language request or context
    """
    # This will be replaced with actual agent invocation
    return f"ROUTE: teaching_agent | Request: {request}"


@tool
def route_to_qa_agent(request: str) -> str:
    """
    Route to Q&A agent for answering questions.
    
    Use when:
    - User asks a question (what, why, how, can you explain)
    - User requests clarification or more details
    - User wants examples or demonstrations
    - User seems confused
    
    Input: Student's question or request
    """
    return f"ROUTE: qa_agent | Request: {request}"


@tool
def route_to_assessment_agent(request: str) -> str:
    """
    Route to assessment agent for quizzes and evaluation.
    
    Use when:
    - User wants to take a quiz or test
    - User asks "quiz me", "test my knowledge"
    - User wants to check understanding
    - Time for knowledge check
    
    Input: Assessment request or context
    """
    return f"ROUTE: assessment_agent | Request: {request}"


@tool
def route_to_navigation_agent(request: str) -> str:
    """
    Route to navigation agent for course management.
    
    Use when:
    - User wants to pause or stop
    - User asks about progress or completion status
    - User wants to skip or go back
    - User asks about course structure
    
    Input: Navigation request
    """
    return f"ROUTE: navigation_agent | Request: {request}"


# ============================================================================
# SUPERVISOR AGENT
# ============================================================================

def create_supervisor_agent(llm: ChatOpenAI) -> StateGraph:
    """
    Supervisor agent that intelligently routes to specialized sub-agents.
    
    Uses LLM to analyze user intent and route to the most appropriate agent.
    """
    supervisor_prompt = """You are a supervisor coordinating a teaching system with specialized agents.

Your specialized agents:
1. **Teaching Agent**: Delivers course content, explains concepts pedagogically
2. **Q&A Agent**: Answers questions, provides clarifications and examples
3. **Assessment Agent**: Creates quizzes, evaluates understanding, gives feedback
4. **Navigation Agent**: Manages course progress, pauses, bookmarks, navigation

Your role:
- Analyze user input to determine intent
- Route to the most appropriate specialized agent
- Coordinate multi-step workflows (e.g., teach → quiz → teach)
- Maintain context across agent transitions
- Ensure smooth user experience

Routing guidelines:
- If user wants to learn/continue → Teaching Agent
- If user asks a question → Q&A Agent
- If user wants quiz/test → Assessment Agent
- If user wants to pause/navigate → Navigation Agent

Be intelligent about routing - consider conversation context and user needs."""

    supervisor_tools = [
        route_to_teaching_agent,
        route_to_qa_agent,
        route_to_assessment_agent,
        route_to_navigation_agent
    ]
    
    # LangGraph v1.0+ API
    supervisor = create_agent(
        llm,
        tools=supervisor_tools,
        system_prompt=supervisor_prompt
    )
    
    return supervisor


# ============================================================================
# BUILD SUPERVISOR SYSTEM
# ============================================================================

async def create_supervisor_teaching_system(redis_url: str) -> StateGraph:
    """
    Create complete supervisor-based multi-agent teaching system.
    Compatible with LangGraph v1.0.5 and LangChain v1.2.
    
    Architecture:
        User Input → Supervisor → Routes to specialized agent → Response
        
    Args:
        redis_url: Redis connection string (e.g., 'redis://localhost:6379')
    
    Returns:
        Compiled StateGraph with supervisor orchestration
    """
    # Initialize async Redis checkpointer - proper async context manager pattern
    checkpointer = await AsyncRedisSaver.from_conn_string(redis_url).__aenter__()
    try:
        await checkpointer.asetup()  # Create required indices asynchronously
        print("✅ Async Redis checkpointer initialized (indices created)")
    except Exception as e:
        print(f"⚠️ Redis checkpointer setup warning: {e}")
        # Continue anyway - may already be set up
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0.7, streaming=True)
    
    # Create specialized sub-agents
    teaching_agent = create_teaching_agent(llm)
    qa_agent = create_qa_agent(llm)
    assessment_agent = create_assessment_agent(llm)
    navigation_agent = create_navigation_agent(llm)
    
    # Create supervisor
    supervisor = create_supervisor_agent(llm)
    
    # Build workflow
    workflow = StateGraph(SupervisorState)
    
    # Add supervisor as main coordinator
    workflow.add_node("supervisor", supervisor)
    
    # Add specialized agents
    workflow.add_node("teaching_agent", teaching_agent)
    workflow.add_node("qa_agent", qa_agent)
    workflow.add_node("assessment_agent", assessment_agent)
    workflow.add_node("navigation_agent", navigation_agent)
    
    # Entry point: Always start with supervisor
    workflow.add_edge(START, "supervisor")
    
    # Supervisor routes to specialized agents based on intent
    # In production, this would be conditional routing based on supervisor's decision
    # For now, using simple edges (will be enhanced with conditional logic)
    
    def route_from_supervisor(state: SupervisorState) -> Literal["teaching_agent", "qa_agent", "assessment_agent", "navigation_agent", END]:
        """
        Route from supervisor to appropriate agent based on analysis.
        """
        # Parse last message from supervisor to determine routing
        messages = state.get("messages", [])
        if not messages:
            return END
        
        last_message = messages[-1].content if hasattr(messages[-1], 'content') else ""
        
        # Simple keyword-based routing (in production, use LLM tool calling)
        if "ROUTE: teaching_agent" in last_message:
            return "teaching_agent"
        elif "ROUTE: qa_agent" in last_message:
            return "qa_agent"
        elif "ROUTE: assessment_agent" in last_message:
            return "assessment_agent"
        elif "ROUTE: navigation_agent" in last_message:
            return "navigation_agent"
        
        # Default to teaching
        return "teaching_agent"
    
    # Add conditional routing from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "teaching_agent": "teaching_agent",
            "qa_agent": "qa_agent",
            "assessment_agent": "assessment_agent",
            "navigation_agent": "navigation_agent",
            END: END
        }
    )
    
    # All agents return to supervisor for next decision (or can go to END)
    def should_continue(state: SupervisorState) -> Literal["supervisor", END]:
        """Determine if we should continue routing or end."""
        # Check if task is complete
        waiting = state.get("waiting_for_continue", False)
        current_seg = state.get("current_segment", 0)
        total_seg = state.get("total_segments", 1)
        
        if current_seg >= total_seg and not waiting:
            return END
        
        # Continue to supervisor for next routing decision
        return "supervisor"
    
    workflow.add_conditional_edges(
        "teaching_agent",
        should_continue,
        {"supervisor": "supervisor", END: END}
    )
    
    workflow.add_conditional_edges(
        "qa_agent",
        should_continue,
        {"supervisor": "supervisor", END: END}
    )
    
    workflow.add_conditional_edges(
        "assessment_agent",
        should_continue,
        {"supervisor": "supervisor", END: END}
    )
    
    workflow.add_conditional_edges(
        "navigation_agent",
        should_continue,
        {"supervisor": "supervisor", END: END}
    )
    
    # Compile with Redis checkpointing (already initialized above)
    graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=[],
        interrupt_after=[]
    )
    
    return graph


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def initialize_supervisor_session(
    session_id: str,
    user_id: str,
    course_id: int,
    module_index: int,
    sub_topic_index: int,
    total_segments: int = 10
) -> dict:
    """
    Initialize supervisor teaching session.
    """
    initial_state = {
        "messages": [
            SystemMessage(content="Multi-agent teaching system initialized. Supervisor ready.")
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
        "assessments_completed": 0,
        "next_agent": None,
        "last_agent": None,
        "is_teaching": False,
        "waiting_for_continue": False,
        "assessment_mode": False
    }
    
    return initial_state


async def process_with_supervisor(
    graph,
    user_input: str,
    thread_id: str
) -> dict:
    """
    Process user input through supervisor system.
    
    Args:
        graph: Compiled supervisor graph
        user_input: User's text input
        thread_id: Thread ID for checkpointing
    
    Returns:
        Updated state after supervisor routing
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    input_state = {
        "messages": [HumanMessage(content=user_input)]
    }
    
    result = await graph.ainvoke(input_state, config=config)
    
    return result
