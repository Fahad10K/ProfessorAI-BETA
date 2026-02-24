# Session Storage & Memory - Current vs Database-Backed

## 🔍 **Current Implementation (In-Memory)**

### Where Sessions Are Stored:
```python
# File: services/chat_service_v2.py, line 45-46

class ChatServiceV2:
    def __init__(self):
        # Session state: session_id -> list of message dicts
        self.sessions = {}  # ⚠️ Python dictionary (RAM only)
        self.max_messages = 20  # Keep last 20 messages (10 exchanges)
```

**Storage:** `self.sessions` is a **Python dictionary in RAM**

**Structure:**
```python
self.sessions = {
    "abc-123-uuid": [
        {"role": "user", "content": "Hi, my name is Alice"},
        {"role": "assistant", "content": "Hello Alice! How can I help you?"},
        {"role": "user", "content": "What's my name?"},
        {"role": "assistant", "content": "Your name is Alice."}
    ],
    "def-456-uuid": [
        {"role": "user", "content": "Tell me about robotics"},
        {"role": "assistant", "content": "Robotics is the science..."}
    ]
}
```

---

## ⚠️ **Current Limitations:**

| Issue | Impact |
|-------|--------|
| **RAM Only** | Sessions lost on server restart |
| **No Persistence** | Can't resume conversation after app crash |
| **Single Server** | Won't work with load-balanced servers |
| **No History** | Can't retrieve old conversations |
| **Memory Leaks** | Dictionary grows forever (no cleanup) |

---

## 🎯 **How LangChain Memory Works in V2:**

**Answer:** We're **NOT using LangChain's memory classes** anymore!

### Old Way (Deprecated):
```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(k=10)  # ❌ Deprecated in LangChain 1.0
```

### New Way (LangChain 1.0):
```python
# Simple message list - agent handles conversation context
messages = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
]

# Agent receives full message history
response = await agent.ainvoke({"messages": messages})
```

**LangChain 1.0 Philosophy:**
- ✅ **Message lists** instead of Memory classes
- ✅ **Agent decides** what context to use
- ✅ **You manage** storage (DB, Redis, etc.)
- ✅ **More flexible** and transparent

---

## 📊 **Database-Backed Session Design**

### Recommended Schema:

#### Table 1: `chat_sessions`
```sql
CREATE TABLE chat_sessions (
    session_id UUID PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),  -- Optional: link to user account
    created_at TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB,  -- Store: language, course_id, etc.
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_sessions_last_message ON chat_sessions(last_message_at);
```

#### Table 2: `chat_messages`
```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB  -- Store: route, confidence, sources, etc.
);

CREATE INDEX idx_messages_session ON chat_messages(session_id, created_at);
```

---

## 🔧 **Implementation Options**

### Option 1: PostgreSQL (Your Neon DB)
**Pros:**
- ✅ Already have Neon PostgreSQL
- ✅ ACID transactions
- ✅ Complex queries
- ✅ Good for analytics

**Cons:**
- ⚠️ Slower than Redis for reads
- ⚠️ More overhead for simple KV storage

### Option 2: Redis
**Pros:**
- ✅ Ultra-fast (sub-millisecond)
- ✅ Perfect for session cache
- ✅ TTL support (auto-expire old sessions)
- ✅ Already using Redis for Celery

**Cons:**
- ⚠️ Limited persistence options
- ⚠️ Need separate DB for long-term history

### Option 3: Hybrid (Best Approach) ⭐
**Architecture:**
```
Redis (Hot Cache)          PostgreSQL (Cold Storage)
├─ Last 10 messages        ├─ Full conversation history
├─ Active sessions         ├─ User analytics
├─ Fast reads (<1ms)       ├─ Search & export
└─ Auto-expire after 24h   └─ Long-term storage
```

**Flow:**
1. User sends message → Check Redis for session
2. If found in Redis → Use cached messages
3. If not in Redis → Load from PostgreSQL → Cache in Redis
4. After each message → Update both Redis & PostgreSQL
5. Old sessions → Auto-expire from Redis, stay in DB

---

## 💾 **Implementation Code**

