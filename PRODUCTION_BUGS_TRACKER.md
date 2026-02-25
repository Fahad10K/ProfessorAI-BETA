# ProfessorAI — Production Bug Tracker & Intent Analysis

> Created: 2026-02-25 | Status: IN PROGRESS

---

## Bug 1: Voice IDs Not Working (Persona voice_id ignored)

**Symptom:** Logs always show `voice=EXAVITQu...` (Prof Sarah) regardless of which persona the user selects.

**Root Cause Analysis:**
- `handle_interactive_teaching` resolves `persona_id` → `voice_id` correctly and stores it in `teaching_session['voice_id']`.
- All TTS calls (`_stream_teaching_content`, `_stream_answer_response`, `_stream_filler_tts`) pass `voice_id=self.teaching_session.get('voice_id')`.
- `audio_service.stream_audio_from_text` passes `voice_id` to `elevenlabs_service.text_to_speech_stream`.
- `elevenlabs_service.text_to_speech_stream` uses `effective_voice = voice_id or self.voice_id`.
- **BUT** `chat_with_audio` handler at line 533 does NOT pass `voice_id` at all:
  ```python
  async for audio_chunk in self.audio_service.stream_audio_from_text(response_text, language, self.websocket):
  ```
  This means chat-with-audio always uses the default voice.
- For interactive teaching, the voice_id flow looks correct. The log `voice=EXAVITQu...` in the user's logs is from Sarah which IS the default persona selected. **Need to verify the client is actually sending a different persona_id.**
- **Action:** Ensure `voice_id` is passed in `chat_with_audio` handler. Also add logging to confirm which persona_id was received from client.

**Fix Applied:**
- Added persona resolution (`persona_id` → `voice_id`) to `handle_chat_with_audio` in `websocket_server.py`
- `chat_voice_id` is now passed to `audio_service.stream_audio_from_text(..., voice_id=chat_voice_id)`
- Added logging to confirm which persona/voice is being used
- Interactive teaching already had correct voice_id passthrough (verified)

**Status:** ✅ FIXED

---

## Bug 2: Chat-with-Audio Not Interactive / Pedagogical

**Symptom:** Chat-with-audio is a one-shot Q&A — user asks, gets answer, done. No follow-up questions, no pedagogical engagement.

**Root Cause:** `handle_chat_with_audio` calls `chat_service.ask_question()` which returns a single answer. There's no prompt engineering to make the response pedagogical (ask follow-up Qs, check understanding, offer to explore further).

**Fix Applied:**
1. Added `pedagogical: bool = False` parameter to `chat_service.ask_question()` and `llm_service.get_general_response()`
2. When `pedagogical=True`, system prompt gets appended with PEDAGOGICAL ENGAGEMENT instructions:
   - End with ONE follow-up question or invitation to explore further
   - Natural conversational style like a real teacher
3. `handle_chat_with_audio` now passes `pedagogical=True` to `ask_question()`
4. All general LLM routes in `chat_service` propagate the flag via `self._pedagogical`

**Status:** ✅ FIXED

---

## Bug 3: Recommendation Service Initialized But Never Used

**Symptom:** Logs show `RecommendationService initialized` but recommendations are only fetched at `end_teaching`. They're never used proactively during teaching or in chat-with-audio.

**Current Usage:**
- `handle_end_teaching()` — fetches recommendations and sends with `teaching_ended` payload ✅
- `app_celery.py` — REST endpoint `/api/recommendations/{user_id}` ✅
- **Missing:** Not used during interactive teaching (e.g., after marking complete, suggest next topic/quiz).
- **Missing:** Not used in chat-with-audio to proactively suggest courses/quizzes.

**Fix Applied:**
1. Added `_send_recommendations_if_available()` method to `websocket_server.py`
   - Fetches recommendations via `RecommendationService.get_recommendations(user_id)` in executor (non-blocking)
   - Sends `{type: "recommendations", next_topics, recommended_quizzes, next_courses, summary}` to client
2. Called after `_handle_mark_complete()` succeeds — student sees what to study next
3. Best-effort: failures are logged but don't break the flow

**Status:** ✅ FIXED

---

## Bug 4: Missing Teaching-Mode vs Query-Resolution-Mode Flag

**Symptom:** No clear demarcation between "teaching from course content" mode and "resolving user query during barge-in" mode. This matters for:
- TTS audio type (teaching_audio_chunk vs answer_audio_chunk)
- UI behavior (topic banner vs Q&A mode)
- Orchestrator state management
- What happens after query resolution (should auto-resume teaching)

**Current State:**
- `TeachingPhase` enum has `TEACHING`, `PAUSED_FOR_QUERY`, `ANSWERING`, `WAITING_RESUME` — these conceptually cover it.
- But the WebSocket server doesn't track this cleanly in `teaching_session`.
- The client doesn't know which mode the server is in.

**Fix Applied:**
1. `teaching_session['mode']` initialized as `'course_teaching'` at session start
2. Mode transitions:
   - Barge-in confirmed → `'query_resolution'` (sent in `user_interrupt_detected` event)
   - `continue_teaching` / `repeat` / `advance_next_topic` → `'course_teaching'` (sent in events)
   - `answer_with_rag` / `answer_general` → `'query_resolution'`
   - `handle_continue_teaching` → `'course_teaching'`
3. All relevant WebSocket events include `"mode"` field so client can adjust UI

**Status:** ✅ FIXED

---

## Bug 5: Chat APIs Always Use RAG (Slow for Generic Queries)

**Symptom:** From logs — "What is machine learning?" gets routed as `course_query` with `confidence: 0.46` and goes through full RAG pipeline (2-5s). Generic queries should use direct LLM (< 1s).

**Root Cause:** The `semantic_router_service.classify_intent()` has low confidence (0.46) but still routes to `course_query`. The chat service already has routing logic (greeting → fast, general_question → LLM, course_query → RAG), but the semantic router's thresholds may be too aggressive toward RAG.

**Current Flow:**
1. `semantic_router.classify_intent(query)` → returns `{route_name, should_use_rag, confidence}`
2. Chat service routes based on `route_name`
3. If `course_query` + `course_id` provided → validates with `is_query_course_specific()`
4. But without `course_id`, ALL course_query routes go to RAG regardless of confidence

**Fix Applied:**
1. `semantic_router_service.classify_intent()`: Fixed hardcoded `confidence: 0.8` — now uses real `route_choice.similarity_score`
2. Added threshold: `should_use_rag = (route_name == "course_query") and confidence >= 0.55`
   - Low-confidence course_query routes (`< 0.55`) get `should_use_rag=False`
3. `chat_service.ask_question()`: Added early exit for low-confidence course_query
   - Routes to general LLM instead of RAG → saves 2-5s latency
   - Logged as `course_query_low_confidence` route for analytics

**Status:** ✅ FIXED

---

## Priority Order
1. **Bug 1** — Voice ID fix (quick win, high visibility)
2. **Bug 4** — Mode flag (architectural, enables other fixes)
3. **Bug 5** — Smart routing (latency improvement)
4. **Bug 3** — Recommendations integration
5. **Bug 2** — Pedagogical chat (prompt engineering)
