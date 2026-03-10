# Schema Verification Report — NeonDB + ChromaDB Pipeline

## 1. NeonDB Actual Schema (from `get_neon_schema.py`)

### Critical Tables for Document Pipeline

| Table | Column | **Actual DB Type** |
|-------|--------|--------------------|
| `courses` | `id` | **INTEGER** (autoincrement) |
| `courses` | `teacher_id` | **INTEGER** (FK → users.id) |
| `courses` | `course_number` | **INTEGER** (nullable) |
| `courses` | `title` | TEXT NOT NULL |
| `courses` | `country` | TEXT (nullable) |
| `modules` | `id` | **INTEGER** (autoincrement) |
| `modules` | `course_id` | **INTEGER** (FK → courses.id) |
| `modules` | `week` | INTEGER NOT NULL |
| `topics` | `id` | **INTEGER** (autoincrement) |
| `topics` | `module_id` | **INTEGER** (FK → modules.id) |
| `quizzes` | `course_id` | **INTEGER** (FK → courses.id) |
| `quizzes` | `quiz_id` | VARCHAR(100) UNIQUE |
| `quiz_questions` | `quiz_id` | VARCHAR(100) (FK → quizzes.quiz_id) |
| `users` | `id` | **INTEGER** (autoincrement) |

### Row Counts
- courses: 18 | modules: 231 | topics: 1081 | quizzes: 92 | quiz_questions: 2380 | users: 307

---

## 2. ROOT CAUSE BUG — ORM Type Mismatch (BOTH repos)

### What was wrong in `database_service_actual.py`:

| ORM Model | Column | **Was (WRONG)** | **Actual DB** | **Fixed To** |
|-----------|--------|-----------------|---------------|--------------|
| `User.id` | id | `Column(Text)` UUID | INTEGER auto | `Column(Integer, autoincrement=True)` |
| `Course.id` | id | `Column(Text)` UUID | INTEGER auto | `Column(Integer, autoincrement=True)` |
| `Course.teacher_id` | teacher_id | `Column(Text)` | INTEGER FK | `Column(Integer, ForeignKey('users.id'))` |
| `Module.course_id` | course_id | `Column(Text)` | INTEGER FK | `Column(Integer, ForeignKey('courses.id'))` |
| `Quiz.course_id` | course_id | `Column(Text)` | INTEGER FK | `Column(Integer, ForeignKey('courses.id'))` |
| `QuizResponse.user_id` | user_id | `Column(Text)` | INTEGER FK | `Column(Integer, ForeignKey('users.id'))` |
| `UserProgress.user_id` | user_id | `Column(Text)` | INTEGER | `Column(Integer)` |
| `UserProgress.course_id` | course_id | `Column(Text)` | INTEGER | `Column(Integer)` |

### Impact of the bug:
1. `create_course()` generated `id=str(uuid.uuid4())` → tried to INSERT UUID string into INTEGER column → **ALWAYS FAILED**
2. `teacher_id='system'` → tried to INSERT string into INTEGER FK column → **ALWAYS FAILED**
3. Exception caught → silently fell back to JSON files
4. ChromaDB indexing step (inside `try` block) → **NEVER REACHED**
5. Quiz `create_quiz()` → FK to non-existent course → **ALSO FAILED**
6. Existing 18 courses in DB were from migration scripts, NOT from the pipeline

---

## 3. Fixes Applied

### Fix A: ORM Models → INTEGER types (BOTH repos)
- **File:** `services/database_service_actual.py`
- Changed all Text/UUID columns to Integer matching actual schema
- Added `country` column to OLD repo's Course model (was missing)

### Fix B: `create_course()` rewritten (BOTH repos)
- **Before:** Generated UUID, set `id=uuid`, `teacher_id='system'`
- **After:** Let DB autoincrement handle `id`, resolve `teacher_id` to valid integer via `_resolve_teacher_id()`
- `_resolve_teacher_id()`: tries int parse → looks up admin/teacher user → fallback to first user → absolute fallback 1

### Fix C: `create_quiz()` / `get_course()` updated (BOTH repos)
- `create_quiz()`: `course_id` parameter cast to `int()` before insertion
- `get_course()`: `course_id` parameter cast to `int()` for query filter

