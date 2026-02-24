# ProfAI Service Audit & Bug Analysis

## 1. Complete Service Map

### REST API Endpoints (app_celery.py — production)

| Endpoint | Method | Service | Status |
|---|---|---|---|
| `/api/upload-pdfs` | POST | DocumentService + Celery | ✅ FIXED (was calling wrong method) |
| `/api/jobs/{task_id}` | GET | Celery AsyncResult | ✅ OK |
| `/api/worker-stats` | GET | Celery Inspector | ✅ OK |
| `/api/courses` | GET | DatabaseServiceV2 / JSON | ✅ OK |
| `/api/course/{course_id}` | GET | DatabaseServiceV2 / JSON | ✅ OK |
| `/api/quiz/generate-module` | POST | QuizService | ⚠️ SEE BUGS |
| `/api/quiz/generate-course` | POST | QuizService | ⚠️ SEE BUGS |
| `/api/quiz/submit` | POST | QuizService | ✅ OK |
| `/api/quiz/{quiz_id}` | GET | QuizService | ✅ OK |
| `/api/chat` | POST | ChatService | ✅ OK |
| `/api/chat-with-audio` | POST | ChatService + AudioService | ✅ OK (REST version) |
| `/api/transcribe` | POST | AudioService | ✅ OK |
| `/api/start-class` | POST | TeachingService + AudioService | ✅ OK (REST version) |
| `/api/session/check` | GET | SessionManager | ✅ OK |
| `/api/session/create` | POST | SessionManager | ✅ OK |
| `/api/session/end` | POST | SessionManager | ✅ OK |
| `/api/session/history` | GET | SessionManager | ✅ OK |
| `/api/admin/user/{id}/quiz-stats` | GET | DatabaseServiceV2 | ✅ OK |
| `/api/admin/users` | GET | DatabaseServiceV2 | ✅ OK |
| `/api/admin/users/{id}` | GET | DatabaseServiceV2 | ✅ OK |
| `/api/admin/dashboard` | GET | DatabaseServiceV2 | ✅ OK |
| `/api/assessment/upload-and-generate` | POST | AssessmentService | ✅ OK |
| `/api/assessment/{id}` | GET | AssessmentService | ✅ OK |
| `/api/assessment/submit` | POST | AssessmentService | ✅ OK |
| `/api/assessment/user/{id}` | GET | AssessmentService | ✅ OK |
| `/api/assessment/{id}/attempts/{uid}` | GET | AssessmentService | ✅ OK |
| `/api/progress/mark-complete` | POST | DatabaseServiceV2 | ✅ OK |
| `/api/progress/user/{uid}/course/{cid}` | GET | DatabaseServiceV2 | ✅ OK |
| `/health` | GET | Health Check | ✅ OK |

### WebSocket Handlers (websocket_server.py)

| Message Type | Handler | Description | Status |
|---|---|---|---|
| `ping` | `handle_ping` | Connection test | ✅ OK |
| `chat_with_audio` | `handle_chat_with_audio` | Chat + TTS streaming | ⚠️ NEEDS IMPROVEMENT (no chunk accumulation, no barge-in) |
| `start_class` | `handle_start_class` | Simple one-way teaching | ⚠️ NEEDS RENAME → keep as simple mode |
| `interactive_teaching` | `handle_interactive_teaching` | Two-way voice teaching with barge-in | ✅ RECENTLY IMPROVED |
| `stt_audio_chunk` | `handle_stt_audio_chunk` | Forward audio to Deepgram STT | ✅ OK |
| `continue_teaching` | `handle_continue_teaching` | Resume after Q&A | ✅ OK |
| `end_teaching` | `handle_end_teaching` | Cleanup teaching session | ✅ OK |
| `audio_only` | `handle_audio_only` | TTS-only generation | ✅ OK |
| `transcribe_audio` | `handle_transcribe_audio` | Audio transcription | ✅ OK |
| `set_language` | `handle_set_language` | Change TTS language | ✅ OK |
| `get_metrics` | `handle_get_metrics` | Performance metrics | ✅ OK |

