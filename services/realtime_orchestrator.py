"""
Real-Time Teaching Orchestrator (Hybrid: Fast Pre-Router + LangGraph)

Architecture:
  User Input → RealtimeOrchestrator (Tier 1, <5ms, keyword-based)
    ├─ Obvious intents (continue, pause, repeat, bye) → Handle directly
    └─ Complex intents (question, teach) → LangGraph Teaching Agent (Tier 2)
         ├─ teach_content node (pedagogical LLM with gpt-4o-mini)
         ├─ answer_question node (RAG + conversation context + LLM)
         └─ Redis checkpointed state

Tier 1: Keyword-based intent classification (<5ms) for real-time responsiveness.
Tier 2: LangGraph teaching agent for LLM-powered pedagogical responses.
State: In-memory with optional Redis persistence.
"""

import asyncio
import json
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# ---- LangGraph Teaching Agent (Tier 2) ----
# Lazy import to avoid circular deps and allow graceful fallback
_langgraph_agent = None
_langgraph_available = False

def _try_import_langgraph():
    """Try to import and prepare LangGraph teaching agent components."""
    global _langgraph_available
    try:
        from services.langgraph_teaching_agent import (
            teach_content,
            answer_question,
            TeachingState as LGTeachingState,
        )
        _langgraph_available = True
        logger.info("✅ LangGraph teaching agent available (Tier 2)")
        return True
    except Exception as e:
        logger.warning(f"⚠️ LangGraph teaching agent not available: {e}")
        _langgraph_available = False
        return False


# =============================================================================
# TEACHING STATE MACHINE
# =============================================================================

