# Chat Service LangChain 1.0 Upgrade Plan

## Current Architecture (Deprecated)

```
User Query → Semantic Router → RAGService (chains) → Response
                             → LLMService → Response
```

### Problems:
1. **RAGService uses deprecated chains pattern**
2. **Manual memory management** (partially fixed)
3. **No tool-based retrieval**
4. **Direct service orchestration instead of agent pattern**

---

## New Architecture (LangChain 1.0)

```
User Query → Semantic Router → Agent with Tools → Response
                                  ├─ retrieve_context (tool)
                                  ├─ general_llm (tool)
                                  └─ greeting_handler (tool)
```

### Benefits:
1. ✅ **Native conversation state** (messages list)
2. ✅ **Tool-based retrieval** (modern pattern)
3. ✅ **Agent decides when to use RAG**
4. ✅ **Middleware for memory management**
5. ✅ **Better error handling and fallbacks**

---

## Implementation Steps

### Step 1: Create Retrieval Tool
**File:** `services/retrieval_tool.py` (new)

```python
from langchain.tools import tool
from typing import Tuple, List
from langchain_core.documents import Document

@tool(response_format="content_and_artifact")
def retrieve_course_context(query: str) -> Tuple[str, List[Document]]:
    """Retrieve relevant course content to answer student questions."""
    # Uses existing vector_store
    retrieved_docs = vector_store.similarity_search(query, k=5)
    serialized = "\n\n".join(
        f"Source: {doc.metadata.get('source', 'Unknown')}\n"
        f"Content: {doc.page_content}"
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs
```

### Step 2: Replace RAGService with Agent
**File:** `services/chat_service.py` (updated)

```python
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

class ChatService:
    def __init__(self):
        # Initialize model
        self.model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Create retrieval tool
        self.retrieval_tool = self._create_retrieval_tool()
        
        # Create agent with tools
        self.agent = create_agent(
            model=self.model,
            tools=[self.retrieval_tool],
            system_prompt=self._build_system_prompt()
        )
        
        # Session state storage
        self.sessions = {}  # session_id -> messages list
```

### Step 3: Message-Based Conversation
**Pattern:** Store messages as dicts with role/content

```python
def _get_messages(self, session_id: str) -> List[dict]:
    """Get message history for session."""
    if session_id not in self.sessions:
        self.sessions[session_id] = []
    return self.sessions[session_id]

def _add_message(self, session_id: str, role: str, content: str):
    """Add message to session history."""
    messages = self._get_messages(session_id)
    messages.append({"role": role, "content": content})
    
    # Trim to last 10 exchanges (20 messages)
    if len(messages) > 20:
        self.sessions[session_id] = messages[-20:]
```

### Step 4: Agent Invocation
**Pattern:** Pass messages to agent, not raw strings

```python
async def ask_question(self, query: str, session_id: str, language: str = "en-IN"):
    # Get existing conversation
    messages = self._get_messages(session_id)
    
    # Add user message
    messages.append({"role": "user", "content": query})
    
    # Invoke agent with full message history
    response = await self.agent.ainvoke(
        {"messages": messages},
        {"configurable": {"thread_id": session_id}}
    )
    
    # Extract answer from agent response
    answer = response["messages"][-1].content
    
    # Save assistant message
    messages.append({"role": "assistant", "content": answer})
    
    return {"answer": answer, "sources": ["Agent"]}
```

### Step 5: Integration with Semantic Router
**Strategy:** Use router for intent, then route to appropriate agent behavior

```python
# Option A: Single agent with dynamic system prompt
routing_result = self.semantic_router.classify_intent(query)

if routing_result["route_name"] == "greeting":
    # Skip agent, return pre-defined response
    return {"answer": self.get_greeting(), "route": "greeting"}

# For course_query and general_question, use agent
# Agent will decide whether to use retrieval tool

# Option B: Multiple specialized agents
if routing_result["route_name"] == "course_query":
    agent = self.rag_agent  # Has retrieval tool
else:
    agent = self.general_agent  # No retrieval tool
```

---

## Migration Checklist

- [ ] Create `retrieval_tool.py` with @tool decorator
- [ ] Update `chat_service.py` to use create_agent
- [ ] Remove RAGService dependency (will update separately)
- [ ] Implement message-based state management
- [ ] Test with semantic router integration
- [ ] Add error handling for tool failures
- [ ] Update response format for API compatibility
- [ ] Test multilingual support with new pattern
- [ ] Verify session management works
- [ ] Performance testing vs old implementation

---

## Files to Update

1. **services/chat_service.py** - Main redesign
2. **services/retrieval_tool.py** - New file (tool)
3. **services/rag_service.py** - Will deprecate or simplify
4. **app_celery.py** - Update imports if needed
5. **websocket_server.py** - Verify compatibility

---

## Testing Strategy

1. **Unit Tests**: Test retrieval tool independently
2. **Integration Tests**: Test agent with mock vector store
3. **E2E Tests**: Test full conversation flow
4. **Performance Tests**: Compare to old implementation

---

## Rollback Plan

Keep old implementation in `chat_service_legacy.py` for 1 week before deletion.