### Backend Services

| Service File | Purpose | DB Service Used | Status |
|---|---|---|---|
| `document_service.py` | PDF processing + course gen | `database_service_actual` | ✅ FIXED |
| `async_document_service.py` | Async wrapper for above | via DocumentService | ✅ FIXED (quiz auto-gen added) |
| `quiz_service.py` | Quiz gen + evaluation | `database_service_v2` | ✅ FIXED (course_id key) |
| `chat_service.py` | RAG chat | - | ✅ OK |
| `audio_service.py` | TTS orchestration | - | ✅ OK |
| `teaching_service.py` | LLM teaching content gen | - | ✅ OK |
| `assessment_service.py` | Notes assessment | `database_service_v2` | ✅ OK |
| `session_manager.py` | Session + message tracking | `database_service_v2` | ✅ OK |
| `realtime_orchestrator.py` | Interactive teaching state | Redis | ✅ OK |
| `langgraph_teaching_agent.py` | LangGraph agent | - | ✅ OK |
| `deepgram_stt_service.py` | Speech-to-text | - | ✅ OK |
| `sarvam_service.py` | Sarvam TTS | - | ✅ OK |
| `elevenlabs_service.py` | ElevenLabs TTS | - | ✅ OK |
| `rag_service.py` | RAG retrieval | ChromaDB | ✅ OK |
| `llm_service.py` | OpenAI LLM | - | ✅ OK |
| `semantic_router_service.py` | Intent routing | - | ✅ OK |

### Database Service Files (4 files — INCONSISTENCY)

| File | Tech | Used By | Status |
|---|---|---|---|
| `database_service.py` | Placeholder (disabled) | Nothing (legacy) | ❌ DEAD CODE |
| `database_service_actual.py` | SQLAlchemy ORM | DocumentService (course creation) | ✅ FIXED |
| `database_service_new.py` | SQLAlchemy ORM (copy?) | Nothing? | ❌ LIKELY DEAD CODE |
| `database_service_v2.py` | psycopg2 raw SQL | QuizService, SessionManager, app_celery, AssessmentService, Progress | ✅ PRIMARY |

---

## 2. Bugs Found & Fixed (Previous Session)

### BUG-1: Celery task called wrong method [CRITICAL] ✅ FIXED
- **File:** `tasks/pdf_processing.py:100`
- **Issue:** Called `process_pdfs_and_generate_course` (async, expects UploadFile) instead of `process_pdf_files_from_paths` (sync, expects file path dicts)
- **Effect:** Coroutine returned but never awaited → course never generated

### BUG-2: Missing sqlalchemy.text import [CRITICAL] ✅ FIXED
- **File:** `services/database_service_actual.py:11`
- **Issue:** `create_course` uses `session.execute(text(...))` but `text` wasn't imported
- **Effect:** NameError crash when saving course to DB

### BUG-3: Quiz course_id key mismatch [CRITICAL] ✅ FIXED
- **File:** `services/quiz_service.py:86,137`
- **Issue:** Used `course_content.get('id')` but document service uses `'course_id'` key
- **Effect:** Quiz never saved to DB (course_id was always None)

### BUG-4: Quiz never auto-generated [MEDIUM] ✅ FIXED
- **Files:** `async_document_service.py`, `tasks/pdf_processing.py`
- **Issue:** Quiz generation was only a separate API call, never triggered after course creation
- **Fix:** Added auto quiz generation after course creation in both paths

### BUG-5: Missing country column in ORM [MINOR] ✅ FIXED
- **File:** `services/database_service_actual.py`
- **Issue:** Course ORM model missing `country` column that exists in DB schema

---

## 3. Bugs Found & Fixed (Current Session)

