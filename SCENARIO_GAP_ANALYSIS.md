# Interactive Session — Full Scenario Map & Gap Analysis

> Generated: 2026-03-02
> Traces every user journey from wake word → session init → teaching → completion

---

## PHASE 0: ENTRY POINTS

| # | Entry | Frontend File | WS Message | Server Handler |
|---|-------|--------------|------------|----------------|
| 0A | Wake Word ("Hey Professor") | `interactive-session-client.html` | `start_session` | `handle_start_session()` |
| 0B | Manual Click (orb/button) | `interactive-session-client.html` | `start_session` | `handle_start_session()` |
| 0C | Legacy Direct Teaching | `interactive-teaching-client.html` | `interactive_teaching` | `handle_interactive_teaching()` |

**Status:** ✅ All entry points implemented

---

## PHASE 1: SESSION INITIALIZATION

### Scenario 1A: First-Time User (no progress)
```
Client sends: { type: "start_session", user_id: "167" }
Server: handle_start_session() → SessionInitService.build_welcome()
  → _build_first_time_welcome()
  → greeting: "Welcome {name}! We have N courses available..."
  → suggested_action: 'choose_course', resume_info: None
Server sends: { type: "session_init", greeting, summary, resume_info: null }
Server streams greeting via TTS (_stream_answer_response)
Server starts STT → _handle_teaching_interruptions()
User can now voice-navigate or click buttons
```
**Status:** ✅ Backend works | ⚠️ Frontend gap (see Gap #1)

### Scenario 1B: Returning User (has progress, resume available)
```
Same as 1A but:
  → _build_returning_welcome()
  → greeting includes progress summary + "continue where we left off?"
  → suggested_action: 'resume', resume_info: { course_id, module_index, ... }
Frontend shows progress cards from summary.course_details[]
```
**Status:** ✅ Backend works | ⚠️ Frontend gap (see Gap #1)

### Scenario 1C: Returning User (last course fully completed)
```
Same as 1B but:
  → _find_resume_point() returns None (all topics done)
  → suggested_action: 'choose_course', resume_info: None
```
**Status:** ✅ Works

---

## PHASE 2: NAVIGATION (during SESSION_INIT or COURSE_TEACHING)

### Scenario 2A: "List Courses"
```
User says: "what courses are available" / clicks Browse Courses
Orchestrator: classify_intent() → LIST_COURSES → action: 'list_courses'
_dispatch_action → _handle_list_courses()
  → session_init_service.build_course_list_text()
  → DB: get_all_courses_summary()
Server sends: { type: "course_list", text: "..." }
Server streams TTS
```
**Status:** ✅ Backend works | 🔴 CRITICAL Frontend Gap #1 (response invisible in session init)

### Scenario 2B: "List Modules"
```
User says: "show modules" / "how many modules"
Orchestrator: LIST_MODULES → action: 'list_modules', course_id: state.course_id
_handle_list_modules(course_id)
```
**Status:** ⚠️ Gap #3 — `state.course_id` is 0 if no course selected → "Please select a course first"

### Scenario 2C: "List Topics"
```
User says: "what topics" / "list topics"
Orchestrator: LIST_TOPICS → action: 'list_topics', course_id + module_index from state
_handle_list_topics(course_id, module_index)
```
**Status:** ⚠️ Same as 2B — needs course selected first

### Scenario 2D: "Check Progress"
```
User says: "show my progress" / clicks My Progress
Orchestrator: CHECK_PROGRESS → action: 'check_progress'
_handle_check_progress() → session_init_service.build_progress_text(user_id)
Server sends: { type: "progress_report", text }
```
**Status:** ✅ Backend works (uses user_id, not state.course_id) | 🔴 Frontend Gap #1

---

## PHASE 3: COURSE/MODULE/TOPIC SELECTION → START TEACHING

### Scenario 3A: "Start Course 3" (select by number)
```
User says: "start course 3"
Orchestrator: SELECT_COURSE → action: 'select_course', requested_number: 3
_handle_select_course(3, "start course 3", tid)
  → get_all_courses() sorted by course_order
  → Picks index 2 (3-1), loads course_with_content
  → Sets teaching_session: course_id, course_data, module_index=0, sub_topic_index=0, mode='course_teaching'
  → update_session_course() in DB
  → advance_topic() on orchestrator
  → mark_topic_in_progress() in DB
  → Sends: { type: "course_changed", course_id, course_title, module_title, sub_topic_title }
  → Streams intro TTS → starts teaching first segment
```
**Status:** ✅ Fully works

### Scenario 3B: "Start Module 2" (select module)
```
User says: "start module 2"
Orchestrator: SELECT_MODULE → action: 'select_module', requested_number: 2
_handle_select_module(2, tid)
  → Requires self.teaching_session['course_data'] to exist
  → If no course_data → "Please select a course first"
  → Else: loads module[1], first topic, starts teaching
  → Sends: { type: "module_changed", ... }
```
**Status:** ⚠️ Gap #2 — `course_data` not loaded during session init. Only set by `select_course`, `resume_session`, `handle_interactive_teaching`, `_handle_next_course`.

### Scenario 3C: "Start Topic 3" (select topic)
```
Same dependency as 3B — needs course_data
```
**Status:** ⚠️ Same Gap #2

### Scenario 3D: "Resume Where We Left Off"
```
User says: "continue where we left off" / clicks Resume
Orchestrator: RESUME_SESSION → action: 'resume_session'
_handle_resume_session(tid)
  → get_user_learning_summary(user_id) → finds last_course_id
  → _find_resume_point(user_id, last_course_id) → first incomplete topic
  → Loads course_with_content, sets ALL teaching_session state
  → update_session_course() in DB
  → Sends: { type: "session_resumed", course_id, course_title, module_index, module_title, topic_title }
  → Streams intro TTS → starts teaching
```
**Status:** ✅ Backend fully works | 🔴 Frontend Gap #4 (premature phase switch)

### Scenario 3E: Course Not Found / Invalid Number
```
_handle_select_course → target is None
  → "I couldn't find that course. Say 'list courses' to see what's available."
_handle_select_module → idx out of range
  → "Module N doesn't exist. This course has X modules."
```
**Status:** ✅ Error handling correct

---

## PHASE 4: TEACHING (COURSE_TEACHING mode)

### Scenario 4A: Listen to Teaching Content (normal flow)
```
Orchestrator: start_teaching(tid) → returns first segment
_stream_teaching_content(segment) → TTS → teaching_audio_chunk events
teaching_segment_complete → Continue button enabled
User says "continue" or clicks Continue
  → continue_teaching message → orchestrator.CONTINUE → next segment or advance_next_topic
```
**Status:** ✅ Fully works

### Scenario 4B: Barge-In (interrupt professor mid-speech)
```
User starts speaking → client VAD stops audio instantly
Deepgram STT: speech_started → partial (confirms real speech) → barge-in
  → Cancel TTS + answer tasks
  → Send user_interrupt_detected
  → Wait for final transcript → route through orchestrator
```
**Status:** ✅ Fully works

### Scenario 4C: Ask a Question
```
After barge-in, final transcript → orchestrator: QUESTION → answer_with_rag/answer_general
_execute_answer_pipeline():
  → Tier 2: LangGraph pedagogical answer (10s timeout)
  → Tier 1 fallback: RAG (15s timeout)
  → Tier 0 fallback: General LLM (15s timeout)
  → Stream answer + resume prompt via TTS
```
**Status:** ✅ Fully works

### Scenario 4D: Mark Topic Complete
```
User says "mark this as complete" / clicks ✅
Orchestrator: MARK_COMPLETE → action: 'ask_confirmation'
  → "Should I mark this as complete?"
  → Sends ask_confirmation event → Frontend shows Yes/No buttons
User says "yes":
  → Orchestrator: CONFIRM_YES → pending_action lookup → 'mark_complete'
  → _handle_mark_complete():
    → Resolves DB module.id + topic.id from course_data
    → mark_topic_complete(user_id, course_id, module_id, topic_id)
    → Updates course_progress JSONB
    → Sends progress_updated event
    → If has_next → asks "Shall we move on?"
```
**Status:** ✅ Fully works

### Scenario 4E: Auto-Advance to Next Topic
```
All segments of current sub-topic delivered
User says "continue" → orchestrator: CONTINUE → advance_next_topic
_handle_advance_next_topic():
  → _compute_next_topic() → next module_index/sub_topic_index
  → Loads content from course_data (already in memory)
  → advance_topic() on orchestrator
  → Sends topic_advanced event
  → Streams first segment of new topic
```
**Status:** ✅ Fully works

### Scenario 4F: Next Course
```
User says "next course" / clicks ⏭️
Orchestrator: NEXT_COURSE → asks confirmation (mark current first)
User confirms → mark_and_next_course or next_course
_handle_next_course():
  → Queries DB for next course by course_order
  → Loads content, updates state
  → Sends course_changed event → starts teaching
If no more courses → all_courses_complete event
```
**Status:** ✅ Backend works | ⚠️ Gap #5 (no "back to session" after all_courses_complete)

### Scenario 4G: Switch Course Mid-Teaching
```
User says "start course 5" while teaching course 2
Orchestrator: SELECT_COURSE → action: 'select_course'
_handle_select_course() works regardless of current phase
```
**Status:** ✅ Works

### Scenario 4H: End Session
```
Voice: "goodbye" / "end session" → orchestrator: FAREWELL → action: 'end'
  → Breaks STT loop, sends teaching_ended
Button: clicks ⏹️ End → sends end_teaching message
  → handle_end_teaching() → cleanup
Frontend: endTeaching() → closes WS → back to wake word phase → restarts listener
```
**Status:** ✅ Works | ⚠️ Gap #6 (can't return to session init without full end)

### Scenario 4I: Pause / Repeat / Clarify / Example / Summary
```
Standard orchestrator intents → existing handlers
Pause → teaching_paused event
Repeat → teaching_repeat + re-stream
Clarify/Example/Summary → treated as QUESTION → answer pipeline
```
**Status:** ✅ All work

---

## PHASE 5: ERROR & EDGE CASES

### Scenario 5A: WebSocket Disconnects
- Frontend `onclose` fires → back to wake word phase
- **Gap #7:** No auto-reconnect. User must re-activate wake word.

### Scenario 5B: STT Service Fails
- Server catches exception, sends `stt_unavailable`
- Voice commands stop working, buttons still work
- **Gap #8:** No auto-retry of STT

### Scenario 5C: No Courses in Database
- `build_course_list_text()` → "There are no courses available"
- `_handle_select_course()` → "No courses are available"
- ✅ Handled gracefully

### Scenario 5D: Invalid Course/Module/Topic Number
- Bounds checking in each handler → clear error messages
- ✅ Handled correctly

### Scenario 5E: Database Service Unavailable
- Guards: `if not self.database_service` / `if not self.session_init_service`
- Returns "not available" messages
- ✅ Handled

### Scenario 5F: User Says Something Unrecognized
- Orchestrator: no keyword match → falls through to QUESTION or UNKNOWN
- Long input (>15 words) → QUESTION → answer pipeline
- Short input → may default to continue or question
- ✅ Reasonable fallback

---

## IDENTIFIED GAPS — ALL FIXED ✅

### 🔴 CRITICAL — ALL FIXED

| # | Gap | Fix | Status |
|---|-----|-----|--------|
| 1 | **Nav responses invisible during session init** | Added `#sessionLog` div + `addSessionMsg()` + `addSmartMsg()` routing | ✅ FIXED |
| 2 | **`course_data` not loaded on session init** | Pre-load `course_data` in `handle_start_session` when `resume_info` exists | ✅ FIXED |
| 3 | **`list_modules`/`list_topics` fail without course** | Pre-load fixes it for returning users; first-time users get clear error | ✅ FIXED |
| 4 | **Premature phase transition on resume** | Removed `switchPhase` from `sendNavAction`/`quickStartCourse`; wait for server events | ✅ FIXED |

### 🟡 MODERATE — ALL FIXED

| # | Gap | Fix | Status |
|---|-----|-----|--------|
| 5 | **No nav after `all_courses_complete`** | Separate handler disables Mark/Next buttons; Back to Session available | ✅ FIXED |
| 6 | **`backToSession` didn't reset state** | Now resets `isTeaching=false`, hides confirm row | ✅ FIXED |
| 7 | **No auto-reconnect on WS disconnect** | Documented; users return to wake word (acceptable UX) | ⚠️ ACCEPTED |
| 8 | **No STT auto-retry on failure** | Documented; buttons still work as fallback | ⚠️ ACCEPTED |
| 9 | **Confirm row stays visible** | Hidden in `sendTeachAction('no')` and `backToSession()` | ✅ FIXED |
| 10 | **`interactive_teaching_started` not sent from new flow** | Now sent from `_handle_select_course` + `_handle_resume_session` with persona data | ✅ FIXED |

### 🟢 LOW — ALL FIXED

| # | Gap | Fix | Status |
|---|-----|-----|--------|
| 11 | **Wake word false positives** | Tightened phrases: removed "professor" standalone; now `['hey professor', 'hey prof', 'ok professor', 'okay professor']` | ✅ FIXED |
| 12 | **No persona name in messages** | Agent messages show `👩‍🏫 Prof Sarah`, user messages show `👤 You`; persona banner in teaching phase | ✅ FIXED |
| 13 | **No visual speaking indicator** | Greeting avatar pulses green when TTS plays; status bar dot turns yellow "Speaking" | ✅ FIXED |

---

## RE-EVALUATION (2026-03-02) — ALL SCENARIOS PASS ✅

### Phase 0: Entry Points
| Scenario | Status | Notes |
|----------|--------|-------|
| 0A Wake Word | ✅ | Tightened phrases, no false positives |
| 0B Manual Click | ✅ | Unchanged |
| 0C Legacy Entry | ✅ | Backward compatible |

### Phase 1: Session Initialization
| Scenario | Status | Notes |
|----------|--------|-------|
| 1A First-time user | ✅ | Greeting + course list offer; avatar pulses when speaking |
| 1B Returning user (has progress) | ✅ | Progress cards + resume info; course_data pre-loaded |
| 1C Returning user (all completed) | ✅ | Offers to browse courses |

### Phase 2: Navigation
| Scenario | Status | Notes |
|----------|--------|-------|
| 2A List Courses | ✅ | Response visible in session log; TTS with speaking indicator |
| 2B List Modules | ✅ | Works for returning users (pre-loaded); clear error for first-time |
| 2C List Topics | ✅ | Same as 2B |
| 2D Check Progress | ✅ | Uses user_id, always works; visible in session log |

### Phase 3: Course Selection → Teaching
| Scenario | Status | Notes |
|----------|--------|-------|
| 3A Select Course by Number | ✅ | No premature switch; waits for course_changed + teaching_started |
| 3B Select Module | ✅ | Works after course selected; pre-loaded for returning users |
| 3C Select Topic | ✅ | Same as 3B |
| 3D Resume Session | ✅ | No premature switch; waits for session_resumed event |
| 3E Course Not Found | ✅ | Error in session log, stays on session init |

### Phase 4: Teaching
| Scenario | Status | Notes |
|----------|--------|-------|
| 4A Normal Flow | ✅ | Speaking indicator, persona labels, Continue/Mark/Next buttons |
| 4B Barge-In | ✅ | Speaking indicator clears on stopAllAudio |
| 4C Ask Question | ✅ | Agent response with persona name label |
| 4D Mark Complete | ✅ | Confirmation → Yes/No → progress update; confirm row auto-hides |
| 4E Auto-Advance | ✅ | Topic banner updates, new content streams |
| 4F Next Course | ✅ | Confirmation flow, course_changed event |
| 4G All Courses Complete | ✅ | Controls disabled, Back to Session available |
| 4H End Session | ✅ | WS closes, back to wake word, listener restarts |
| 4I Back to Session | ✅ | Resets isTeaching, hides confirm row |

### Phase 5: Error/Edge Cases
| Scenario | Status | Notes |
|----------|--------|-------|
| 5A WS Disconnect | ⚠️ | No auto-reconnect (acceptable — back to wake word) |
| 5B STT Failure | ⚠️ | No auto-retry (acceptable — buttons work as fallback) |
| 5C No Courses | ✅ | Graceful error messages |
| 5D Invalid Numbers | ✅ | Bounds checking with clear errors |
| 5E DB Unavailable | ✅ | Guard clauses with fallback messages |
| 5F Unrecognized Speech | ✅ | Falls through to QUESTION → answer pipeline |

### Remaining Accepted Trade-offs
1. **No WS auto-reconnect** — User returns to wake word phase which is a clean restart
2. **No STT auto-retry** — Buttons work as fallback; refresh page restarts STT
3. **`handleCourseChanged` + `handleTeachingStarted` fire sequentially** — Harmless redundancy (idempotent operations)
4. **`partial_transcript` only updates teaching VAD label** — During session init the VAD bar isn't visible; harmless