### Session Manager Service:
```python
# services/session_manager.py

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import redis
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class SessionManager:
    """Hybrid session storage: Redis (cache) + PostgreSQL (persistence)"""
    
    def __init__(self, redis_url: str = None, use_redis: bool = True):
        self.use_redis = use_redis
        self.db = DatabaseService()
        
        if use_redis and redis_url:
            try:
                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                logger.info("✅ Redis connected for session cache")
            except Exception as e:
                logger.warning(f"⚠️ Redis unavailable: {e}, using DB only")
                self.use_redis = False
                self.redis = None
        else:
            self.redis = None
            self.use_redis = False
    
    def _redis_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"session:{session_id}:messages"
    
    async def get_messages(self, session_id: str, limit: int = 20) -> List[Dict]:
        """
        Get conversation messages for a session.
        Tries Redis first (fast), falls back to DB.
        """
        # Try Redis cache first
        if self.use_redis and self.redis:
            try:
                cached = self.redis.get(self._redis_key(session_id))
                if cached:
                    messages = json.loads(cached)
                    logger.info(f"💨 Cache HIT: {len(messages)} messages from Redis")
                    return messages[-limit:]  # Return last N messages
            except Exception as e:
                logger.warning(f"Redis read failed: {e}")
        
        # Fallback to database
        try:
            messages = self.db.get_session_messages(session_id, limit=limit)
            logger.info(f"💾 Cache MISS: {len(messages)} messages from DB")
            
            # Cache in Redis for next time
            if self.use_redis and self.redis and messages:
                try:
                    self.redis.setex(
                        self._redis_key(session_id),
                        timedelta(hours=24),  # Expire after 24 hours
                        json.dumps(messages)
                    )
                except Exception as e:
                    logger.warning(f"Redis cache write failed: {e}")
            
            return messages
        except Exception as e:
            logger.error(f"Failed to load messages from DB: {e}")
            return []
    
    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Dict = None
    ):
        """
        Add a message to the session.
        Updates both Redis (cache) and PostgreSQL (persistence).
        """
        message = {
            "role": role,
            "content": content,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # 1. Save to database (persistence)
        try:
            self.db.add_message(session_id, role, content, metadata)
            logger.info(f"💾 Message saved to DB")
        except Exception as e:
            logger.error(f"Failed to save message to DB: {e}")
        
        # 2. Update Redis cache
        if self.use_redis and self.redis:
            try:
                key = self._redis_key(session_id)
                
                # Get current messages
                cached = self.redis.get(key)
                messages = json.loads(cached) if cached else []
                
                # Append new message
                messages.append(message)
                
                # Keep only last 50 messages in cache
                if len(messages) > 50:
                    messages = messages[-50:]
                
                # Save back to Redis
                self.redis.setex(
                    key,
                    timedelta(hours=24),
                    json.dumps(messages)
                )
                logger.info(f"💨 Cache updated")
            except Exception as e:
                logger.warning(f"Redis cache update failed: {e}")
    
    async def create_session(
        self, 
        session_id: str, 
        user_id: int = None,
        metadata: Dict = None
    ):
        """Create a new session in the database."""
        try:
            self.db.create_session(session_id, user_id, metadata)
            logger.info(f"✅ Session {session_id} created")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
    
    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session metadata."""
        try:
            return self.db.get_session(session_id)
        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return None
    
    async def cleanup_old_sessions(self, days: int = 30):
        """Delete sessions older than N days."""
        try:
            deleted = self.db.delete_old_sessions(days)
            logger.info(f"🧹 Cleaned up {deleted} old sessions")
            return deleted
        except Exception as e:
            logger.error(f"Session cleanup failed: {e}")
            return 0
```

---

## 🔌 **Integration with ChatServiceV2:**

### Updated chat_service_v2.py:
```python
class ChatServiceV2:
    def __init__(self):
        # OLD: In-memory sessions
        # self.sessions = {}
        
        # NEW: Database-backed sessions
        from services.session_manager import SessionManager
        self.session_manager = SessionManager(
            redis_url=config.REDIS_URL,
            use_redis=True
        )
    
    def _get_messages(self, session_id: str) -> List[Dict]:
        """Get message history from DB/cache."""
        if not session_id:
            return []
        return await self.session_manager.get_messages(session_id, limit=20)
    
    def _add_message(self, session_id: str, role: str, content: str):
        """Save message to DB/cache."""
        if not session_id:
            return
        await self.session_manager.add_message(session_id, role, content)
```

---

## 📋 **Database Service Methods Needed:**

Add to `services/database_service.py`:

```python
def create_session(self, session_id: str, user_id: int = None, metadata: dict = None):
    query = """
        INSERT INTO chat_sessions (session_id, user_id, metadata)
        VALUES (%s, %s, %s)
        ON CONFLICT (session_id) DO NOTHING
    """
    self.execute(query, (session_id, user_id, json.dumps(metadata or {})))

def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
    query = """
        INSERT INTO chat_messages (session_id, role, content, metadata)
        VALUES (%s, %s, %s, %s)
    """
    self.execute(query, (session_id, role, content, json.dumps(metadata or {})))
    
    # Update last_message_at
    update_query = """
        UPDATE chat_sessions 
        SET last_message_at = NOW() 
        WHERE session_id = %s
    """
    self.execute(update_query, (session_id,))

def get_session_messages(self, session_id: str, limit: int = 20) -> List[Dict]:
    query = """
        SELECT role, content, created_at, metadata
        FROM chat_messages
        WHERE session_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    rows = self.fetch_all(query, (session_id, limit))
    return [
        {
            "role": row[0],
            "content": row[1],
            "created_at": row[2].isoformat(),
            "metadata": row[3]
        }
        for row in reversed(rows)  # Return chronological order
    ]
```

---

## 🎯 **Benefits of Database-Backed Sessions:**

| Feature | In-Memory | Database-Backed |
|---------|-----------|----------------|
| **Persistence** | ❌ Lost on restart | ✅ Survives restarts |
| **History** | ❌ No old conversations | ✅ Full chat history |
| **Multi-Server** | ❌ One server only | ✅ Load balancer ready |
| **User Analytics** | ❌ No insights | ✅ Query patterns, topics |
| **Export** | ❌ Can't export | ✅ Export to PDF/CSV |
| **Search** | ❌ No search | ✅ Search old chats |
| **Performance** | ⚡ Fast (RAM) | ⚡ Fast (Redis cache) |

---

## 🚀 **Recommendation:**

**Use Hybrid Approach:**
1. **Redis** for hot cache (last 10-20 messages, 24h TTL)
2. **PostgreSQL** for persistence (full history, forever)
3. **Auto-cleanup** old inactive sessions (>30 days)

This gives you:
- ✅ Fast performance (Redis)
- ✅ Data persistence (PostgreSQL)
- ✅ Cost efficiency (cache only active sessions)
- ✅ Scalability (works with multiple servers)

---

## 📝 **Next Steps:**

1. Create database tables (chat_sessions, chat_messages)
2. Implement SessionManager service
3. Add database methods to DatabaseService
4. Update ChatServiceV2 to use SessionManager
5. Test with real conversations
6. Add cleanup cron job for old sessions
