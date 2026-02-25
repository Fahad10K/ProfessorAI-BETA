# ProfessorAI — Comprehensive System Analysis, Bug Report & Fix Tracker

> **Author:** AI Engineering Audit  
> **Date:** 2026-02-25  
> **Scope:** Full-stack analysis of the ProfessorAI real-time teaching platform  
> **Goal:** Production-grade, industry-standard quality

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 System Components

| Component | Technology | Role |
|-----------|-----------|------|
| **WebSocket Server** | `websockets` (Python) | Real-time bidirectional communication hub |
| **REST API** | FastAPI (`app_celery.py`) | CRUD, uploads, quiz, recommendations |
| **STT** | Deepgram Nova-3 / Flux v2 | Real-time speech-to-text via WebSocket |
| **TTS** | ElevenLabs (SDK → WS → REST → Edge) | Multi-voice text-to-speech streaming |
| **LLM** | OpenAI GPT-4o-mini (chat), Groq Llama-3.1 (RAG) | Response generation |
| **RAG** | ChromaDB Cloud + Hybrid BM25 + Cross-Encoder Reranker | Course-specific Q&A |
| **Orchestrator** | `RealtimeOrchestrator` (custom state machine) | Intent classification, session management |
| **LangGraph** | Optional Tier-2 pedagogical agent | Enhanced teaching content + Q&A |
| **Database** | Neon PostgreSQL | Users, courses, progress, sessions, messages |
| **Cache** | Redis | Session caching, Celery broker |
| **Frontend** | Vanilla HTML/JS clients | Interactive teaching + Chat-with-audio |

### 1.2 Core Data Flows

**Interactive Teaching Flow:**
```
Client → start_class_interactive → Load course from DB/JSON → Init Orchestrator session
→ Init Deepgram STT → Start STT listener task → Stream teaching audio (TTS)
→ User speaks → Deepgram partial/final → Orchestrator classifies intent (<5ms)
→ Route action (continue/pause/repeat/question/advance/mark_complete/next_course)
→ Execute action (stream teaching / answer pipeline / mark progress)
```

**Chat-with-Audio Flow:**
```
Client → chat_with_audio → Semantic Router classifies intent
→ Route: greeting (instant) | general_question (LLM) | course_query (RAG)
→ Get text response → Stream TTS audio chunks to client
```

**Answer Pipeline (during teaching barge-in):**
```
User interrupts → Barge-in detected → Cancel current TTS
→ Send filler TTS ("Let me think...") IN PARALLEL with LLM generation
→ LLM tiers: LangGraph → RAG → General LLM → Fallback
→ Stream answer TTS → Resume prompt → Wait for "continue"
```

---

## 2. FUNCTIONALITY-BY-FUNCTIONALITY ANALYSIS

### 2.1 Interactive Teaching Session Lifecycle

**States:** IDLE → INITIALIZING → TEACHING → PAUSED_FOR_QUERY → ANSWERING → WAITING_RESUME → PENDING_CONFIRMATION → COMPLETED

**Scenarios analyzed:**
- Normal teaching flow (start → segments → auto-advance)
- Barge-in mid-sentence → answer → resume
- Mark complete → confirmation → next topic
- Next course → confirmation → load new course
- Compound: mark complete + next course
- Session end (explicit farewell)
- STT noise filtering
- Content segmentation and resumable delivery

### 2.2 Chat-with-Audio

**Scenarios analyzed:**
- Simple greeting → instant response
- General question → LLM (no RAG)
- Course-specific question → RAG pipeline
- Low-confidence routing → bypass RAG
- Barge-in during audio playback
- Pedagogical follow-up questions

### 2.3 Audio Pipeline

**Scenarios analyzed:**
- ElevenLabs SDK streaming (primary)
- WebSocket fallback
- REST fallback
- Edge TTS fallback (free)
- Sarvam fallback (non-English)
- Audio chunk accumulation (16KB min)
- Multi-voice persona support

---

## 3. IDENTIFIED BUGS, GAPS & EDGE CASES

### CRITICAL BUGS (Will cause failures or incorrect behavior)

#### BUG-C1: `cleanup()` does not stop STT service or cancel background tasks
**File:** `websocket_server.py:2905-2915`  
**Scenario:** Client disconnects unexpectedly (browser close, network drop).  
**Impact:** Deepgram STT WebSocket stays open (resource leak). Background TTS/answer tasks continue executing and try to send to closed WebSocket → ConnectionClosed exceptions flood logs. The `_handle_teaching_interruptions` task keeps running.  
**Fix:** Cleanup must stop STT, cancel all tasks, clear teaching_session.

#### BUG-C2: `handle_end_teaching` calls `rec_service.get_recommendations()` synchronously on event loop
**File:** `websocket_server.py:2512`  
**Scenario:** Teaching session ends.  
**Impact:** `RecommendationService.get_recommendations()` uses `self.db` which does synchronous psycopg2 queries. Calling it directly on the asyncio event loop blocks the entire server for all clients during the DB query (~50-200ms). This is a concurrency killer.  
**Fix:** Wrap in `run_in_executor()` like `_send_recommendations_if_available` does.