### Fix D: ChromaDB course-content indexing added (BOTH repos — from previous session)
- **File:** `services/document_service.py`
- STEP 6 added after NeonDB save: calls `cloud_vectorizer.add_course_content_to_vectorstore()`
- Now reachable because `create_course()` actually succeeds

### Fix E: OLD repo Celery task fixed (from previous session)
- **File:** `tasks/pdf_processing.py`
- Changed wrong `process_pdfs_and_generate_course()` (async) → `process_pdf_files_from_paths()` (sync)
- Added quiz auto-generation block

### Fix F: Quiz error logging improved (NEW repo — from previous session)
- Upgraded from WARNING to ERROR with full traceback
- Added `quiz_status` field to task result

---

## 4. Data Flow Verification (Post-Fix)

### Pipeline: Upload → NeonDB → ChromaDB → Quiz

```
POST /api/upload-pdfs
  → base64 encode → Celery task: process_pdf_and_generate_course
  
Celery Worker:
  → decode → temp files
  → document_service.process_pdf_files_from_paths()   ← BOTH repos now correct
    STEP 1: PDFExtractor → raw_docs
    STEP 2: TextChunker → doc_chunks
    STEP 3: CloudVectorizer.create_vector_store_from_documents(doc_chunks) → ChromaDB (raw chunks)
    STEP 4: CourseGenerator.generate_course() → structured course dict
    STEP 5: database_service_actual.create_course(course_dict, teacher_id='system')
            → _resolve_teacher_id('system') → finds admin/teacher user INTEGER id
            → INSERT INTO courses (title, teacher_id, course_number, country, ...)
            → INSERT INTO modules (course_id=INTEGER, week, title, ...)
            → INSERT INTO topics (module_id=INTEGER, title, content, ...)
            → returns course.id (INTEGER)
    STEP 6: cloud_vectorizer.add_course_content_to_vectorstore(course_for_chroma)
            → course_for_chroma['id'] = course_id (INTEGER)
            → int(course_id) → works ✅
            → metadata: {'course_id': int, 'course_name': str, 'module': str, 'week': int, ...}
            → ChromaDB documents with course_id metadata for RAG filtering
  
  → quiz_service.generate_course_quiz(result)
    → result.get('course_id') → INTEGER
    → _store_quiz(quiz, course_id=INTEGER)
      → database_service_v2.create_quiz(quiz_data, course_id=INTEGER)
        → INSERT INTO quizzes (quiz_id, course_id=INTEGER, ...) → FK valid ✅
        → INSERT INTO quiz_questions (...) → each question stored ✅
```

### RAG Query Flow (reads back):
```
rag_service.get_answer(question, course_id=INTEGER)
  → metadata_filter = {"course_id": INTEGER}      ← matches what we wrote ✅
  → hybrid_retriever with filter → ChromaDB query
  → returns filtered documents for that course
```

---

## 5. Metadata Consistency Check

| Step | Key | Type Written | Type Read | Match? |
|------|-----|-------------|-----------|--------|
| ChromaDB write (`cloud_vectorizer.py:176`) | `course_id` | `int(course_id)` → int | — | — |
| ChromaDB read (`rag_service.py:186`) | `course_id` | — | `course_id` (int) | ✅ |
| NeonDB write (`create_course`) | `courses.id` | INTEGER (autoincrement) | — | — |
| NeonDB read (`get_course`) | `courses.id` | — | `int(course_id)` | ✅ |
| Quiz write (`create_quiz`) | `quizzes.course_id` | `int(course_id)` | — | — |
| Quiz read (`get_quiz`) | `quizzes.course_id` | — | INTEGER | ✅ |

---

## 6. Files Modified

### NEW repo (`Prof_AI-8126/Prof_AI-8126/`)
- `services/database_service_actual.py` — ORM models + methods fixed to INTEGER
- `services/document_service.py` — STEP 6 ChromaDB indexing added
- `tasks/pdf_processing.py` — Quiz error logging improved

### OLD repo (`Prof_AI-8126-old/Prof_AI-8126/`)
- `services/database_service_actual.py` — ORM models + methods fixed to INTEGER + country column
- `services/document_service.py` — STEP 6 ChromaDB indexing added
- `tasks/pdf_processing.py` — Wrong method call fixed + quiz auto-gen added
