# Document Upload → Course/Quiz Generation Pipeline Analysis

## Full Pipeline Trace

```
POST /api/upload-pdfs (app_celery.py)
  → Base64-encode PDFs → Celery task: process_pdf_and_generate_course
        ↓
Celery Worker (tasks/pdf_processing.py)
  → Decode base64 → temp files
  → document_service.process_pdf_files_from_paths()  [NEW repo ✅]
  → document_service.process_pdfs_and_generate_course()  [OLD repo ❌ BROKEN]
        ↓
DocumentService.process_pdf_files_from_paths() (services/document_service.py)
  STEP 1: PDFExtractor → raw_docs
  STEP 2: TextChunker → doc_chunks
  STEP 3: CloudVectorizer.create_vector_store_from_documents(doc_chunks) → ChromaDB
           ⚠️ Raw PDF chunks only — NO course_id metadata
  STEP 4: CourseGenerator.generate_course() → structured course
  STEP 5: database_service_actual.create_course() → NeonDB
  ❌ MISSING: add_course_content_to_vectorstore() → ChromaDB with course_id
        ↓
Back in Celery task [NEW repo only]
  → QuizService.generate_course_quiz(result) → NeonDB
```

---

## ISSUES FOUND

### ISSUE A — [OLD REPO] CRITICAL: Wrong method called in pdf_processing.py

**File:** `Prof_AI-8126-old/.../tasks/pdf_processing.py:100`

```python
result = document_service.process_pdfs_and_generate_course(
    temp_files, course_title, country=country, progress_callback=...
)
```

**3 fatal problems:**
1. `process_pdfs_and_generate_course()` is **async** — calling without `await` returns a coroutine, not results
2. Expects `List[UploadFile]` objects, NOT `List[dict]` with path/filename
3. Doesn't accept `country` or `progress_callback` → immediate `TypeError`

**NEW repo correctly calls** `process_pdf_files_from_paths()` (sync, correct params).

### ISSUE B — [BOTH REPOS] Missing course-content → ChromaDB indexing

`CloudVectorizer.add_course_content_to_vectorstore(course_data)` **EXISTS** in `cloud_vectorizer.py:110` with full implementation (course_id metadata, batching, dedup) but is **NEVER CALLED** in the pipeline.

**Impact:** RAG cannot filter by course_id for newly uploaded courses.

### ISSUE C — [NEW REPO] Quiz errors swallowed silently

Quiz auto-gen failures logged as `WARNING` only — invisible to users checking job status.

### ISSUE D — [OLD REPO] No quiz auto-generation

OLD repo lacks the quiz auto-gen block entirely.

---

## FIX PLAN

| # | Fix | Repo | File |
|---|-----|------|------|
| 1 | Add ChromaDB course-content indexing after NeonDB save | BOTH | `services/document_service.py` |
| 2 | Fix wrong method call | OLD | `tasks/pdf_processing.py` |
| 3 | Add quiz auto-generation | OLD | `tasks/pdf_processing.py` |
| 4 | Improve quiz error reporting | NEW | `tasks/pdf_processing.py` |

---

## Database Services Map

| Service | Backend | Used By |
|---------|---------|---------|
| `database_service_actual.py` | SQLAlchemy ORM | `DocumentService` (course creation) |
| `database_service_v2.py` | psycopg2 raw SQL | `app_celery.py`, `QuizService` |
| `CloudVectorizer` | ChromaDB Cloud | `DocumentService` (vector storage) |
