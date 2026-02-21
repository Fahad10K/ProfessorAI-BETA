"""
Teaching Orchestrator - Agentic System for Interactive Teaching
Manages teaching state, context, and pedagogical flow

CLOUD-READY: Uses Redis for state management (horizontally scalable)
"""

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import redis

class TeachingState(Enum):
    """States in the teaching state machine"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    TEACHING = "teaching"
    PAUSED = "paused"
    LISTENING = "listening"
    PROCESSING_QUESTION = "processing_question"
    ANSWERING = "answering"
    WAITING_FOR_CONTINUE = "waiting_for_continue"
    COMPLETED = "completed"
    ERROR = "error"

class IntentType(Enum):
    """Types of user intents"""
    QUESTION = "question"
    CONTINUE = "continue"
    PAUSE = "pause"
    REPEAT = "repeat"
    CLARIFY = "clarify"
    EXAMPLE = "example"
    SUMMARY = "summary"
    UNKNOWN = "unknown"

@dataclass
class TeachingContext:
    """Context for the current teaching session"""
    session_id: str
    user_id: str
    course_id: int
    module_index: int
    sub_topic_index: int
    current_state: str
    current_segment: int
    total_segments: int
    questions_asked: int
    interruptions: int
    last_user_input: Optional[str]
    last_assistant_response: Optional[str]
    teaching_started_at: str
    last_state_change: str
    pedagogical_notes: List[str]
    
    def to_dict(self):
        return asdict(self)
    
    def to_markdown(self) -> str:
        """Convert context to markdown format for LLM prompts"""
        return f"""# Teaching Session Context

## Session Info
- Session ID: {self.session_id}
- User ID: {self.user_id}
- Course ID: {self.course_id}
- Module: {self.module_index}, Sub-topic: {self.sub_topic_index}

## Progress
- Current State: {self.current_state}
- Segment: {self.current_segment}/{self.total_segments}
- Questions Asked: {self.questions_asked}
- Interruptions: {self.interruptions}

## Recent Interaction
- Last User Input: {self.last_user_input or 'None'}
- Last Response: {self.last_assistant_response or 'None'}

## Pedagogical Notes
{chr(10).join('- ' + note for note in self.pedagogical_notes) if self.pedagogical_notes else '- No notes yet'}