#### BUG-C3: `_run_action` closure captures stale `self.teaching_session` references
**File:** `websocket_server.py:1377-1462` and `2370-2430`  
**Scenario:** User sends "mark complete", then immediately sends "next course" before first action completes.  
**Impact:** Both actions are created as background tasks. The second `_run_action` cancels `current_answer_task` (the first), but both closures reference `self.teaching_session` dict directly. If the first task modifies `teaching_session` (e.g., module_index) after the second reads it, we get race conditions. The `current_answer_task` field is set but the old task may still be running briefly.  
**Fix:** Add a serial execution guard — queue actions instead of firing concurrent tasks.

#### BUG-C4: `_stream_answer_response` saves to DB synchronously via `session_manager.add_message`
**File:** `websocket_server.py:2121`  
**Scenario:** Every answer response during interactive teaching.  
**Impact:** `add_message` does a synchronous DB INSERT + Redis update on the asyncio event loop. Blocks server for ~20-50ms per message.  
**Fix:** Wrap in `run_in_executor()`.

#### BUG-C5: `handle_teaching_user_input` saves to DB synchronously
**File:** `websocket_server.py:2353`  
**Scenario:** User sends text input via button (mark complete, yes, no).  
**Impact:** Same as C4 — synchronous DB call on event loop.  
**Fix:** Wrap in `run_in_executor()`.

#### BUG-C6: `_on_teaching_tts_done` callback accesses `self.teaching_session` without None check on inner keys
**File:** `websocket_server.py:2075-2084`  
**Scenario:** Teaching session ends (`handle_end_teaching` sets `self.teaching_session = None`), then the TTS callback fires.  
**Impact:** `self.teaching_session['is_teaching'] = False` on line 2080/2083 will raise `TypeError: 'NoneType' object does not support item assignment` — but only if the task was cancelled or errored AFTER session cleanup.  
**Fix:** Check `if self.teaching_session:` before accessing keys in the error/cancel branches.

