# Interactive Session Issues — Root Cause Analysis & Fix Plan

## ISSUE 1: Service Re-initialization on Session Start (20s+ delay)

### Root Cause
`ProfAIAgent.__init__` (websocket_server.py:188-214) creates **new instances** of `ChatService()`, `AudioService()`, `TeachingService()` for **every** WebSocket client connection. These constructors are heavy:
- `ChatService()` → loads ChromaDB (54k docs), initializes SemanticRouter (3 routes), creates RAG service + BM25 retriever
- `AudioService()` → initializes Deepgram STT client + ElevenLabs TTS SDK
- `TeachingService()` → initializes LLM chains

Meanwhile `app_celery.py` already pre-initializes these same services at startup. The per-client re-init adds 15-25 seconds to every session start.

### Fix
Convert ChatService, AudioService, TeachingService to **module-level singletons** in websocket_server.py:
- Create `_shared_chat_service`, `_shared_audio_service`, `_shared_teaching_service` at module level
- `ProfAIAgent.__init__` references the shared instances instead of creating new ones
- Fallback: if singleton is None (startup failed), try creating per-client

---

## ISSUE 2: Delay After Teaching Audio Completes / Barge-in Lag

### Root Cause
After every answer, `_execute_answer_pipeline()` (line 1852-1860) concatenates:
```python
resume_prompt = self.orchestrator.get_resume_text(thread_id)
full_response = f"{answer_text} {resume_prompt}"
```
Then streams the ENTIRE thing via TTS. The `get_resume_text()` always returns:
> "Is your doubt clear, {name}? We have N more sections to cover. Say 'continue' when you're ready to resume."

This adds ~5-8 seconds of unnecessary TTS after every answer. The user has to wait for this to finish before barge-in reacts, creating perceived lag.

### Fix
- Remove the resume prompt from TTS stream — the answer itself should end naturally
- The `answer_question` prompt already handles wrapping up naturally
- The UI already shows "Section complete" and "continue" button — no need for audio resume prompt
- Restructure `get_resume_text()` to be much shorter or remove it entirely from TTS

---

## ISSUE 3: "Which topics have I completed" → MARK_COMPLETE (misclassification)

### Root Cause
`_MARK_COMPLETE_KW` (line 215) contains the bare keyword `'completed'`. The phrase "which topics have I completed" matches this keyword. In `classify_intent()`, MARK_COMPLETE is checked at line 386 **before** CHECK_PROGRESS at line 394. So the query hits MARK_COMPLETE first.

Additionally, `_CHECK_PROGRESS_KW` has `'what have i completed'` but NOT `'which ones have i completed'` or `'which topics have i completed'`.

### Fix
1. Remove bare `'completed'` from `_MARK_COMPLETE_KW` — too generic, causes false positives
2. Add specific phrases to `_CHECK_PROGRESS_KW`: `'which ones have i completed'`, `'which topics have i completed'`, `'topics i completed'`
3. Move CHECK_PROGRESS check **before** MARK_COMPLETE in `classify_intent()` to prioritize progress queries

---

## ISSUE 4: Unnatural LLM Responses — Missing Context in Prompt

### Root Cause
The `answer_question` prompt in `langgraph_teaching_agent.py` (line 388-421) has:
- **No current module/topic name** — model doesn't know what we're teaching right now
- **No progress info** — model doesn't know how far the user is (e.g., "2/53 topics done")
- **No next topic info** — model can't guide about what comes next
- **No previous topic context** — model can't reference what was taught before
- **Repetitive "Hi {name}"** — prompt says "use sparingly" but model still over-uses it
- **"Is your doubt clear"** appended to every answer via `get_resume_text()` → feels robotic

The `lg_state` dict (realtime_orchestrator.py:1300-1316) passes `teaching_content` but NOT:
- `module_title`, `sub_topic_title`
- `total_modules`, `total_sub_topics`
- Progress percentage
- Previously completed topics

### Fix
1. Pass rich context to `answer_question` prompt:
   - module_title, sub_topic_title, course_title
   - progress: "3/53 topics completed (6%)"
   - previously taught topic title
   - next topic title
2. Rewrite the prompt to be explicitly conversational with rules:
   - NEVER start with student name
   - NEVER say "Is your doubt clear" — end naturally
   - Reference the current topic when relevant
   - Vary transitions