## Timing
- Started: {self.teaching_started_at}
- Last State Change: {self.last_state_change}
"""

class TeachingOrchestrator:
    """
    Agentic orchestrator for managing interactive teaching sessions
    Implements pedagogical strategies and state management
    
    CLOUD-READY: Uses Redis for session state (horizontally scalable)
    """
    
    def __init__(self, session_id: str, redis_client: Optional[redis.Redis] = None, 
                 state_ttl: int = 1800):
        """
        Initialize orchestrator with Redis backend
        
        Args:
            session_id: Unique session identifier
            redis_client: Redis client instance (uses session_manager's Redis if None)
            state_ttl: State TTL in seconds (default 30 minutes)
        """
        self.session_id = session_id
        self.redis_client = redis_client
        self.state_ttl = state_ttl
        self.context: Optional[TeachingContext] = None
        self.state_history: List[Dict] = []
        
        # Redis keys
        self.context_key = f"teaching:session:{session_id}:context"
        self.history_key = f"teaching:session:{session_id}:history"
        self.metrics_key = f"teaching:session:{session_id}:metrics"
        
        # Load existing state if available
        self._load_from_redis()
        
    def initialize(self, user_id: str, course_id: int, module_index: int, sub_topic_index: int, total_segments: int):
        """Initialize a new teaching session"""
        self.context = TeachingContext(
            session_id=self.session_id,
            user_id=user_id,
            course_id=course_id,
            module_index=module_index,
            sub_topic_index=sub_topic_index,
            current_state=TeachingState.INITIALIZING.value,
            current_segment=0,
            total_segments=total_segments,
            questions_asked=0,
            interruptions=0,
            last_user_input=None,
            last_assistant_response=None,
            teaching_started_at=datetime.now().isoformat(),
            last_state_change=datetime.now().isoformat(),
            pedagogical_notes=[]
        )
        self._save_to_redis()
        self._transition_state(TeachingState.TEACHING)
        
    def _transition_state(self, new_state: TeachingState, reason: str = ""):
        """Transition to a new state and log it"""
        if not self.context:
            return
            
        old_state = self.context.current_state
        self.context.current_state = new_state.value
        self.context.last_state_change = datetime.now().isoformat()
        
        # Log state transition
        transition = {
            "timestamp": datetime.now().isoformat(),
            "from": old_state,
            "to": new_state.value,
            "reason": reason
        }
        self.state_history.append(transition)
        self._save_to_redis()
        
    def classify_intent(self, user_input: str) -> IntentType:
        """Classify user intent from input"""
        user_input_lower = user_input.lower().strip()
        
        # Continue intents
        continue_keywords = ['continue', 'resume', 'go on', 'keep going', 'next', 'proceed', 
                            'carry on', 'move on', 'keep teaching', 'go ahead', 'okay']
        if any(kw in user_input_lower for kw in continue_keywords):
            # Check if it's JUST a continue phrase (not a question with "continue")
            if len(user_input_lower.split()) <= 3:
                return IntentType.CONTINUE
        
        # Pause intents
        pause_keywords = ['pause', 'stop', 'wait', 'hold on', 'hold']
        if any(kw in user_input_lower for kw in pause_keywords):
            return IntentType.PAUSE
        
        # Repeat intents
        repeat_keywords = ['repeat', 'again', 'say that again', 'one more time', 'didn\'t understand']
        if any(kw in user_input_lower for kw in repeat_keywords):
            return IntentType.REPEAT
        
        # Clarify intents
        clarify_keywords = ['clarify', 'explain more', 'elaborate', 'more details', 'confused']
        if any(kw in user_input_lower for kw in clarify_keywords):
            return IntentType.CLARIFY
        
        # Example intents
        example_keywords = ['example', 'instance', 'case', 'demonstrate', 'show me']
        if any(kw in user_input_lower for kw in example_keywords):
            return IntentType.EXAMPLE
        
        # Summary intents
        summary_keywords = ['summary', 'summarize', 'recap', 'review', 'main points']
        if any(kw in user_input_lower for kw in summary_keywords):
            return IntentType.SUMMARY
        
        # Question indicators
        question_keywords = ['what', 'why', 'how', 'when', 'where', 'who', 'which', 'can you', 'could you', 'tell me', 'explain']
        if any(kw in user_input_lower for kw in question_keywords) or user_input.strip().endswith('?'):
            return IntentType.QUESTION
        
        return IntentType.UNKNOWN
    
    def handle_user_input(self, user_input: str) -> Dict[str, Any]:
        """
        Handle user input and determine appropriate response
        Returns action to take
        """
        if not self.context:
            return {"action": "error", "message": "Session not initialized"}
        
        # Update context
        self.context.last_user_input = user_input
        
        # Classify intent
        intent = self.classify_intent(user_input)
        
        # Determine action based on current state and intent
        current_state = TeachingState(self.context.current_state)
        
        # Handle based on state and intent
        if intent == IntentType.CONTINUE:
            self._transition_state(TeachingState.TEACHING, f"User requested continue: '{user_input}'")
            return {
                "action": "continue_teaching",
                "intent": intent.value,
                "message": "Resuming the lesson..."
            }
        
        elif intent == IntentType.PAUSE:
            self._transition_state(TeachingState.PAUSED, f"User requested pause: '{user_input}'")
            return {
                "action": "pause",
                "intent": intent.value,
                "message": "Pausing. Say 'continue' when ready."
            }
        
        elif intent == IntentType.REPEAT:
            return {
                "action": "repeat_last",
                "intent": intent.value,
                "message": "Let me repeat that..."
            }
        
        elif intent in [IntentType.QUESTION, IntentType.CLARIFY, IntentType.EXAMPLE, IntentType.SUMMARY]:
            self.context.questions_asked += 1
            self._transition_state(TeachingState.PROCESSING_QUESTION, f"User asked: '{user_input}'")
            
            # Add pedagogical note
            self.context.pedagogical_notes.append(
                f"Q{self.context.questions_asked}: {intent.value} - {user_input[:50]}..."
            )
            
            return {
                "action": "answer_question",
                "intent": intent.value,
                "question": user_input,
                "context": self.get_pedagogical_context()
            }
        
        else:
            # Unknown intent - treat as question to be safe
            return {
                "action": "answer_question",
                "intent": IntentType.UNKNOWN.value,
                "question": user_input,
                "context": self.get_pedagogical_context()
            }
    
    def on_barge_in(self):
        """Handle user interruption"""
        if not self.context:
            return
            
        self.context.interruptions += 1
        self._transition_state(TeachingState.LISTENING, "User interrupted")
        self._save_to_redis()
    
    def on_answer_complete(self):
        """Handle completion of answer"""
        if not self.context:
            return
            
        self._transition_state(TeachingState.WAITING_FOR_CONTINUE, "Answer complete")
        self._save_to_redis()
    
    def advance_segment(self):
        """Move to next segment"""
        if not self.context:
            return
            
        self.context.current_segment += 1
        self._save_to_redis()
    
    def get_pedagogical_context(self) -> str:
        """Get current context for LLM prompts"""
        if not self.context:
            return "No context available"
        
        return self.context.to_markdown()
    
    def get_teaching_prompt(self, content: str) -> str:
        """Generate pedagogical teaching prompt"""
        context = self.get_pedagogical_context()
        
        return f"""{context}

## Your Role
You are an expert professor delivering an interactive lesson. Your teaching style is:
- **Engaging**: Use storytelling, real-world examples, and relatable analogies
- **Socratic**: Ask thought-provoking questions to engage critical thinking
- **Adaptive**: Adjust explanations based on student questions and understanding
- **Clear**: Break complex concepts into digestible pieces
- **Encouraging**: Provide positive reinforcement and build confidence

## Current Content to Teach
{content}

## Teaching Instructions
1. Deliver this content in a conversational, engaging manner
2. Use the "explain like I'm learning this for the first time" approach
3. Incorporate examples and analogies where helpful
4. Pause naturally to let concepts sink in
5. If this builds on previous content, briefly reference it
6. Keep segments concise (2-3 minutes of speaking)

Deliver the teaching in a natural, professor-like tone:"""
    
    def get_answer_prompt(self, question: str, content: str) -> str:
        """Generate pedagogical answer prompt"""
        context = self.get_pedagogical_context()
        
        return f"""{context}

## Student Question
{question}

## Course Content Context
{content}

## Your Role
You are an expert professor answering a student's question during a lesson. Your approach:
- **Directly address** the question first
- **Connect** the answer to the broader lesson context
- **Provide examples** to illustrate the concept
- **Check understanding** by relating to what you've already taught
- **Be encouraging** - there are no "dumb questions"
- **Keep it concise** - 1-2 minutes of speaking maximum

Answer the question naturally and pedagogically:"""
    
    def _load_from_redis(self):
        """Load existing state from Redis if available"""
        if not self.redis_client:
            return
        
        try:
            # Load context
            context_json = self.redis_client.get(self.context_key)
            if context_json:
                context_dict = json.loads(context_json)
                self.context = TeachingContext(**context_dict)
            
            # Load state history
            history_json = self.redis_client.get(self.history_key)
            if history_json:
                self.state_history = json.loads(history_json)
        except Exception as e:
            print(f"Error loading from Redis: {e}")
    
    def _save_to_redis(self):
        """Save context to Redis with TTL (cloud-ready, horizontally scalable)"""
        if not self.context or not self.redis_client:
            return
        
        try:
            # Save context with TTL
            context_json = json.dumps(self.context.to_dict())
            self.redis_client.setex(self.context_key, self.state_ttl, context_json)
            
            # Save state history (last 20 transitions)
            history_json = json.dumps(self.state_history[-20:])
            self.redis_client.setex(self.history_key, self.state_ttl, history_json)
            
            # Update metrics
            metrics = {
                "questions_asked": self.context.questions_asked,
                "interruptions": self.context.interruptions,
                "current_segment": self.context.current_segment,
                "total_segments": self.context.total_segments,
                "last_updated": datetime.now().isoformat()
            }
            self.redis_client.setex(self.metrics_key, self.state_ttl, json.dumps(metrics))
            
        except Exception as e:
            print(f"Error saving to Redis: {e}")
    
    def cleanup(self):
        """Cleanup session resources - delete from Redis"""
        if not self.redis_client:
            return
        
        try:
            # Delete all session keys from Redis
            self.redis_client.delete(
                self.context_key,
                self.history_key,
                self.metrics_key
            )
            print(f"Cleaned up Redis keys for session {self.session_id}")
        except Exception as e:
            print(f"Error cleaning up Redis keys: {e}")