### BUG-6: chat_with_audio WebSocket — no chunk accumulation ✅ FIXED
- **File:** `websocket_server.py` — `handle_chat_with_audio`
- **Issue:** Sends tiny TTS chunks (1-4KB) individually, causing audio gaps
- **Fix:** Applied same 16KB accumulation buffer as teaching audio

### BUG-7: chat_with_audio REST endpoint not streaming ⚠️ KNOWN
- **File:** `app.py:416-457`, `app_celery.py` equivalent
- **Issue:** REST `/api/chat-with-audio` generates full audio then returns as base64 blob — no streaming
- **Note:** WebSocket version is the primary path; REST is legacy — acceptable as-is

### BUG-8: start_class WebSocket — no chunk accumulation ✅ FIXED
- **File:** `websocket_server.py` — `handle_start_class`
- **Issue:** Same as BUG-6, sends tiny chunks individually
- **Fix:** Applied 16KB accumulation buffer

### BUG-9: Multiple database service files ✅ AUDITED
- `database_service.py` — ❌ DEAD CODE (placeholder, USE_DATABASE=False hardcoded)
- `database_service_actual.py` — Used by DocumentService for course creation (SQLAlchemy ORM)
- `database_service_new.py` — ❌ DEAD CODE (only referenced in test_setup.py)
- `database_service_v2.py` — ✅ PRIMARY (psycopg2 raw SQL, used by everything else)
- **Conclusion:** `database_service_actual` and `database_service_v2` both hit the same Neon DB. ORM is used for writes (course creation), psycopg2 for reads. Acceptable architecture.

### BUG-10: app.py quiz endpoints only read from JSON ⚠️ KNOWN
- **File:** `app.py:248-349`
- **Note:** `app_celery.py` is the production version and checks DB first — `app.py` is the simple/dev version

### BUG-11: No self-improvement / recommendation system ✅ BUILT
- **New file:** `services/recommendation_service.py`
- **New endpoint:** `GET /api/recommendations/{user_id}`
- **Features:** Weak module detection, quiz recommendations, next topics, next courses, natural-language summary

---

## 4. Improvements Made (Current Session)

### New WebSocket route: `start_class_interactive`
- Routes to the existing `handle_interactive_teaching` handler
- `start_class` remains as the simple one-way teaching mode
- `start_class_interactive` / `interactive_teaching` = two-way voice mode with barge-in

### Chat audio barge-in support
- Added `_chat_audio_gen` counter to `ProfAIAgent`
- Each new `chat_with_audio` request increments the counter
- Audio streaming loop checks counter — stops sending if a newer request has arrived

---

## 5. Database Service Usage Map

| Consumer | DB Service | Method |
|---|---|---|
| `document_service.py` (course creation) | `database_service_actual` (SQLAlchemy) | `create_course()` |
| `websocket_server.py` (course loading) | `database_service_v2` (psycopg2) | `get_course_with_content()` |
| `quiz_service.py` (quiz storage) | `database_service_v2` (psycopg2) | `create_quiz()`, `get_quiz()` |
| `session_manager.py` | `database_service_v2` (psycopg2) | Session + message CRUD |
| `assessment_service.py` | `database_service_v2` (psycopg2) | Assessment CRUD |
| `app_celery.py` (all endpoints) | `database_service_v2` (psycopg2) | All reads |
| `recommendation_service.py` | `database_service_v2` (psycopg2) | Progress + quiz analytics |

---

## 6. Action Items Summary

1. ✅ Fix document processing pipeline (Celery task, text import, course_id key)
2. ✅ Apply chunk accumulation to `handle_chat_with_audio` and `handle_start_class`
3. ✅ Add `start_class_interactive` WebSocket route
4. ✅ Add barge-in support to `handle_chat_with_audio`
5. ✅ Audit and document database service usage
6. ✅ Build self-improvement recommendation agent
7. ✅ Auto quiz generation after course creation
