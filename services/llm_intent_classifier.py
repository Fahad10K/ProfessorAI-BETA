"""
LLM-based Navigation Intent Classifier (Tier 1.5)

Called when keyword-based Tier 1 returns a navigation intent (select_course,
check_progress, etc.) to get accurate course name extraction and intent
disambiguation.  Uses Groq llama-3.1-8b-instant for <500ms latency.

Flow:
  Tier 1 (keyword, <1ms) → navigation intent detected
  → Tier 1.5 (this module, ~300ms) → accurate intent + extracted params
  → Handler in websocket_server.py acts on the result
"""

import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List

import config

logger = logging.getLogger(__name__)

# ── Groq client (lazy singleton) ─────────────────────────────────────────────
_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=config.GROQ_API_KEY)
            logger.info("✅ Groq client initialized for LLM intent classifier")
        except Exception as e:
            logger.warning(f"⚠️ Groq client init failed: {e}")
    return _groq_client


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a navigation intent classifier for an AI teaching platform.
Given the user's message and available courses, return a JSON object.

INTENTS (pick exactly one):
- select_course       : user wants to start/switch to a specific course
- select_course_resume: user wants to resume a specific course from where they left off
- check_progress      : user wants to see progress (optionally for a specific course)
- list_courses        : user wants to see available courses
- list_modules        : user wants to see modules in current/specified course
- list_topics         : user wants to see topics in a module
- resume_session      : user wants to continue from where they left off (no specific course)
- previous_course     : user wants to go back to the previous course
- next_course         : user wants to move to the next course
- select_module       : user wants to jump to a specific module (by number)
- select_topic        : user wants to jump to a specific topic (by number)
- correction          : user is correcting a misunderstanding (e.g. "no, I said...")
- question            : user is asking a question, not navigating
- unknown             : cannot determine intent

RULES:
1. Match course names FUZZILY — STT often mis-transcribes. "accountancy part one and two" = "Accountancy Part I And II". "generetiv AI" = "Generative AI Handson".
2. Numbers like "one", "two", "1", "2" in user text may be PART OF A COURSE NAME, not a course selection number. Only set course_number when the user clearly means "course number X" (e.g. "start course 3", "course number five").
3. If the user mentions a course name (even partially), set course_name to the EXACT matching course name from the list.
4. For "correction" intent: if user says "no, I asked for X" or "I meant X", extract what they actually want.
5. For check_progress with a specific course, set course_name.
6. Return ONLY valid JSON, no markdown, no explanation.

RESPONSE FORMAT (JSON):
{
  "intent": "<intent_string>",
  "course_name": "<exact course name from list or null>",
  "course_number": <integer or null>,
  "module_number": <integer or null>,
  "topic_number": <integer or null>,
  "confidence": <float 0-1>
}"""


# ── Public API ────────────────────────────────────────────────────────────────

async def classify_navigation_intent(
    user_input: str,
    course_names: List[str],
    current_course: str = "",
    timeout: float = 3.0,
) -> Optional[Dict[str, Any]]:
    """
    Classify a navigation intent using Groq LLM.

    Args:
        user_input:    Raw transcribed text from the user.
        course_names:  List of available course titles.
        current_course: Currently active course title (for context).
        timeout:       Max seconds to wait for response.

    Returns:
        Dict with intent, course_name, course_number, etc. or None on failure.
    """
    client = _get_groq_client()
    if not client:
        logger.warning("⚠️ Groq client not available, skipping LLM classification")
        return None

    t0 = time.time()

    # Build user message with course list context
    numbered_courses = "\n".join(
        f"  {i+1}. {name}" for i, name in enumerate(course_names)
    )
    user_msg = (
        f"Available courses:\n{numbered_courses}\n\n"
        f"Currently teaching: {current_course or 'none'}\n\n"
        f"User said: \"{user_input}\""
    )

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )),
            timeout=timeout,
        )

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        elapsed = (time.time() - t0) * 1000
        logger.info(
            f"🤖 LLM intent: {result.get('intent')} "
            f"course={result.get('course_name')} "
            f"num={result.get('course_number')} "
            f"conf={result.get('confidence', '?')} "
            f"in {elapsed:.0f}ms"
        )
        return result

    except asyncio.TimeoutError:
        logger.warning(f"⏰ LLM intent classifier timed out after {timeout}s")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ LLM intent classifier returned invalid JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ LLM intent classifier error: {e}")
        return None


# ── Quiz-choice classifier ───────────────────────────────────────────────────

_QUIZ_CHOICE_SYSTEM = """\
You classify a student's response to:
"Should I ask you a few quick questions to test your understanding, or move ahead?"

Return ONLY a JSON object:
{"choice": "take_quiz" | "skip_quiz", "confidence": 0.0-1.0}

RULES:
- "take_quiz" = user wants questions / testing / quiz (e.g. "yes", "test me", "sure ask away", "go ahead ask", "quiz me", "let's do it")
- "skip_quiz" = user wants to skip and move on (e.g. "no", "move ahead", "skip", "let's just continue", "next topic", "move on")
- If truly ambiguous, lean toward "take_quiz" with low confidence.
- Return ONLY valid JSON."""


async def classify_quiz_choice(
    user_input: str,
    topic_title: str = "",
    timeout: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """
    Use Groq LLM to classify whether the user wants to take the quiz or skip it.

    Returns {"choice": "take_quiz"|"skip_quiz", "confidence": float} or None.
    """
    client = _get_groq_client()
    if not client:
        return None

    t0 = time.time()
    user_msg = f'Topic: "{topic_title}"\nStudent said: "{user_input}"'

    try:
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": _QUIZ_CHOICE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
                max_tokens=60,
                response_format={"type": "json_object"},
            )),
            timeout=timeout,
        )

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        elapsed = (time.time() - t0) * 1000
        logger.info(
            f"🤖 Quiz choice LLM: {result.get('choice')} "
            f"conf={result.get('confidence', '?')} in {elapsed:.0f}ms"
        )
        return result

    except asyncio.TimeoutError:
        logger.warning(f"⏰ Quiz choice classifier timed out after {timeout}s")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Quiz choice classifier invalid JSON: {e}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Quiz choice classifier error: {e}")
        return None
