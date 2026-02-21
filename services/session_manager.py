"""
Session Manager - Hybrid PostgreSQL + Redis session management
Handles user sessions and conversation history with caching
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

# Optional Redis support
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using database only for sessions")

from services.database_service_v2 import get_database_service

class SessionManager:
    """Hybrid session storage: Redis (cache) + PostgreSQL (persistence)"""
    
    def __init__(self, redis_url: str = None, use_redis: bool = True):
        self.db = get_database_service()
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.redis = None
        
        if self.use_redis and redis_url:
            # Try to initialize Redis
            try:
                # Create Redis connection - redis-py 6.4.0+ compatible
                # SSL is auto-detected from redis:// vs rediss:// URL scheme
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis.ping()
                self.use_redis = True
                logger.info("✅ Redis cache initialized")
            except Exception as e:
                logger.warning(f"⚠️ Redis unavailable: {e}, using DB only")
                self.redis = None
                self.use_redis = False
        else:
            self.use_redis = False
    
    def _redis_key(self, session_id: str, suffix: str = "messages") -> str:
        """Generate Redis key for session data"""
        return f"session:{session_id}:{suffix}"
    
    def get_or_create_session(
        self, 
        user_id: int,
        ip_address: str = None,
        user_agent: str = None,
        device_type: str = None
    ) -> Dict:
        """
        Get existing active session for user or create new one.
        Returns session info with session_id.
        """
        # Check if user has active session in database
        session = self.db.get_user_session(user_id)
        
        if session and session.get('is_active'):
            logger.info(f"📍 Found existing session {session['session_id']} for user {user_id}")
            # Update last activity
            self.db.update_session_activity(session['session_id'])
            return session
        
        # Create new session
        session_id = str(uuid.uuid4())
        session = self.db.create_user_session(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_type
        )
        
        if session:
            logger.info(f"🆕 Created new session {session_id} for user {user_id}")
            return session
        
        raise Exception(f"Failed to create session for user {user_id}")
    
    def get_session(self, user_id: int) -> Optional[Dict]:
        """Get active session for user"""
        return self.db.get_user_session(user_id)
    
    def get_messages(
        self, 
        session_id: str, 
        limit: int = 20
    ) -> List[Dict]:
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
        messages = self.db.get_session_messages(session_id, limit=limit)
        logger.info(f"💾 Retrieved {len(messages)} messages from DB")
        
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
    
    def add_message(
        self,
        user_id: int,
        session_id: str,
        role: str,
        content: str,
        message_type: str = 'text',
        course_id: int = None,
        metadata: Dict = None,
        tokens_used: int = None,
        model_used: str = None
    ) -> Optional[Dict]:
        """
        Add a message to the session.
        Updates both Redis (cache) and PostgreSQL (persistence).
        """
        # Save to database (persistence)
        message = self.db.add_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            course_id=course_id,
            metadata=metadata,
            tokens_used=tokens_used,
            model_used=model_used
        )
        
        if not message:
            logger.error("Failed to save message to database")
            return None
        
        logger.info(f"💾 Message saved to DB")
        
        # Update Redis cache
        if self.use_redis and self.redis:
            try:
                key = self._redis_key(session_id)
                
                # Get current messages from cache
                cached = self.redis.get(key)
                messages = json.loads(cached) if cached else []
                
                # Append new message
                messages.append({
                    "role": role,
                    "content": content,
                    "created_at": message.get('created_at', datetime.utcnow().isoformat())
                })
                
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
        
        # Update session activity timestamp
        self.db.update_session_activity(session_id)
        
        return message
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get conversation history formatted for LLM.
        Returns last N turns (turn = user + assistant pair).
        """
        return self.db.get_conversation_history(session_id, limit=limit)
    
    def end_session(self, session_id: str):
        """End a session and clear cache"""
        self.db.end_session(session_id)
        
        # Clear Redis cache
        if self.use_redis and self.redis:
            try:
                self.redis.delete(self._redis_key(session_id))
                logger.info(f"💨 Cache cleared for session {session_id}")
            except Exception as e:
                logger.warning(f"Redis cache clear failed: {e}")
    
    def cleanup_expired_sessions(self, days: int = 7):
        """Cleanup sessions older than N days (admin task)"""
        # This would be run as a cron job
        # TODO: Implement database cleanup query
        pass


# Global instance
_session_manager = None

def get_session_manager(redis_url: str = None) -> SessionManager:
    """Get or create session manager instance"""
    global _session_manager
    
    if _session_manager is None:
        import os
        redis_url = redis_url or os.getenv("REDIS_URL")
        _session_manager = SessionManager(redis_url=redis_url, use_redis=True)
        logger.info("✅ SessionManager initialized")
    
    return _session_manager