class TeachingPhase(str, Enum):
    """Teaching session phases - stored per session."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    TEACHING = "teaching"
    PAUSED_FOR_QUERY = "paused_for_query"
    ANSWERING = "answering"
    WAITING_RESUME = "waiting_resume"
    PENDING_CONFIRMATION = "pending_confirmation"
    COMPLETED = "completed"
    ERROR = "error"


class UserIntent(str, Enum):
    """Classified user intents for fast routing."""
    QUESTION = "question"
    CONTINUE = "continue"
    PAUSE = "pause"
    REPEAT = "repeat"
    CLARIFY = "clarify"
    EXAMPLE = "example"
    SUMMARY = "summary"
    ADVANCE = "advance"
    MARK_COMPLETE = "mark_complete"
    NEXT_COURSE = "next_course"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    MARK_AND_NEXT_COURSE = "mark_and_next_course"
    GREETING = "greeting"
    FAREWELL = "farewell"
    UNKNOWN = "unknown"


@dataclass
class TeachingState:
    """Complete state for a teaching session."""
    session_id: str
    user_id: str
    course_id: int
    module_index: int
    sub_topic_index: int

    # User info (for personalised prompts)
    user_name: str = ""

    # State machine
    phase: str = TeachingPhase.IDLE.value
    previous_phase: str = TeachingPhase.IDLE.value

    # Content tracking for resume
    content_segments: List[str] = field(default_factory=list)
    current_segment_index: int = 0
    total_segments: int = 0
    content_char_offset: int = 0  # Where in content we were interrupted

    # Barge-in resume: text that was being spoken when user interrupted
    interrupted_text: str = ""

    # Course structure (for auto-advance)
    total_modules: int = 0
    total_sub_topics: int = 0  # Sub-topics in current module

    # Persona
    persona_id: str = ""

    # Confirmation flow: stores pending action when user is asked "mark as complete?"
    pending_action: str = ""       # e.g. "advance_next_topic", "next_course"
    pending_action_data: str = ""  # JSON-encoded payload for the pending action

    # Teaching metadata
    module_title: str = ""
    sub_topic_title: str = ""
    raw_content: str = ""
    teaching_content: str = ""

    # Interaction tracking
    questions_asked: int = 0
    interruptions: int = 0
    last_question: str = ""
    last_answer: str = ""
    last_intent: str = ""
    topic_marked_complete: bool = False  # Set when user marks current topic complete

    # Timing
    started_at: str = ""
    last_interaction_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TeachingState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# INTENT CLASSIFIER (Ultra-fast, no LLM call)
# =============================================================================

# Keyword sets for classification
_CONTINUE_KW = frozenset([
    'continue', 'resume', 'go on', 'keep going', 'next', 'proceed',
    'carry on', 'move on', 'keep teaching', 'go ahead', 'okay', 'ok',
    'yes continue', 'yes please', 'lets continue', "let's continue",
    'sure', 'yeah', 'yes', 'yep', 'alright', 'ready'
])

_PAUSE_KW = frozenset([
    'pause', 'stop', 'wait', 'hold on', 'hold', 'break',
    'one moment', 'one second', 'hang on'
])

_REPEAT_KW = frozenset([
    'repeat', 'again', 'say that again', 'one more time',
    "didn't understand", 'what did you say', 'come again',
    'say again', 'repeat that', 'can you repeat'
])

_CLARIFY_KW = frozenset([
    'clarify', 'explain more', 'elaborate', 'more details',
    'confused', "don't understand", 'what do you mean',
    'can you explain', 'tell me more', 'more about'
])

_EXAMPLE_KW = frozenset([
    'example', 'instance', 'case', 'demonstrate',
    'show me', 'give me an example', 'like what'
])

_SUMMARY_KW = frozenset([
    'summary', 'summarize', 'recap', 'review',
    'main points', 'key points', 'what did we learn'
])

_QUESTION_KW = frozenset([
    'what', 'why', 'how', 'when', 'where', 'who', 'which',
    'can you', 'could you', 'tell me', 'explain', 'define',
    'is it', 'are there', 'does it', 'do we'
])

_ADVANCE_KW = frozenset([
    'skip', 'next module', 'next topic', 'next lesson',
    'move to next', 'move on to next', 'skip to next',
    'skip ahead', 'skip this', 'jump to next',
    'go to next module', 'go to next topic',
    'advance', 'let\'s move on to the next',
])

_MARK_COMPLETE_KW = frozenset([
    'mark as complete', 'mark complete', 'mark it complete',
    'mark this complete', 'mark this as complete', 'completed',
    'i have completed', 'mark done', 'mark it done',
    'mark as done', 'i am done with this', 'finished this',
    'mark finished', 'complete this', "i'm done with this",
    "i'm done", 'done with this', 'finished with this',
    "that's all for this", 'done with this topic',
    'market complete', 'market is complete', 'market as complete',  # STT mishearings
    'market it complete', 'march complete', 'march as complete',
])

_NEXT_COURSE_KW = frozenset([
    'next course', 'move to next course', 'start next course',
    'go to next course', 'switch course', 'new course',
    'another course', 'different course', 'change course',
])

_CONFIRM_YES_KW = frozenset([
    'yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'do it',
    'yes please', 'go ahead', 'mark it', 'confirm', 'absolutely',
    'of course', 'definitely', 'please do', 'yes mark it',
    'yes do it', 'please mark', 'right', 'correct', 'affirmative',
    'market it', 'market is', 'market complete',  # common STT mishearings of "mark it/complete"
    'yes mark', 'please mark it', 'mark it as complete',
    'yes mark it as complete', 'let\'s do it', 'sounds good',
])

_CONFIRM_NO_KW = frozenset([
    'no', 'nope', 'not yet', 'don\'t', 'cancel', 'skip marking',
    'no thanks', 'not now', 'leave it', 'don\'t mark',
])

_GREETING_KW = frozenset([
    'hello', 'hi', 'hey', 'good morning', 'good afternoon',
    'good evening', 'greetings'
])

_FAREWELL_KW = frozenset([
    'bye', 'goodbye', 'see you', 'thank you', 'thanks',
    'end class', 'end session', 'end the class', 'end the session',
])


def _clean_first_name(raw_name: str) -> str:
    """Extract a clean first name from a username like 'vivek_sapra' → 'Vivek'."""
    if not raw_name:
        return "there"
    # Split on underscore, dash, dot, or space — take first part
    import re
    parts = re.split(r'[_\-.\s]+', raw_name.strip())
    first = parts[0] if parts else raw_name
    return first.capitalize()


def classify_intent(user_input: str, pending_confirmation: bool = False) -> UserIntent:
    """
    Ultra-fast intent classification using keyword matching.
    No LLM call needed - runs in <1ms.

    Args:
        user_input: Raw text from the student.
        pending_confirmation: When True, prioritise yes/no detection
            (the orchestrator is waiting for a confirmation answer).
    """
    text = user_input.lower().strip()
    words = text.split()
    word_count = len(words)

    # --- Compound: mark complete + next course in one sentence ---
    has_mark = any(kw in text for kw in _MARK_COMPLETE_KW)
    has_next_course = any(kw in text for kw in _NEXT_COURSE_KW)
    if has_mark and has_next_course:
        return UserIntent.MARK_AND_NEXT_COURSE

    # --- Confirmation yes/no (highest priority when awaiting) ---
    if pending_confirmation:
        # Check explicit yes/no first (no strict word-count limit)
        if any(kw in text for kw in _CONFIRM_YES_KW):
            return UserIntent.CONFIRM_YES
        if any(kw in text for kw in _CONFIRM_NO_KW):
            return UserIntent.CONFIRM_NO
        # If user repeats the action ("next course", "mark complete") while
        # we are waiting for confirmation, treat it as implicit YES
        if has_next_course or has_mark:
            return UserIntent.CONFIRM_YES

    # --- Mark-complete / next-course (check before advance) ---
    if has_mark:
        return UserIntent.MARK_COMPLETE
    if has_next_course:
        return UserIntent.NEXT_COURSE

    # --- Long inputs (>15 words): almost certainly a question, not a command ---
    # Skip short-phrase intents that could be embedded in a longer sentence
    # (e.g., "I was saying ok continue but then I realized I don't understand")
    if word_count > 15:
        # Only check for repeat/clarify/example/summary (multi-word phrases unlikely to be accidental)
        if any(kw in text for kw in _REPEAT_KW):
            return UserIntent.REPEAT
        if any(kw in text for kw in _CLARIFY_KW):
            return UserIntent.CLARIFY
        if any(kw in text for kw in _EXAMPLE_KW):
            return UserIntent.EXAMPLE
        if any(kw in text for kw in _SUMMARY_KW):
            return UserIntent.SUMMARY
        # Default long input to question
        return UserIntent.QUESTION

    # Short phrases (1-3 words) - check exact/near matches first
    if word_count <= 3:
        if any(kw in text for kw in _ADVANCE_KW):
            return UserIntent.ADVANCE
        if any(kw in text for kw in _CONTINUE_KW):
            return UserIntent.CONTINUE
        if any(kw in text for kw in _PAUSE_KW):
            return UserIntent.PAUSE
        if any(kw in text for kw in _GREETING_KW):
            return UserIntent.GREETING
        if any(kw in text for kw in _FAREWELL_KW):
            return UserIntent.FAREWELL

    # Medium inputs (4-15 words) - check intent keywords
    if any(kw in text for kw in _REPEAT_KW):
        return UserIntent.REPEAT
    if any(kw in text for kw in _CLARIFY_KW):
        return UserIntent.CLARIFY
    if any(kw in text for kw in _EXAMPLE_KW):
        return UserIntent.EXAMPLE
    if any(kw in text for kw in _SUMMARY_KW):
        return UserIntent.SUMMARY
    if any(kw in text for kw in _PAUSE_KW):
        return UserIntent.PAUSE
    # Advance / skip detection (no word-count limit)
    if any(kw in text for kw in _ADVANCE_KW):
        return UserIntent.ADVANCE
    if any(kw in text for kw in _CONTINUE_KW) and word_count <= 8:
        return UserIntent.CONTINUE

    # Question detection
    if text.endswith('?'):
        return UserIntent.QUESTION
    if any(text.startswith(kw) for kw in _QUESTION_KW):
        return UserIntent.QUESTION
    if any(kw in text for kw in _QUESTION_KW):
        return UserIntent.QUESTION

    # Default: treat as question (safest for teaching context)
    return UserIntent.QUESTION


def needs_rag(question: str, teaching_content: str) -> bool:
    """
    Decide if a question needs RAG (course-specific) or can be answered
    by general LLM. Fast heuristic, no LLM call.

    Returns True if RAG is needed.
    """
    text = question.lower().strip()

    # Course-specific keywords that need RAG
    course_kw = [
        'course', 'module', 'topic', 'lesson', 'lecture',
        'slide', 'chapter', 'syllabus', 'curriculum',
        'assignment', 'project', 'exam', 'quiz', 'test',
        'this topic', 'current topic', 'what we learned',
        'what you taught', 'what you said', 'in the course',
        'according to', 'in the lecture', 'in this module',
        'from the content', 'course content'
    ]

    if any(kw in text for kw in course_kw):
        return True

    # If the question seems related to the teaching content being discussed
    # Check if key terms from teaching content appear in the question
    if teaching_content:
        # Extract significant words from teaching content (>4 chars, not common)
        common_words = {'about', 'their', 'there', 'which', 'would', 'could',
                       'should', 'these', 'those', 'being', 'other', 'after',
                       'before', 'between', 'through', 'during', 'without',
                       'learn', 'first', 'second', 'third', 'using', 'allow'}
        content_words = set(
            w.lower().strip('.,!?;:') for w in teaching_content.split()
            if len(w) > 4 and w.lower().strip('.,!?;:') not in common_words
        )
        question_words = set(
            w.lower().strip('.,!?;:') for w in text.split()
            if len(w) > 4 and w.lower().strip('.,!?;:') not in common_words
        )

        if question_words and content_words:
            overlap = question_words & content_words
            # Require 2+ overlapping words to avoid false positives
            # (e.g., "machine" alone shouldn't trigger RAG for "how does a washing machine work?")
            if len(overlap) >= 2:
                return True

    # General questions don't need RAG
    return False


# =============================================================================
# CONTENT SEGMENTER
# =============================================================================

def segment_content(content: str, max_segment_chars: int = 800) -> List[str]:
    """
    Split teaching content into segments for resumable delivery.
    Splits at sentence boundaries for natural speech.
    """
    if not content:
        return []

    segments = []
    current = ""

    # Split by sentences (period, question mark, exclamation)
    sentences = []
    temp = ""
    for char in content:
        temp += char
        if char in '.?!' and len(temp.strip()) > 10:
            sentences.append(temp.strip())
            temp = ""
    if temp.strip():
        sentences.append(temp.strip())

    for sentence in sentences:
        if len(current) + len(sentence) > max_segment_chars and current:
            segments.append(current.strip())
            current = sentence
        else:
            current += " " + sentence if current else sentence

    if current.strip():
        segments.append(current.strip())

    return segments if segments else [content]


# =============================================================================
# REAL-TIME TEACHING ORCHESTRATOR
# =============================================================================

class RealtimeOrchestrator:
    """
    Fast, lightweight orchestrator for real-time teaching.

    Replaces the broken LangGraph supervisor with direct routing.
    Decision latency: <5ms (no LLM calls for routing).
    """

    def __init__(self, redis_client=None):
        self.sessions: Dict[str, TeachingState] = {}
        self.redis_client = redis_client
        self._redis_prefix = "profai:teach:"

    def create_session(
        self,
        session_id: str,
        user_id: str,
        course_id: int,
        module_index: int,
        sub_topic_index: int,
        module_title: str = "",
        sub_topic_title: str = "",
        user_name: str = "",
        persona_id: str = "",
    ) -> TeachingState:
        """Create a new teaching session with state tracking."""
        state = TeachingState(
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
            module_index=module_index,
            sub_topic_index=sub_topic_index,
            module_title=module_title,
            sub_topic_title=sub_topic_title,
            user_name=user_name,
            persona_id=persona_id,
            phase=TeachingPhase.INITIALIZING.value,
            started_at=datetime.utcnow().isoformat(),
            last_interaction_at=datetime.utcnow().isoformat(),
        )
        self.sessions[session_id] = state
        self._persist(state)
        logger.info(f"📚 Teaching session created: {session_id} (user: {user_name or user_id})")
        return state

    def get_session(self, session_id: str) -> Optional[TeachingState]:
        """Get existing session (memory first, then Redis)."""
        if session_id in self.sessions:
            return self.sessions[session_id]

        # Try Redis
        state = self._load(session_id)
        if state:
            self.sessions[session_id] = state
        return state

    def set_content(self, session_id: str, teaching_content: str, raw_content: str = ""):
        """Set teaching content and segment it for resumable delivery."""
        state = self.get_session(session_id)
        if not state:
            return

        state.teaching_content = teaching_content
        state.raw_content = raw_content
        state.content_segments = segment_content(teaching_content)
        state.total_segments = len(state.content_segments)
        state.current_segment_index = 0
        self._persist(state)

        logger.info(
            f"📝 Content set: {len(teaching_content)} chars, "
            f"{state.total_segments} segments"
        )

    def start_teaching(self, session_id: str) -> Optional[str]:
        """
        Transition to TEACHING and return the current segment to deliver.
        Returns None if no content or session.
        """
        state = self.get_session(session_id)
        if not state or not state.content_segments:
            return None

        self._transition(state, TeachingPhase.TEACHING)
        return self._current_segment_text(state)

    def on_barge_in(self, session_id: str, streaming_text: str = "") -> TeachingState:
        """Handle user interruption during teaching.
        
        Args:
            session_id: Session identifier
            streaming_text: The text that was being spoken when interrupted.
                           Saved so 'continue' can resume from it.
        """
        state = self.get_session(session_id)
        if not state:
            return None

        state.interruptions += 1
        if streaming_text:
            state.interrupted_text = streaming_text

        # Preserve PENDING_CONFIRMATION phase — the user is responding to
        # a yes/no prompt (e.g. "should I mark complete?"), not interrupting
        # teaching content. Resetting the phase here would destroy the
        # pending_action and cause the confirmation flow to break.
        if state.phase == TeachingPhase.PENDING_CONFIRMATION.value:
            logger.info(
                f"🗣️ Barge-in #{state.interruptions} during confirmation prompt "
                f"(preserving PENDING_CONFIRMATION)"
            )
        else:
            self._transition(state, TeachingPhase.PAUSED_FOR_QUERY)
            logger.info(
                f"🗣️ Barge-in #{state.interruptions} at segment "
                f"{state.current_segment_index}/{state.total_segments}"
                f"{' (text saved for resume)' if streaming_text else ''}"
            )
        return state

    def process_user_input(self, session_id: str, user_input: str) -> Dict[str, Any]:
        """
        Process user input and return action to take.

        Returns dict with:
        - action: "answer_with_rag", "answer_general", "continue_teaching",
                  "pause", "repeat", "end", "greeting"
        - intent: classified intent
        - needs_rag: bool
        - state: current teaching state
        """
        t0 = time.time()
        state = self.get_session(session_id)
        if not state:
            return {"action": "error", "message": "No active session"}

        # Classify intent (<1ms)
        pending = state.phase == TeachingPhase.PENDING_CONFIRMATION.value
        intent = classify_intent(user_input, pending_confirmation=pending)
        state.last_intent = intent.value
        state.last_interaction_at = datetime.utcnow().isoformat()

        logger.info(f"⚡ Intent classified: {intent.value} in {(time.time()-t0)*1000:.1f}ms")

        # ── Confirmation flow (yes/no after "should I mark complete?") ──
        if intent == UserIntent.CONFIRM_YES and pending:
            pending_act = state.pending_action
            pending_data_str = state.pending_action_data
            state.pending_action = ""
            state.pending_action_data = ""
            state.topic_marked_complete = True  # User confirmed marking complete
            self._transition(state, TeachingPhase.TEACHING)
            import json as _json
            pending_data = _json.loads(pending_data_str) if pending_data_str else {}
            if pending_act == "advance_next_topic":
                return {
                    "action": "mark_and_advance",
                    "intent": intent.value,
                    "mark_type": "topic",
                    "next_module_index": pending_data.get("next_module_index"),
                    "next_sub_topic_index": pending_data.get("next_sub_topic_index"),
                    "state": state,
                }
            elif pending_act == "next_course":
                return {
                    "action": "mark_and_next_course",
                    "intent": intent.value,
                    "state": state,
                }
            # Fallback: just mark complete
            adv = self._compute_next_topic(state)
            return {
                "action": "mark_complete",
                "intent": intent.value,
                "has_next": adv is not None,
                "next_module_index": adv["module_index"] if adv else None,
                "next_sub_topic_index": adv["sub_topic_index"] if adv else None,
                "state": state,
            }

        if intent == UserIntent.CONFIRM_NO and pending:
            pending_act = state.pending_action
            pending_data_str = state.pending_action_data
            state.pending_action = ""
            state.pending_action_data = ""
            import json as _json
            pending_data = _json.loads(pending_data_str) if pending_data_str else {}
            # Proceed without marking
            if pending_act == "advance_next_topic":
                self._transition(state, TeachingPhase.TEACHING)
                return {
                    "action": "advance_next_topic",
                    "intent": intent.value,
                    "next_module_index": pending_data.get("next_module_index"),
                    "next_sub_topic_index": pending_data.get("next_sub_topic_index"),
                    "state": state,
                }
            elif pending_act == "next_course":
                self._transition(state, TeachingPhase.TEACHING)
                return {
                    "action": "next_course",
                    "intent": intent.value,
                    "state": state,
                }
            self._transition(state, TeachingPhase.WAITING_RESUME)
            return {
                "action": "continue_teaching",
                "intent": intent.value,
                "segment_text": self._current_segment_text(state),
                "state": state,
            }

        # ── Compound: mark complete AND move to next course ──
        if intent == UserIntent.MARK_AND_NEXT_COURSE:
            state.topic_marked_complete = True
            return {
                "action": "mark_and_next_course",
                "intent": intent.value,
                "state": state,
            }

        # ── Mark complete (explicit request) ──
        if intent == UserIntent.MARK_COMPLETE:
            state.topic_marked_complete = True
            # After marking complete, set up follow-up to ask about advancing
            adv = self._compute_next_topic(state)
            return {
                "action": "mark_complete",
                "intent": intent.value,
                "has_next": adv is not None,
                "next_module_index": adv["module_index"] if adv else None,
                "next_sub_topic_index": adv["sub_topic_index"] if adv else None,
                "state": state,
            }

        # ── Next course ──
        if intent == UserIntent.NEXT_COURSE:
            # If topic was already marked complete, skip confirmation and go directly
            if state.topic_marked_complete:
                state.topic_marked_complete = False  # Reset for next topic
                return {
                    "action": "next_course",
                    "intent": intent.value,
                    "state": state,
                }
            name = _clean_first_name(state.user_name)
            # Ask for confirmation to mark current course complete
            import json as _json
            state.pending_action = "next_course"
            state.pending_action_data = ""
            self._transition(state, TeachingPhase.PENDING_CONFIRMATION)
            return {
                "action": "ask_confirmation",
                "intent": intent.value,
                "message": (
                    f"Sure {name}, before we move to the next course, "
                    f"should I mark the current course as complete?"
                ),
                "state": state,
            }

        # Route based on intent
        if intent == UserIntent.CONTINUE:
            self._transition(state, TeachingPhase.TEACHING)
            # If we have interrupted text from a barge-in, resume from it
            resume_text = None
            is_resume = False
            if state.interrupted_text:
                resume_text = state.interrupted_text
                state.interrupted_text = ""  # Clear after consuming
                is_resume = True
                self._persist(state)
                logger.info(f"▶️ Resuming interrupted content ({len(resume_text)} chars)")
            else:
                resume_text = self._current_segment_text(state)

            # Check if all segments of the current sub-topic are done
            if resume_text is None or (
                not is_resume
                and state.current_segment_index >= state.total_segments
            ):
                # All segments delivered — determine what's next
                adv = self._compute_next_topic(state)
                if adv is None:
                    # Course complete
                    self._transition(state, TeachingPhase.COMPLETED)
                    name = _clean_first_name(state.user_name)
                    return {
                        "action": "course_complete",
                        "intent": intent.value,
                        "message": (
                            f"Congratulations {name}! "
                            f"You've completed all topics in this course. "
                            f"Great job!"
                        ),
                        "state": state,
                    }
                return {
                    "action": "advance_next_topic",
                    "intent": intent.value,
                    "next_module_index": adv["module_index"],
                    "next_sub_topic_index": adv["sub_topic_index"],
                    "state": state,
                }

            return {
                "action": "continue_teaching",
                "intent": intent.value,
                "segment_text": resume_text,
                "segment_index": state.current_segment_index,
                "is_resume": is_resume,
                "state": state,
            }

        elif intent == UserIntent.ADVANCE:
            # User explicitly wants to skip to next topic/module
            adv = self._compute_next_topic(state)
            if adv is None:
                self._transition(state, TeachingPhase.COMPLETED)
                name = _clean_first_name(state.user_name)
                return {
                    "action": "course_complete",
                    "intent": intent.value,
                    "message": (
                        f"Congratulations {name}! "
                        f"You've completed all topics in this course. "
                        f"Great job!"
                    ),
                    "state": state,
                }
            # Ask confirmation to mark current topic complete before advancing
            name = _clean_first_name(state.user_name)
            import json as _json
            state.pending_action = "advance_next_topic"
            state.pending_action_data = _json.dumps({
                "next_module_index": adv["module_index"],
                "next_sub_topic_index": adv["sub_topic_index"],
            })
            self._transition(state, TeachingPhase.PENDING_CONFIRMATION)
            return {
                "action": "ask_confirmation",
                "intent": intent.value,
                "message": (
                    f"Sure {name}, before we move on, "
                    f"should I mark the current topic as complete?"
                ),
                "state": state,
            }

        elif intent == UserIntent.PAUSE:
            self._transition(state, TeachingPhase.PAUSED_FOR_QUERY)
            return {
                "action": "pause",
                "intent": intent.value,
                "message": "Paused. Say 'continue' when you're ready to resume.",
                "state": state,
            }

        elif intent == UserIntent.REPEAT:
            return {
                "action": "repeat",
                "intent": intent.value,
                "segment_text": self._current_segment_text(state),
                "state": state,
            }

        elif intent == UserIntent.FAREWELL:
            self._transition(state, TeachingPhase.COMPLETED)
            return {
                "action": "end",
                "intent": intent.value,
                "message": "Thank you for the session! See you next time.",
                "state": state,
            }

        elif intent == UserIntent.GREETING:
            return {
                "action": "greeting",
                "intent": intent.value,
                "message": "Hello! Let me know if you have a question, or say 'continue' to resume the lesson.",
                "state": state,
            }

        else:
            # QUESTION / CLARIFY / EXAMPLE / SUMMARY / UNKNOWN
            # All treated as questions that need answering
            state.questions_asked += 1
            state.last_question = user_input
            self._transition(state, TeachingPhase.ANSWERING)

            # Decide RAG vs general LLM
            use_rag = needs_rag(user_input, state.teaching_content)

            logger.info(
                f"❓ Q#{state.questions_asked}: '{user_input[:60]}...' "
                f"→ {'RAG' if use_rag else 'General LLM'}"
            )

            return {
                "action": "answer_with_rag" if use_rag else "answer_general",
                "intent": intent.value,
                "question": user_input,
                "needs_rag": use_rag,
                "state": state,
            }

    def on_answer_complete(self, session_id: str, answer_text: str):
        """
        Called after answering a question.
        Transitions to WAITING_RESUME.
        """
        state = self.get_session(session_id)
        if not state:
            return

        state.last_answer = answer_text
        self._transition(state, TeachingPhase.WAITING_RESUME)
        self._persist(state)

    def advance_segment(self, session_id: str) -> Optional[str]:
        """
        Move to next content segment. Returns next segment text or None if done.
        """
        state = self.get_session(session_id)
        if not state:
            return None

        state.current_segment_index += 1
        self._persist(state)

        if state.current_segment_index >= state.total_segments:
            # Sub-topic segments exhausted — wait for user to say "continue"
            # The CONTINUE handler will then auto-advance to next topic/module
            self._transition(state, TeachingPhase.WAITING_RESUME)
            return None

        return self._current_segment_text(state)

    def get_resume_text(self, session_id: str) -> str:
        """Get the text to say when asking user to resume."""
        state = self.get_session(session_id)
        if not state:
            return "Shall we continue?"

        name = _clean_first_name(state.user_name)
        remaining = state.total_segments - state.current_segment_index
        return (
            f"Is your doubt clear, {name}? "
            f"We have {remaining} more section{'s' if remaining > 1 else ''} to cover. "
            f"Say 'continue' when you're ready to resume."
        )

    def advance_topic(
        self,
        session_id: str,
        module_index: int,
        sub_topic_index: int,
        module_title: str = "",
        sub_topic_title: str = "",
        total_sub_topics: int = 0,
    ) -> TeachingState:
        """
        Advance to a new sub-topic/module.  Called by the server after loading
        the next topic's content.  Resets segment tracking.
        """
        state = self.get_session(session_id)
        if not state:
            return None

        state.module_index = module_index
        state.sub_topic_index = sub_topic_index
        state.module_title = module_title
        state.sub_topic_title = sub_topic_title
        state.topic_marked_complete = False  # Reset for new topic
        if total_sub_topics:
            state.total_sub_topics = total_sub_topics
        # Reset segment state — set_content() will fill these in
        state.content_segments = []
        state.current_segment_index = 0
        state.total_segments = 0
        state.interrupted_text = ""
        state.teaching_content = ""
        state.raw_content = ""
        self._transition(state, TeachingPhase.TEACHING)
        logger.info(
            f"⏭️ Advanced to module {module_index}, topic {sub_topic_index}"
            f" ({module_title} → {sub_topic_title})"
        )
        return state

    def cleanup(self, session_id: str):
        """Remove session from memory and Redis."""
        self.sessions.pop(session_id, None)
        if self.redis_client:
            try:
                self.redis_client.delete(f"{self._redis_prefix}{session_id}")
            except Exception:
                pass
        logger.info(f"🧹 Session cleaned up: {session_id}")

    # --- Internal helpers ---

    def _compute_next_topic(self, state: TeachingState) -> Optional[Dict[str, int]]:
        """
        Determine the next sub-topic/module indices.

        Returns {"module_index": int, "sub_topic_index": int} or None if
        the entire course is complete.
        """
        mi = state.module_index
        si = state.sub_topic_index

        # Next sub-topic in same module?
        if si + 1 < state.total_sub_topics:
            return {"module_index": mi, "sub_topic_index": si + 1}

        # Next module?
        if mi + 1 < state.total_modules:
            return {"module_index": mi + 1, "sub_topic_index": 0}

        # Course complete
        return None

    def _current_segment_text(self, state: TeachingState) -> Optional[str]:
        """Get text for current segment.  Returns None when all segments are done."""
        if not state.content_segments:
            return state.teaching_content  # Fallback: whole content
        if state.current_segment_index >= len(state.content_segments):
            return None  # All segments delivered
        return state.content_segments[state.current_segment_index]

    def _transition(self, state: TeachingState, new_phase: TeachingPhase):
        """Transition teaching phase."""
        old = state.phase
        state.previous_phase = old
        state.phase = new_phase.value
        state.last_interaction_at = datetime.utcnow().isoformat()
        self._persist(state)
        logger.debug(f"🔄 Phase: {old} → {new_phase.value}")

    def _persist(self, state: TeachingState):
        """Persist state to Redis (non-blocking, best-effort)."""
        if not self.redis_client:
            return
        try:
            key = f"{self._redis_prefix}{state.session_id}"
            # Don't persist large content fields to Redis
            data = state.to_dict()
            data.pop("content_segments", None)  # Too large
            data.pop("teaching_content", None)
            data.pop("raw_content", None)
            # Keep interrupted_text (small, needed for resume across reconnects)
            self.redis_client.setex(key, 1800, json.dumps(data))
        except Exception as e:
            logger.debug(f"Redis persist error (non-critical): {e}")

    def _load(self, session_id: str) -> Optional[TeachingState]:
        """Load state from Redis."""
        if not self.redis_client:
            return None
        try:
            key = f"{self._redis_prefix}{session_id}"
            data = self.redis_client.get(key)
            if data:
                return TeachingState.from_dict(json.loads(data))
        except Exception as e:
            logger.debug(f"Redis load error (non-critical): {e}")
        return None

    # =================================================================
    # TIER 2: LangGraph Integration (Pedagogical LLM Responses)
    # =================================================================

    def generate_teaching_content_with_llm(self, session_id: str) -> Optional[str]:
        """
        Use LangGraph's teach_content node to generate pedagogical teaching
        content from raw content. Returns enhanced content or None on failure.
        
        Call this AFTER set_content() for higher-quality TTS delivery.
        Falls back to raw content if LangGraph is unavailable.
        """
        global _langgraph_available
        if not _langgraph_available:
            _try_import_langgraph()
        if not _langgraph_available:
            return None

        state = self.get_session(session_id)
        if not state or not state.raw_content:
            return None

        try:
            from services.langgraph_teaching_agent import teach_content as lg_teach

            # Build a minimal LangGraph TeachingState dict for the node
            lg_state = {
                "messages": [],
                "session_id": state.session_id,
                "user_id": state.user_id,
                "user_name": state.user_name,
                "course_id": state.course_id,
                "module_index": state.module_index,
                "sub_topic_index": state.sub_topic_index,
                "current_segment": state.current_segment_index,
                "total_segments": state.total_segments,
                "teaching_content": state.raw_content,
                "questions_asked": state.questions_asked,
                "interruptions": state.interruptions,
                "current_intent": None,
                "last_user_input": None,
                "is_teaching": True,
                "waiting_for_continue": False,
            }

            t0 = time.time()
            result_state = lg_teach(lg_state)
            elapsed_ms = (time.time() - t0) * 1000

            # Extract the AI message content
            messages = result_state.get("messages", [])
            if messages:
                from langchain_core.messages import AIMessage
                ai_msgs = [m for m in messages if isinstance(m, AIMessage)]
                if ai_msgs:
                    content = ai_msgs[-1].content
                    logger.info(
                        f"✅ LangGraph teach_content: {len(content)} chars in {elapsed_ms:.0f}ms"
                    )
                    return content

        except Exception as e:
            logger.warning(f"⚠️ LangGraph teach_content failed: {e}")

        return None

    def answer_question_with_llm(
        self, session_id: str, question: str,
        conversation_context: list = None
    ) -> Optional[str]:
        """
        Use LangGraph's answer_question node for pedagogical Q&A.
        Uses conversation context + course content for contextual answers.
        Returns answer text or None on failure.
        """
        global _langgraph_available
        if not _langgraph_available:
            _try_import_langgraph()
        if not _langgraph_available:
            return None

        state = self.get_session(session_id)
        if not state:
            return None

        try:
            from services.langgraph_teaching_agent import answer_question as lg_answer
            from langchain_core.messages import HumanMessage

            # Build messages with conversation context for relevance
            msgs = []
            if conversation_context:
                for entry in conversation_context:
                    if entry.get('role') == 'user':
                        msgs.append(HumanMessage(content=entry['content']))
                    else:
                        from langchain_core.messages import AIMessage as _AI
                        msgs.append(_AI(content=entry['content']))
            msgs.append(HumanMessage(content=question))

            lg_state = {
                "messages": msgs,
                "session_id": state.session_id,
                "user_id": state.user_id,
                "user_name": state.user_name,
                "course_id": state.course_id,
                "module_index": state.module_index,
                "sub_topic_index": state.sub_topic_index,
                "current_segment": state.current_segment_index,
                "total_segments": state.total_segments,
                "teaching_content": state.raw_content or state.teaching_content,
                "questions_asked": state.questions_asked,
                "interruptions": state.interruptions,
                "current_intent": "question",
                "last_user_input": question,
                "is_teaching": False,
                "waiting_for_continue": False,
            }

            t0 = time.time()
            result_state = lg_answer(lg_state)
            elapsed_ms = (time.time() - t0) * 1000

            messages = result_state.get("messages", [])
            if messages:
                from langchain_core.messages import AIMessage
                ai_msgs = [m for m in messages if isinstance(m, AIMessage)]
                if ai_msgs:
                    answer = ai_msgs[-1].content
                    logger.info(
                        f"✅ LangGraph answer_question: {len(answer)} chars in {elapsed_ms:.0f}ms"
                    )
                    return answer

        except Exception as e:
            logger.warning(f"⚠️ LangGraph answer_question failed: {e}")

        return None

    @property
    def langgraph_available(self) -> bool:
        """Check if LangGraph Tier 2 is available."""
        global _langgraph_available
        if not _langgraph_available:
            _try_import_langgraph()
        return _langgraph_available