#### BUG-C7: Duplicate `_run_action` definition — text-input version missing mode transitions
**File:** `websocket_server.py:2370-2430` (handle_teaching_user_input's _run_action)  
**Scenario:** User clicks "continue" button via text input path.  
**Impact:** This copy of `_run_action` does NOT set `teaching_session['mode'] = 'course_teaching'` for continue/repeat/advance actions, unlike the STT version (lines 1395-1446). This means mode will stay as `query_resolution` after a text-based resume.  
**Fix:** Sync both `_run_action` implementations or extract to a shared method.

### HIGH-PRIORITY BUGS (Degraded experience)

#### BUG-H1: `audio_only` handler does not pass `voice_id`
**File:** `websocket_server.py:2567`  
**Scenario:** Client requests audio-only generation.  
**Impact:** Always uses default voice, ignoring any persona selection.  
**Fix:** Accept and pass `voice_id` parameter.

#### BUG-H2: No heartbeat/timeout for teaching sessions
**File:** `websocket_server.py` (global)  
**Scenario:** User walks away mid-session. Browser stays open but user is AFK.  
**Impact:** Deepgram STT WebSocket stays open indefinitely (billed per minute). Teaching session resources are never freed. Server accumulates zombie sessions.  
**Fix:** Add idle timeout — if no STT events for N minutes, auto-pause or end session.

#### BUG-H3: `_handle_next_course` doesn't update `orch_state.course_id` atomically
**File:** `websocket_server.py:1870`  
**Scenario:** User says "next course" and then immediately asks a question before course loads.  
**Impact:** `orch_state.course_id` is updated AFTER content loading + streaming starts. During the gap, a barge-in question would use the OLD course_id for RAG, returning irrelevant results.  
**Fix:** Update course_id immediately before content loading.

#### BUG-H4: `classify_intent` treats "done" as FAREWELL, ending the session
**File:** `realtime_orchestrator.py:236` (`_FAREWELL_KW`)  
**Scenario:** User says "I'm done with this topic" or "done learning this".  
**Impact:** "done" is in `_FAREWELL_KW`, so any sentence containing "done" could trigger session end instead of mark-complete or advance. "I'm done with this" overlaps with `_MARK_COMPLETE_KW` ("i am done with this") but only exact substring match — "I'm done" won't match "i am done with this".  
**Fix:** Remove "done" from farewell or add more specific checks. Add "I'm done with this" to mark-complete keywords.

#### BUG-H5: `needs_rag()` overlap detection is too aggressive
**File:** `realtime_orchestrator.py:331-378`  
**Scenario:** Teaching content mentions "machine" and "learning". User asks "How does a washing machine work?"  
**Impact:** "machine" overlaps with teaching content → routed to RAG unnecessarily. The overlap-based heuristic has no minimum threshold — even 1 word overlap triggers RAG.  
**Fix:** Require at least 2 overlapping content words to trigger RAG.

#### BUG-H6: `_stream_teaching_content` creates task but caller doesn't always await
**File:** `websocket_server.py:2070-2073`  
**Scenario:** `handle_interactive_teaching` calls `_stream_teaching_content` at line 1215. This creates a task and returns immediately.  
**Impact:** The `handle_interactive_teaching` method returns to the message processing loop while teaching audio streams in the background. This is actually BY DESIGN for barge-in support. However, if the teaching content fails (e.g., TTS error), the error is swallowed in the callback and the client gets no notification that teaching didn't start.  
**Fix:** Add error notification in `_on_teaching_tts_done` callback when exception occurs.

#### BUG-H7: `_create_simple_teaching_content` truncates to 3 paragraphs silently
**File:** `websocket_server.py:2260`  
**Scenario:** Long topic with 10+ paragraphs of content.  
**Impact:** Only first 3 paragraphs delivered. User never hears the rest. No indication content was truncated.  
**Fix:** Remove paragraph limit or increase significantly. The segmenter handles chunking.

#### BUG-H8: `_send_recommendations_if_available` creates new `RecommendationService()` every call
**File:** `websocket_server.py:1778-1779`  
**Scenario:** User marks multiple topics complete in quick succession.  
**Impact:** Each call creates a new `RecommendationService` → new `DatabaseServiceV2` connection. Under load, this could exhaust DB connection pool.  
**Fix:** Use the shared `self.database_service` or cache the recommendation service.

### MEDIUM-PRIORITY GAPS (Missing features for production)

#### GAP-M1: No rate limiting on WebSocket messages
**Scenario:** Malicious client sends thousands of `chat_with_audio` messages per second.  
**Impact:** Server overwhelmed. LLM API rate limits hit. Potential cost explosion.  
**Fix:** Add per-client rate limiting in `process_messages()`.

#### GAP-M2: No authentication/authorization on WebSocket
**Scenario:** Anyone can connect and use the service.  
**Impact:** Unauthorized access, cost exposure, data leakage.  
**Fix:** Validate JWT/session token on WebSocket connection.

#### GAP-M3: No graceful shutdown handling
**Scenario:** Server process killed (deployment, restart).  
**Impact:** All active teaching sessions lost. No notification to clients. Deepgram connections leak.  
**Fix:** Add signal handlers that close all sessions gracefully.

#### GAP-M4: `handle_chat_with_audio` doesn't track `conversation_context` across requests
**Scenario:** User asks follow-up in chat-with-audio: "Tell me more about that."  
**Impact:** Conversation history is fetched from DB, but DB saving happens AFTER text response. For rapid follow-ups, the previous exchange may not be in DB yet. Redis cache helps but has a race window.  
**Fix:** Maintain an in-memory conversation buffer per connection (like teaching_session does).

#### GAP-M5: Teaching session not recoverable after WebSocket reconnect
**Scenario:** User's connection drops and they reconnect.  
**Impact:** Teaching session is lost. User must restart from scratch.  
**Fix:** Persist session to Redis (already partially done). Add reconnect handler that restores session state.

#### GAP-M6: No client-side `mode` handling
**Scenario:** Server sends `mode: "query_resolution"` in events.  
**Impact:** Client HTML doesn't read or use the `mode` field to adjust UI.  
**Fix:** Add client-side mode handling (show different indicators for teaching vs Q&A).

#### GAP-M7: `cleanup_expired_sessions` is a TODO stub
**File:** `session_manager.py:228-232`  
**Impact:** Old sessions accumulate forever in the database.  
**Fix:** Implement the cleanup query.

### LOW-PRIORITY EDGE CASES

#### EDGE-L1: User says "yes" when NOT in confirmation flow
**Scenario:** Teaching is active. User says "yes I understand" or "yes that makes sense."  
**Impact:** "yes" matches `_CONTINUE_KW` (as it should), so this is handled correctly. But if pending_confirmation is True from a stale state, it would be misrouted. Currently mitigated by clearing pending_action after processing.

#### EDGE-L2: Concurrent WebSocket connections from same user
**Scenario:** User opens two browser tabs.  
**Impact:** Two `ProfAIAgent` instances with same `user_id`. Session manager returns the same session_id. Both write to the same conversation history. Teaching sessions could conflict.  
**Fix:** Detect duplicate connections and close the old one, or prevent concurrent teaching sessions.

#### EDGE-L3: Very long user utterances from STT
**Scenario:** User speaks for 30+ seconds without pause.  
**Impact:** Deepgram may emit very long transcripts. `classify_intent` checks all keyword sets against the full text. A long question containing "continue" somewhere would be misclassified as CONTINUE instead of QUESTION.  
**Fix:** For long inputs (>15 words), skip short-phrase intent keywords and prioritize question detection.

#### EDGE-L4: Language switching mid-session
**Scenario:** User starts in English, then speaks Hindi.  
**Impact:** Deepgram STT is initialized with fixed language hint. TTS voice may not support the new language. Teaching content is in the original language.  
**Fix:** Document this as unsupported, or add language detection + dynamic switching.

---

## 4. FIX IMPLEMENTATION PLAN

| ID | Priority | Status | Description |
|----|----------|--------|-------------|
| BUG-C1 | CRITICAL | ✅ FIXED | cleanup() now stops STT + cancels tasks |
| BUG-C2 | CRITICAL | ✅ FIXED | Async wrap recommendation fetch in handle_end_teaching |
| BUG-C3 | CRITICAL | ✅ FIXED | Unified _dispatch_action prevents races |
| BUG-C4 | CRITICAL | ✅ FIXED | Async wrap DB save in _stream_answer_response |
| BUG-C5 | CRITICAL | ✅ FIXED | Async wrap DB save in handle_teaching_user_input |
| BUG-C6 | CRITICAL | ✅ FIXED | Null-safe callback in _on_teaching_tts_done |
| BUG-C7 | CRITICAL | ✅ FIXED | Unified _dispatch_action with mode transitions |
| BUG-H1 | HIGH | ✅ FIXED | Pass voice_id in audio_only handler |
| BUG-H2 | HIGH | ✅ FIXED | Idle timeout (5min warn, 10min auto-pause) |
| BUG-H3 | HIGH | ✅ FIXED | Update course_id before content load |
| BUG-H4 | HIGH | ✅ FIXED | "done" moved to mark-complete, farewell cleaned |
| BUG-H5 | HIGH | ✅ FIXED | Require 2+ word overlap for RAG trigger |
| BUG-H6 | HIGH | ✅ FIXED | Error notification in TTS callback |
| BUG-H7 | HIGH | ✅ FIXED | Removed 3-paragraph truncation limit |
| BUG-H8 | HIGH | ✅ FIXED | Cached RecommendationService instance |
| GAP-M1 | MEDIUM | ⏳ NOTED | Rate limiting (future sprint) |
| GAP-M2 | MEDIUM | ⏳ NOTED | Authentication (future sprint) |
| GAP-M3 | MEDIUM | ⏳ NOTED | Graceful shutdown (future sprint) |
| GAP-M4 | MEDIUM | ⏳ NOTED | In-memory conversation buffer (future sprint) |
| GAP-M5 | MEDIUM | ⏳ NOTED | Session recovery on reconnect (future sprint) |
| GAP-M6 | MEDIUM | ⏳ NOTED | Client-side mode handling (future sprint) |
| GAP-M7 | MEDIUM | ⏳ NOTED | Session cleanup cron (future sprint) |
| EDGE-L1 | LOW | ✅ OK | Yes during non-confirmation (already handled) |
| EDGE-L2 | LOW | ⏳ NOTED | Concurrent connections (future sprint) |
| EDGE-L3 | LOW | ✅ FIXED | Long utterance (>15 words) defaults to QUESTION |
| EDGE-L4 | LOW | ⏳ NOTED | Language switching (unsupported, documented) |

---

## 5. FIX DETAILS

### BUG-C1: cleanup() Resource Leak
**File:** `websocket_server.py` — `cleanup()` method  
**Fix:** Added full resource cleanup:
- Cancel `current_answer_task` and `current_tts_task` if running
- Close Deepgram STT WebSocket via `stt_service.close()`
- Cleanup orchestrator session
- Set `teaching_session = None`

### BUG-C2: Synchronous Recommendation Fetch Blocks Event Loop
**File:** `websocket_server.py` — `handle_end_teaching()`  
**Fix:** Wrapped `rec_service.get_recommendations()` in `asyncio.get_event_loop().run_in_executor(None, ...)` to run the synchronous DB query in a thread pool.

### BUG-C3 + BUG-C7: Duplicate _run_action With Race Conditions
**File:** `websocket_server.py`  
**Fix:** Created two shared methods:
- `_dispatch_action(act, rt, ui, tid, save_user_msg)` — single authoritative action handler with ALL mode transitions (`course_teaching`/`query_resolution`), DB save support, and proper error handling
- `_schedule_action(...)` — wraps dispatch in `asyncio.create_task` and sets `current_answer_task`
- Both the STT handler and `handle_teaching_user_input` now call `_schedule_action()` instead of defining inline closures
- **Eliminated ~130 lines of duplicate code**

### BUG-C4: Synchronous DB Save in _stream_answer_response
**File:** `websocket_server.py` — `_stream_answer_response()`  
**Fix:** Wrapped `session_manager.add_message()` in `run_in_executor()`. Variables captured before await to prevent closure issues.

### BUG-C5: Synchronous DB Save in handle_teaching_user_input
**File:** `websocket_server.py` — `handle_teaching_user_input()`  
**Fix:** Same pattern as C4 — wrapped in `run_in_executor()`.

### BUG-C6: Null-Unsafe TTS Callback
**File:** `websocket_server.py` — `_on_teaching_tts_done()`  
**Fix:** Added `if self.teaching_session:` guard before accessing `is_teaching` in both cancel and error branches. Added client error notification on TTS exception via `call_soon_threadsafe`.

### BUG-H1: audio_only Missing voice_id
**File:** `websocket_server.py` — `handle_audio_only()`  
**Fix:** Resolve `voice_id` from request data or teaching session, pass to `stream_audio_from_text()`.

### BUG-H2: No Idle Timeout
**File:** `websocket_server.py` — `_handle_teaching_interruptions()`  
**Fix:** Added idle tracking:
- `_last_real_activity` timer, reset on each `final` transcript event
- 5-minute warning: `session_idle_warning` event sent to client
- 10-minute timeout: `session_idle_timeout` event, then STT loop exits (auto-pause)
- Deepgram billing stops when STT loop ends

### BUG-H3: Race Condition in _handle_next_course
**File:** `websocket_server.py` — `_handle_next_course()`  
**Fix:** Moved `teaching_session['course_id'] = next_id` BEFORE `get_course_with_content()` so any barge-in during loading uses the correct course_id for RAG.

### BUG-H4: "done" Keyword Overlap
**File:** `realtime_orchestrator.py`  
**Fix:**
- Removed `'done'`, `'finish'`, `"that's all"` from `_FAREWELL_KW`
- Added explicit farewell phrases: `'end session'`, `'end the class'`, `'end the session'`
- Added to `_MARK_COMPLETE_KW`: `"i'm done"`, `"i'm done with this"`, `'done with this'`, `'finished with this'`, `'done with this topic'`, `"that's all for this"`

### BUG-H5: Overly Aggressive RAG Trigger
**File:** `realtime_orchestrator.py` — `needs_rag()`  
**Fix:** Changed overlap threshold from `if overlap:` (any 1 word) to `if len(overlap) >= 2` (at least 2 significant words). Prevents false positives like "machine" alone triggering RAG for unrelated questions.

### BUG-H6: Silent TTS Failure
**File:** `websocket_server.py` — `_on_teaching_tts_done()`  
**Fix:** When TTS task ends with exception, send error event to client: `"Audio streaming failed. Say 'continue' to retry."` via `call_soon_threadsafe`.

### BUG-H7: Silent Content Truncation
**File:** `websocket_server.py` — `_create_simple_teaching_content()`  
**Fix:** Removed `paragraphs[:3]` limit. All paragraphs now included. The content segmenter (`segment_content()`) handles chunking for TTS delivery.

### BUG-H8: DB Connection Pool Exhaustion
**File:** `websocket_server.py` — `_send_recommendations_if_available()`  
**Fix:** Cache `RecommendationService` instance on `self._recommendation_service` instead of creating a new one (with new DB connection) per call.

### EDGE-L3: Long Utterance Misclassification
**File:** `realtime_orchestrator.py` — `classify_intent()`  
**Fix:** Added early exit for inputs >15 words: only check multi-word intent phrases (repeat/clarify/example/summary), then default to QUESTION. Short-phrase commands like "continue", "ok", "pause" embedded in long sentences are no longer misrouted.

---

## 6. FILES MODIFIED

| File | Changes |
|------|---------|
| `websocket_server.py` | C1, C2, C3, C4, C5, C6, C7, H1, H2, H3, H6, H7, H8 |
| `services/realtime_orchestrator.py` | H4, H5, L3 |

## 7. REMAINING WORK (Future Sprints)

| ID | Description | Effort |
|----|-------------|--------|
| GAP-M1 | Per-client rate limiting on WebSocket messages | Medium |
| GAP-M2 | JWT/session token authentication on WebSocket connect | Medium |
| GAP-M3 | Graceful shutdown with signal handlers | Low |
| GAP-M4 | In-memory conversation buffer for chat-with-audio follow-ups | Low |
| GAP-M5 | Session recovery after WebSocket reconnect (Redis restore) | High |
| GAP-M6 | Client-side UI mode switching based on `mode` field | Medium |
| GAP-M7 | Cron job for expired session cleanup | Low |
| EDGE-L2 | Detect and handle duplicate WebSocket connections from same user | Medium |
| EDGE-L4 | Language detection + dynamic STT/TTS language switching | High |

---

# PHASE 2: REMAINING SERVICES ANALYSIS & FIXES

> **Date:** 2026-02-26  
> **Scope:** All services integrated via `app_celery.py` not covered in Phase 1

---

## 8. SERVICES ANALYZED (Phase 2)

| Service | File | Role |
|---------|------|------|
| **FastAPI App** | `app_celery.py` | REST API orchestrator — all endpoints |
| **TeachingService** | `services/teaching_service.py` | LLM-based teaching content generation + TTS formatting |
| **QuizService** | `services/quiz_service.py` | MCQ quiz generation, parsing, evaluation |
| **AssessmentService** | `services/assessment_service.py` | Document-based assessment generation |
| **DatabaseServiceV2** | `services/database_service_v2.py` | PostgreSQL (Neon) — courses, quizzes, sessions, progress |
| **RecommendationService** | `services/recommendation_service.py` | Personalized learning recommendations |
| **SarvamService** | `services/sarvam_service.py` | Sarvam AI TTS/STT/translation with streaming |
| **DocumentExtractor** | `services/document_extractor.py` | PDF/DOCX/TXT content extraction |
| **Celery Tasks** | `tasks/pdf_processing.py` | Background PDF → course generation |
| **Celery Config** | `celery_app.py` | Redis-backed distributed task queue |
| **DatabaseServiceActual** | `services/database_service_actual.py` | SQLAlchemy ORM for course creation |

---

## 9. PHASE 2 BUG TRACKER

| ID | Priority | Status | Component | Description |
|----|----------|--------|-----------|-------------|
| BUG-P2-C1 | CRITICAL | ✅ FIXED | app_celery.py | Blocking sync DB calls in async chat endpoints freeze event loop |
| BUG-P2-C2 | CRITICAL | ✅ FIXED | database_service_v2.py | Connection pool poisoning — closed conn returned to pool |
| BUG-P2-C3 | CRITICAL | ✅ FIXED | database_service_v2.py | `avg_score`/`best_score` were raw scores, not percentages |
| BUG-P2-C4 | CRITICAL | ✅ FIXED | database_service_v2.py | `passed_count` threshold (score≥70) wrong for variable-length quizzes |
| BUG-P2-H1 | HIGH | ✅ FIXED | app_celery.py | Unreachable code after if/elif/else chain (dead `raise HTTPException`) |
| BUG-P2-H2 | HIGH | ✅ FIXED | app_celery.py | Cursor leak in `get_all_users` — raw SQL with no try/finally on cursor |
| BUG-P2-H3 | HIGH | ✅ FIXED | app_celery.py | New `RecommendationService()` per request — DB pool exhaustion |
| BUG-P2-H4 | HIGH | ✅ FIXED | app_celery.py | Celery inspector calls block event loop (sync Redis in async endpoint) |
| BUG-P2-H5 | HIGH | ✅ FIXED | app_celery.py | `generate_course_quiz` swallows HTTPException in broad `except` |
| BUG-P2-H6 | HIGH | ✅ FIXED | teaching_service.py | 5-second LLM timeout too aggressive — causes frequent fallback |
| BUG-P2-H7 | HIGH | ✅ FIXED | teaching_service.py | TTS pause injection (`" ... "` after every sentence) doubles content |
| BUG-P2-H8 | HIGH | ✅ FIXED | assessment_service.py | Hard crash if `DatabaseServiceV2()` constructor fails |
| BUG-P2-H9 | HIGH | ✅ FIXED | quiz_service.py | No timeout on LLM quiz generation — can hang indefinitely |
| BUG-P2-M1 | MEDIUM | ✅ FIXED | quiz_service.py | Deprecated `.dict()` calls (Pydantic v2 uses `.model_dump()`) |
| BUG-P2-M2 | MEDIUM | ✅ FIXED | sarvam_service.py | Duplicate imports (`io`, `Optional` imported twice) |
| BUG-P2-M3 | MEDIUM | ✅ FIXED | sarvam_service.py | `print()` used instead of `logging` throughout (~50 calls) |
| BUG-P2-M4 | MEDIUM | ✅ FIXED | database_service_v2.py | Cursor leak in `get_dashboard_stats` / `get_course_completion_stats` |
| GAP-P2-1 | MEDIUM | ⏳ NOTED | database_service_v2.py | Hardcoded DB credentials in source code (security) |
| GAP-P2-2 | MEDIUM | ⏳ NOTED | assessment_service.py | `submit_assessment` declared async but only sync DB calls |
| GAP-P2-3 | LOW | ⏳ NOTED | teaching_service.py | `re.IGNORECASE` on abbreviation patterns may match inside words |

---

## 10. PHASE 2 FIX DETAILS

### BUG-P2-C1: Blocking Sync DB Calls in Async Endpoints
**File:** `app_celery.py` — `/api/chat`, `/api/chat-with-audio`, `/api/chat-with-audio-stream`  
**Root Cause:** `session_manager.get_or_create_session()`, `.get_conversation_history()`, `.add_message()` are all synchronous PostgreSQL calls via psycopg2. Calling them directly inside `async def` endpoints blocks the entire asyncio event loop, freezing all concurrent requests.  
**Fix:** Wrapped every sync DB call in `await loop.run_in_executor(None, lambda: ...)`. Variables captured before `await` to prevent closure issues. Applied consistently across all three chat endpoints.

### BUG-P2-C2: Connection Pool Poisoning
**File:** `services/database_service_v2.py` — `execute_query()`  
**Root Cause:** When a connection fails validation, the code called `conn.close()` then `self.return_connection(conn)`. Returning a closed connection to `SimpleConnectionPool` poisons the pool — subsequent `getconn()` may return the dead connection.  
**Fix:** Replaced `return_connection(conn) + conn.close()` with `self.pool.putconn(conn, close=True)` which properly removes the connection from the pool. Same pattern applied to the retry exception handler.

### BUG-P2-C3 + BUG-P2-C4: Quiz Stats Return Raw Scores Instead of Percentages
**File:** `services/database_service_v2.py` — `get_user_quiz_stats()`  
**Root Cause:** SQL query used `AVG(score)` and `MAX(score)` which return raw integers (e.g., 14 out of 20). The `passed_count` used `score >= 70` which is correct for 100-question quizzes but wrong for 20-question quizzes. Recommendation summary displayed raw score as percentage.  
**Fix:** Changed SQL to compute percentages: `AVG(score::float / total_questions * 100)`. Fixed `passed_count` to use `(score::float / total_questions * 100) >= 60`. Added `round(float(...), 1)` conversion for both `avg_score` and `best_score`.

### BUG-P2-H1: Unreachable Code
**File:** `app_celery.py` — `get_course_content()`  
**Fix:** Removed dead `raise HTTPException(status_code=404, ...)` after completed if/elif/else chain where every branch already raises or returns.

### BUG-P2-H2: Cursor Leak in get_all_users
**File:** `app_celery.py` — admin users endpoint  
**Root Cause:** Used raw `database_service.get_connection()` + `cur = conn.cursor()` without try/finally for cursor cleanup. Any exception after cursor creation leaked the cursor.  
**Fix:** Replaced raw SQL with `database_service.execute_query()` which uses context-managed cursors internally.

### BUG-P2-H3: RecommendationService Per-Request Instantiation
**File:** `app_celery.py` — `/api/recommendations/{user_id}`  
**Root Cause:** Every request created `RecommendationService()` which creates a new `DatabaseServiceV2()` with a new connection pool (minconn=1, maxconn=10). Under load, this exhausts database connections.  
**Fix:** Cached instance on function attribute `get_recommendations._rec_service`. Also wrapped the synchronous `get_recommendations()` call in `run_in_executor()`.

### BUG-P2-H4: Celery Inspector Blocks Event Loop
**File:** `app_celery.py` — `/api/celery/workers`  
**Fix:** Wrapped `inspector.active()`, `.scheduled()`, `.reserved()` calls in `run_in_executor()` since they perform synchronous Redis operations.

### BUG-P2-H5: Swallowed HTTPException
**File:** `app_celery.py` — `generate_course_quiz()`  
**Fix:** Added `except HTTPException: raise` before the broad `except Exception` clause.

### BUG-P2-H6: Teaching Content LLM Timeout Too Short
**File:** `services/teaching_service.py` — `generate_teaching_content()`  
**Root Cause:** 5-second timeout for LLM content generation. GPT-4o-mini routinely takes 8–15s for rich teaching content, causing constant fallback to basic template content.  
**Fix:** Increased timeout from 5.0s to 30.0s.

### BUG-P2-H7: TTS Pause Inflation
**File:** `services/teaching_service.py` — `_format_for_tts()`  
**Root Cause:** Added `" ... "` after every `. `, `? `, and `! ` in the content, plus `" ... ... "` for paragraph breaks. This roughly doubled content length and made TTS output sound robotic with excessive pauses. Modern TTS engines (ElevenLabs, Sarvam) handle natural pauses from punctuation.  
**Fix:** Removed sentence-level pause injection entirely. TTS engines handle pauses naturally.

### BUG-P2-H8: AssessmentService Hard Crash
**File:** `services/assessment_service.py` — `__init__()`  
**Root Cause:** `DatabaseServiceV2()` constructor called without try/except. If DB is unreachable at startup, the entire service initialization fails and crashes the app.  
**Fix:** Wrapped in try/except, set `self.db_service = None` on failure. Added `if not self.db_service: raise RuntimeError(...)` guards in `process_and_generate_assessment()` and `submit_assessment()`.

### BUG-P2-H9: Quiz Generation No Timeout
**File:** `services/quiz_service.py` — `generate_module_quiz()`, `generate_course_quiz()`  
**Root Cause:** LLM calls for quiz generation had no timeout. A stalled OpenAI API response could hang the endpoint indefinitely, consuming a worker thread.  
**Fix:** Wrapped all `llm_service.generate_response()` calls in `asyncio.wait_for(..., timeout=120.0)` (2 minutes — generous for 20-question generation).

### BUG-P2-M1: Pydantic v2 Deprecation
**File:** `services/quiz_service.py`  
**Fix:** Replaced all `.dict()` calls with `.model_dump()` for Pydantic v2 compatibility.

### BUG-P2-M2 + M3: Sarvam Service Code Quality
**File:** `services/sarvam_service.py`  
**Fix:** Removed duplicate `import io` and `from typing import Optional`. Added `import logging` + `logger = logging.getLogger(__name__)`. Converted ~50 `print()` calls to appropriate `logger.error()`, `logger.warning()`, `logger.info()`, `logger.debug()` calls.

### BUG-P2-M4: Cursor Leak Safety
**File:** `services/database_service_v2.py` — `get_dashboard_stats()`, `get_course_completion_stats()`  
**Fix:** Wrapped `cur.close()` and `conn.rollback()` in try/except in finally blocks. If `cur` was never created (e.g., `get_connection()` failed), `cur.close()` would raise `NameError`.

---

## 11. FILES MODIFIED (Phase 2)

| File | Changes |
|------|---------|
| `app_celery.py` | P2-C1, P2-H1, P2-H2, P2-H3, P2-H4, P2-H5 |
| `services/database_service_v2.py` | P2-C2, P2-C3, P2-C4, P2-M4 |
| `services/teaching_service.py` | P2-H6, P2-H7 |
| `services/assessment_service.py` | P2-H8 |
| `services/quiz_service.py` | P2-H9, P2-M1 |
| `services/sarvam_service.py` | P2-M2, P2-M3 |

---

## 12. REMAINING WORK (Phase 2 Gaps — Future Sprints)

| ID | Description | Effort |
|----|-------------|--------|
| GAP-P2-1 | Move hardcoded DB credentials to env vars only | Low |
| GAP-P2-2 | Wrap sync DB calls in AssessmentService.submit_assessment with run_in_executor | Low |
| GAP-P2-3 | Use word-boundary-only regex for abbreviation replacement in TTS formatting | Low |
| GAP-P2-4 | Add health-check endpoint for database connectivity | Low |
| GAP-P2-5 | Add pagination to recommendation queries for users with many courses | Medium |
| GAP-P2-6 | Add retry logic to Sarvam TTS streaming connection failures | Medium |

---

# PHASE 3: INTERACTIVE TEACHING BUGS (Live Session Analysis)

> **Date:** 2026-02-25  
> **Scope:** Bugs found from live interactive teaching session logs

---

## 13. PHASE 3 BUG TRACKER

| ID | Priority | Status | Component | Description |
|----|----------|--------|-----------|-------------|
| BUG-P3-C1 | CRITICAL | ✅ FIXED | realtime_orchestrator.py | `on_barge_in()` destroys `PENDING_CONFIRMATION` phase — user's "Yes" to confirmation gets classified as `continue` |
| BUG-P3-C2 | CRITICAL | ✅ FIXED | realtime_orchestrator.py | `next_course` always asks "mark complete?" even if user just marked it — infinite confirmation loop |
| BUG-P3-H1 | HIGH | ✅ FIXED | realtime_orchestrator.py + websocket_server.py | Standalone `mark_complete` dead-ends — no follow-up to advance to next topic/course |
| BUG-P3-H2 | HIGH | ✅ FIXED | elevenlabs_service.py | ElevenLabs quota_exceeded (401) wastes time trying WebSocket + REST fallbacks before Edge TTS |
| BUG-P3-M1 | MEDIUM | ✅ FIXED | realtime_orchestrator.py | Missing STT mishearing variants in keyword lists (`market` for `mark it`, etc.) |

---

## 14. PHASE 3 FIX DETAILS

### BUG-P3-C1: Barge-in Destroys Confirmation State
**File:** `services/realtime_orchestrator.py` — `on_barge_in()`  
**Root Cause:** When the system plays the confirmation audio ("Sure Vivek, should I mark the current course as complete?"), the user's spoken response triggers a barge-in first (since TTS is still playing). `on_barge_in()` unconditionally transitioned to `PAUSED_FOR_QUERY`, destroying the `PENDING_CONFIRMATION` phase. When `process_user_input()` then ran, `pending=False`, so "okay" matched `_CONTINUE_KW` instead of `_CONFIRM_YES_KW`.  
**Fix:** Added a guard in `on_barge_in()`: if the current phase is `PENDING_CONFIRMATION`, preserve it instead of transitioning. The user is responding to the prompt, not interrupting teaching content.

### BUG-P3-C2: Next Course Confirmation Loop
**File:** `services/realtime_orchestrator.py` — `process_user_input()` (NEXT_COURSE handler)  
**Root Cause:** The `NEXT_COURSE` handler always set `pending_action="next_course"` and asked "should I mark complete?" — even if the user had JUST marked the topic complete in the previous turn. This created an infinite loop: mark → next course → "mark complete?" → yes → mark (again) → next course → "mark complete?" → ...  
**Fix:** Added `topic_marked_complete` flag to `TeachingState`. Set to `True` when user marks complete via `MARK_COMPLETE`, `MARK_AND_NEXT_COURSE`, or `CONFIRM_YES`. The `NEXT_COURSE` handler checks this flag and skips confirmation if already marked, going directly to `next_course` action. Flag is reset in `advance_topic()` when loading a new topic.

### BUG-P3-H1: Mark Complete Dead-End
**Files:** `services/realtime_orchestrator.py` + `websocket_server.py`  
**Root Cause:** When user said "Mark as complete", the orchestrator returned `mark_complete` action. The websocket handler marked the topic and said "Done!" but offered no follow-up. The user had to separately say "next course" which triggered the confirmation loop (BUG-P3-C2).  
**Fix:** The `mark_complete` action now includes `has_next`, `next_module_index`, and `next_sub_topic_index` data. The websocket handler checks `has_next` and, if true, sets up a `pending_action="advance_next_topic"` on the orchestrator state and streams a follow-up question: "Great {name}, shall we move on to the next topic?"

### BUG-P3-H2: ElevenLabs Quota Cascade Failure
**File:** `services/elevenlabs_service.py` — `text_to_speech_stream()`  
**Root Cause:** When SDK call fails with `quota_exceeded` (401), the code tried WebSocket fallback, then REST fallback — both of which also fail with the same exhausted API key. This wasted ~2 seconds before reaching Edge TTS. First teaching turn (4981 chars = 2490 credits needed, only 1930 remaining) triggered this cascade; subsequent shorter texts fit within quota.  
**Fix:** Added `quota_exhausted` flag. When SDK error contains 'quota', '401', or 'unauthorized', set the flag and skip directly to Edge TTS fallback. Same detection added to WebSocket fallback stage.

### BUG-P3-M1: STT Mishearing Coverage
**File:** `services/realtime_orchestrator.py` — keyword lists  
**Root Cause:** Deepgram frequently mishears "mark it" as "market", "mark" as "march". These variants were partially covered in `_CONFIRM_YES_KW` but missing from `_MARK_COMPLETE_KW`.  
**Fix:** Added `'market complete'`, `'market is complete'`, `'market as complete'`, `'market it complete'`, `'march complete'`, `'march as complete'` to `_MARK_COMPLETE_KW`. Added `'yes mark'`, `'please mark it'`, `'mark it as complete'`, `'let\'s do it'`, `'sounds good'` to `_CONFIRM_YES_KW`.

---

## 15. FILES MODIFIED (Phase 3)

| File | Changes |
|------|---------|
| `services/realtime_orchestrator.py` | P3-C1, P3-C2, P3-H1, P3-M1 |
| `websocket_server.py` | P3-H1 (mark_complete follow-up) |
| `services/elevenlabs_service.py` | P3-H2 |