3. Remove `get_resume_text()` TTS from answer pipeline — let the UI handle "continue" prompt
4. Add conversation context directly to the prompt template

---

## Implementation Status — ALL FIXED ✅

### ISSUE 1 — Service Singleton ✅
- Added `_shared_chat_service`, `_shared_audio_service`, `_shared_teaching_service` module-level singletons
- Added `_get_shared_*()` lazy getter functions
- `ProfAIAgent.__init__` now calls getters instead of constructors
- **Expected impact**: Session start reduced from ~25s to <2s

### ISSUE 2 — Resume TTS Removed ✅
- Removed `get_resume_text()` concatenation from `_execute_answer_pipeline()` — answers end naturally
- Rewrote `get_resume_text()` to be short and natural (no more "Is your doubt clear")
- UI already shows "continue" button — no need for audio resume prompt

### ISSUE 3 — Intent Misclassification ✅
- Removed bare `'completed'` from `_MARK_COMPLETE_KW` (replaced with `'i have completed this'`)
- Added 8 new phrases to `_CHECK_PROGRESS_KW` (e.g., `'which topics have i completed'`, `'completed so far'`)
- Moved `CHECK_PROGRESS` check **before** `MARK_COMPLETE` in `classify_intent()`
- **Tested: 10/10 intent classification tests pass**

### ISSUE 4 — Prompt Restructuring ✅
- Added rich context fields to LangGraph `TeachingState`: `course_title`, `module_title`, `sub_topic_title`, `progress_summary`, `previous_topic_title`, `next_topic_title`, `conversation_history_text`
- Rewrote `answer_question()` prompt with 10 explicit rules for natural conversation
- `answer_question_with_llm()` now passes: conversation history, progress %, previous/next topic, persona info
- `course_title` set on orchestrator state in `_handle_select_course`, `_handle_resume_session`, `_handle_next_course`, `handle_interactive_teaching`
- Key prompt rules: no name at start, no "Great question!", no "Is your doubt clear?", short spoken-audio answers

---

## ISSUE 5: Double-Processing of resume_session (first utterance hangs, second causes conflict) ✅

### Root Cause (4 factors)
1. **Duplicate DB call**: `_find_resume_point()` calls `get_course_with_content()` (~23s), then `_handle_resume_session()` calls it AGAIN (~18s). Total: ~40s blocking.
2. **Synchronous DB calls block the event loop**: `get_user_learning_summary()`, `_find_resume_point()`, and `update_session_course()` are sync and ran directly inside an async task — freezing the entire asyncio event loop (including the STT listener) for 23+ seconds.
3. **No processing guard**: `_schedule_action()` blindly created new tasks without cancelling old ones or deduplicating. Two `resume_session` tasks ran in parallel, conflicting.
4. **No immediate feedback**: User got zero indication the command was received during the 23s wait, so they repeated it.

### Timeline of the bug
- 12:46:23 — First "Let's start from where we left off" → `resume_session` dispatched
- 12:46:23 to 12:46:47 — **Event loop frozen** (sync DB call). STT events buffered.
- 12:46:47 — First DB call returns. Second DB call starts (another 18s).
- 12:47:06 — Resume intro sent + teaching starts
- 12:47:06 — **Buffered STT events flood in** → barge-in #2 + #3 → second `resume_session` → first one's teaching cancelled

### Fix (4 changes)
1. **Cache `_course_data`** in `_find_resume_point()` return dict → `_handle_resume_session()` uses it instead of calling DB again. Saves ~20s.
2. **`run_in_executor`** for all blocking DB calls in `_handle_resume_session()` — prevents event loop freeze.
3. **Processing guard in `_schedule_action()`** — cancels existing running task + deduplicates same action within 2s window.
4. **Immediate `system_message`** sent to client ("📍 Resuming your session...") so user knows command was received.

### Files Modified
- `websocket_server.py` — Service singletons, remove resume TTS, set course_title, processing guard, run_in_executor, immediate feedback
- `services/realtime_orchestrator.py` — Intent keywords, classify_intent order, TeachingState.course_title, get_resume_text, rich LangGraph context
- `services/langgraph_teaching_agent.py` — TeachingState fields, answer_question prompt rewrite
- `services/session_init_service.py` — Cache `_course_data` in `_find_resume_point` return value
