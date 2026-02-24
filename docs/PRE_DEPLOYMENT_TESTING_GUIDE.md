# 🧪 PRE-DEPLOYMENT TESTING GUIDE
## Complete Testing Checklist Before AWS Deployment

**Time Required:** ~30-45 minutes  
**Prerequisites:** Database URL, Redis URL, API keys configured

---

## 📋 TESTING PHASES

### Phase 1: Environment Setup (5 minutes)
### Phase 2: Database Connection (5 minutes)
### Phase 3: Service Verification (10 minutes)
### Phase 4: Local Application Testing (15 minutes)
### Phase 5: Integration Testing (10 minutes)

---

## 🔧 PHASE 1: ENVIRONMENT SETUP

### Step 1.1: Verify .env File

**File:** `.env` in project root

**Required Variables:**
```env
# OpenAI (REQUIRED)
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE

# Database (REQUIRED for DB mode)
USE_DATABASE=True
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/profai?sslmode=require

# Redis (REQUIRED for Celery)
REDIS_URL=rediss://default:pass@xxx.upstash.io:6379

# Optional APIs
SARVAM_API_KEY=your_sarvam_key
GROQ_API_KEY=your_groq_key

# Vector Store
USE_CHROMA_CLOUD=True
CHROMA_CLOUD_API_KEY=your_chroma_key  # if using ChromaDB Cloud
```

**Verify:**
```bash
# Check if .env file exists
ls -l .env

# View variables (sensitive data masked)
cat .env | grep -v "KEY=" | grep -v "URL="
```

**Expected:**
```
✅ .env file exists
✅ USE_DATABASE=True
✅ Required keys are set
```

---

## 🗄️ PHASE 2: DATABASE CONNECTION TESTING

### Step 2.1: Test Database Integration Script

**Command:**
```bash
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI
python test_database_integration.py
```

**Expected Output:**
```
============================================================
DATABASE INTEGRATION TEST SUITE
============================================================
Database URL: postgresql://...@neon.tech/profai...
USE_DATABASE: True

============================================================
TEST 1: Database Connection
============================================================
✅ Database service initialized successfully
✅ Connected to: postgresql://...

============================================================
TEST 2: List Existing Courses
============================================================
✅ Found X courses in database:
   1. [abc12345...] Course Title (3 modules)
   ... (if courses exist)

============================================================
TEST 3: Create Test Course
============================================================
✅ Course created successfully!
   Course ID: a1b2c3d4-5e6f-7890-abcd-1234567890ef
   Title: Database Integration Test Course
   Modules: 2

============================================================
TEST 4: Retrieve Course
============================================================
✅ Course retrieved successfully!
   Course ID: a1b2c3d4-5e6f-7890-abcd-1234567890ef
   Title: Database Integration Test Course
   Modules: 2
   Module 1: Test Module 1 (2 topics)
   Module 2: Test Module 2 (1 topics)

============================================================
TEST 5: Create Quiz
============================================================
✅ Quiz created successfully!
   Quiz ID: test_quiz_db_integration
   Title: Database Integration Quiz
   Questions: 2

============================================================
TEST 6: Retrieve Quiz
============================================================
✅ Quiz retrieved successfully!
   Quiz ID: test_quiz_db_integration
   Title: Database Integration Quiz
   Course ID: a1b2c3d4-5e6f-7890-abcd-1234567890ef
   Questions: 2
   Q1: What is the purpose of this test?...
   Q2: Which database are we using?...

============================================================
TEST SUMMARY
============================================================
✅ Database Connection: PASSED
✅ List Courses: PASSED (X courses found)
✅ Create Course: PASSED (ID: a1b2c3d4...)
✅ Retrieve Course: PASSED
✅ Create Quiz: PASSED (ID: test_quiz_db_integration)
✅ Retrieve Quiz: PASSED

============================================================
🎉 ALL TESTS PASSED! Database integration is working!
============================================================
```

**If Tests FAIL:**
```
❌ Database Connection: FAILED
   Check: USE_DATABASE=True in .env
   Check: DATABASE_URL is correct
```

**Action:** Fix DATABASE_URL in .env and retry

---

### Step 2.2: Verify Database Directly (Optional)

**Using Neon Console:**
```sql
-- Go to https://console.neon.tech
-- Select your project
-- Go to SQL Editor

-- 1. Check if test data exists
SELECT id, title FROM courses ORDER BY created_at DESC LIMIT 5;

-- Expected: Should see "Database Integration Test Course"

-- 2. Check quizzes
SELECT quiz_id, title, course_id FROM quizzes ORDER BY created_at DESC LIMIT 5;

-- Expected: Should see "Database Integration Quiz"

-- 3. Verify foreign keys work
SELECT 
    c.title as course_title,
    q.title as quiz_title
FROM courses c
LEFT JOIN quizzes q ON c.id = q.course_id
LIMIT 5;

-- Expected: Courses linked to quizzes
```

---

## ✅ PHASE 3: SERVICE VERIFICATION

### Step 3.1: Test All Services

**Command:**
```bash
python test_all_services.py
```

**Expected Output:**
```
============================================================
COMPREHENSIVE SERVICE VERIFICATION
============================================================

============================================================
TEST 1: Service Imports
============================================================
✅ AudioService                - Import successful
✅ ChatService                 - Import successful
✅ DocumentService             - Import successful
✅ AsyncDocumentService        - Import successful
✅ LLMService                  - Import successful
✅ QuizService                 - Import successful
✅ RAGService                  - Import successful
✅ SarvamService               - Import successful
✅ TeachingService             - Import successful
✅ TranscriptionService        - Import successful
✅ DatabaseService             - Import successful

============================================================
TEST 2: Service Initialization
============================================================
✅ DocumentService              - Initialized (with database)
✅ AsyncDocumentService         - Initialized (with database)
✅ QuizService                  - Initialized (with database)
✅ LLMService                   - Initialized
✅ AudioService                 - Initialized
✅ TeachingService              - Initialized
✅ SarvamService                - Initialized
✅ TranscriptionService         - Initialized
⚠️  ChatService                  - Warning: No vector store...
✅ DatabaseService              - Initialized (Connected to DB)

============================================================
TEST 3: Database Integration
============================================================
USE_DATABASE setting: True
✅ DocumentService has database integration
✅ AsyncDocumentService has database integration
✅ QuizService has database integration

============================================================
TEST 4: Model Schemas
============================================================
✅ CourseLMS accepts INTEGER course_id
✅ CourseLMS accepts TEXT UUID course_id
✅ QuizRequest accepts INTEGER course_id
✅ QuizRequest accepts TEXT UUID course_id

============================================================
TEST 5: Configuration
============================================================
Critical Configuration:
✅ OPENAI_API_KEY        - Set (sk-proj-...)
✅ DATABASE_URL          - Set (postgresql...)
✅ REDIS_URL             - Set (rediss://...)
✅ USE_DATABASE          - Set (True)

Optional Configuration:
✅ SARVAM_API_KEY        - Set (your_key...)
✅ GROQ_API_KEY          - Set (gsk_...)
✅ USE_CHROMA_CLOUD      - Set (True)

============================================================
TEST SUMMARY
============================================================
✅ Imports              - PASSED
✅ Initialization       - PASSED
✅ Database Integration - PASSED
✅ Model Schemas        - PASSED
✅ Configuration        - PASSED

============================================================
🎉 ALL TESTS PASSED! All services are working correctly!
============================================================
```

**If Tests FAIL:**
- Check missing API keys
- Verify import paths
- Check for syntax errors

---

## 🚀 PHASE 4: LOCAL APPLICATION TESTING

### Step 4.1: Start Celery Worker

**Terminal 1:**
```bash
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI
celery -A celery_app worker --loglevel=info --pool=solo
```

**Expected Output:**
```
-------------- celery@YOUR_COMPUTER v5.x.x
--- ***** -----
-- ******* ---- Windows-10.x.x
- *** --- * ---
- ** ---------- [config]
- ** ---------- .> app:         profai:0x...
- ** ---------- .> transport:   redis://...
- ** ---------- .> results:     redis://...
- *** --- * --- .> concurrency: 1 (solo)
-- ******* ---- .> task events: OFF
--- ***** -----

[tasks]
  . tasks.pdf_processing.process_pdf_and_generate_course
  . tasks.quiz_generation.generate_quiz_from_content

✅ Celery: Using Redis URL: rediss://...@upstash.io:6379
[2025-11-30 14:25:00,123: INFO/MainProcess] Connected to redis://...
[2025-11-30 14:25:00,456: INFO/MainProcess] mingle: searching for neighbors
[2025-11-30 14:25:01,789: INFO/MainProcess] mingle: all alone
[2025-11-30 14:25:01,890: INFO/MainProcess] celery@YOUR_COMPUTER ready.
```

**Key Things to Look For:**
- ✅ Connected to Redis (Upstash)
- ✅ Tasks registered
- ✅ Worker ready
- ❌ NO connection errors

---

### Step 4.2: Start Application Server

**Terminal 2:**
```bash
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI
python run_profai_websocket_celery.py
```

**Expected Output:**
```
🚀 Starting ProfAI with Celery Integration...

Loading environment variables...
✅ Environment loaded

Initializing services...
INFO: DocumentService initialized with database support
INFO: QuizService initialized with database support
INFO: AsyncDocumentService initialized with database support
✅ Services initialized

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5001 (Press CTRL+C to quit)

🎉 ProfAI server is running!
📡 API: http://localhost:5001
📚 Docs: http://localhost:5001/docs
🔌 WebSocket: ws://localhost:8765
```

**Critical Log Messages to Look For:**
```
✅ DocumentService initialized with database support
✅ QuizService initialized with database support
✅ AsyncDocumentService initialized with database support
```

**If you see:**
```
INFO: DocumentService initialized (JSON mode)
```
**This means:** Database is NOT enabled. Check USE_DATABASE in .env

---

### Step 4.3: Test API Endpoints

**Terminal 3:**

**Test 1: Health Check**
```bash
curl http://localhost:5001/
```
**Expected:**
```json
{"message":"ProfAI API is running!"}
```

**Test 2: Get Courses**
```bash
curl http://localhost:5001/api/courses
```
**Expected:**
```json
[
  {
    "course_id": "a1b2c3d4-...",  // UUID if from database
    "course_title": "Course Title",
    "modules": [...]
  }
]
```

**Test 3: Get API Docs**
```
Open browser: http://localhost:5001/docs
```
**Expected:** Swagger UI with all endpoints listed

---

## 🔗 PHASE 5: INTEGRATION TESTING

### Step 5.1: Test PDF Upload & Course Generation

**Prepare a test PDF:**
```bash
# Use any small PDF file (< 5MB)
# Example: test.pdf
```

**Upload via API:**
```bash
curl -X POST http://localhost:5001/api/upload-pdfs-async \
  -F "files=@test.pdf" \
  -F "course_title=Integration Test Course"
```

**Expected Response:**
```json
{
  "job_id": "abc-123-def",
  "status": "pending",
  "message": "PDF processing started"
}
```

**Check Job Status:**
```bash
curl http://localhost:5001/api/job-status/abc-123-def
```

**Expected (After ~30-60 seconds):**
```json
{
  "job_id": "abc-123-def",
  "status": "completed",
  "progress": 100,
  "result": {
    "course_id": "xyz-789-uvw",  // UUID from database
    "course_title": "Integration Test Course",
    "modules": 3
  }
}
```

**Check Logs (Terminal 2):**
```
INFO: STEP 1: Extracting text from PDFs...
INFO: STEP 2: Chunking documents...
INFO: STEP 3: Creating vector store...
INFO: STEP 4: Generating course...
INFO: STEP 5: Saving course...
INFO: ✅ Course saved to database! Course ID: xyz-789-uvw
INFO: Course generation completed successfully!
```

**Verify in Database:**
```sql
-- In Neon Console
SELECT id, title FROM courses ORDER BY created_at DESC LIMIT 1;
-- Should show: Integration Test Course
```

---

### Step 5.2: Test Quiz Generation

**Generate Module Quiz:**
```bash
curl -X POST http://localhost:5001/api/quiz/generate-module \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "xyz-789-uvw",
    "quiz_type": "module",
    "module_week": 1
  }'
```

**Expected Response:**
```json
{
  "message": "Module quiz generated successfully",
  "quiz": {
    "quiz_id": "quiz_xyz_module_1",
    "title": "Module 1 Quiz",
    "questions": [
      {
        "question_id": "q1",
        "question_text": "What is...",
        "options": ["A", "B", "C", "D"]
      },
      // ... 19 more questions
    ],
    "total_questions": 20
  }
}
```

**Check Logs:**
```
INFO: Generating module quiz for week 1
INFO: ✅ Quiz quiz_xyz_module_1 saved to database (course: xyz-789-uvw)
```

**Verify in Database:**
```sql
SELECT quiz_id, title, course_id FROM quizzes ORDER BY created_at DESC LIMIT 1;
-- Should show: quiz_xyz_module_1 linked to course xyz-789-uvw
```

---

### Step 5.3: Test Chat/RAG (If Vector Store Configured)

**Send Chat Message:**
```bash
curl -X POST http://localhost:5001/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is this course about?",
    "language": "en-IN"
  }'
```

**Expected Response:**
```json
{
  "response": "Based on the course content...",
  "language": "en-IN"
}
```

---

## ✅ SUCCESS CRITERIA

### Before Proceeding to AWS Deployment, Ensure:

**Database Tests:**
- [x] ✅ Database connection successful
- [x] ✅ Can create courses in database
- [x] ✅ Can retrieve courses from database
- [x] ✅ Can create quizzes in database
- [x] ✅ Can retrieve quizzes from database
- [x] ✅ Foreign keys work (quiz → course)

**Service Tests:**
- [x] ✅ All services import successfully
- [x] ✅ All services initialize correctly
- [x] ✅ Database-integrated services show "(with database)"
- [x] ✅ Model schemas accept both int and UUID course_id

**Application Tests:**
- [x] ✅ Celery worker connects to Redis
- [x] ✅ Application starts without errors
- [x] ✅ Logs show "initialized with database support"
- [x] ✅ API endpoints respond correctly
- [x] ✅ Health check returns 200 OK

**Integration Tests:**
- [x] ✅ PDF upload creates course in database
- [x] ✅ Course ID is UUID (not integer)
- [x] ✅ Quiz generation saves to database
- [x] ✅ Quiz links to course via foreign key
- [x] ✅ APIs return data from database

---

## ❌ COMMON ISSUES & SOLUTIONS

### Issue 1: Database Connection Failed
```
❌ Database Connection: FAILED
```

**Solutions:**
```bash
# Check DATABASE_URL
echo $env:DATABASE_URL

# Verify Neon database is active
# Go to: https://console.neon.tech

# Test connection
psql "$DATABASE_URL"
# Should connect successfully

# Fix .env
USE_DATABASE=True
DATABASE_URL=postgresql://...@neon.tech/profai?sslmode=require
```

---

### Issue 2: Services Not Using Database
```
INFO: DocumentService initialized (JSON mode)
```

**Solution:**
```bash
# Check USE_DATABASE
cat .env | grep USE_DATABASE
# Should be: USE_DATABASE=True (not False)

# Restart application
# Kill and restart run_profai_websocket_celery.py
```

---

### Issue 3: Celery Worker Can't Connect to Redis
```
[ERROR/MainProcess] consumer: Cannot connect to redis://localhost:6379
```

**Solution:**
```bash
# Check REDIS_URL
echo $env:REDIS_URL

# Should be: rediss://...@upstash.io:6379
# NOT: redis://localhost:6379

# Fix .env
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST.upstash.io:6379

# Restart Celery worker
```

---

### Issue 4: Course ID is Integer (Not UUID)
```json
{"course_id": 1}  // ❌ Wrong - should be UUID
```

**Solution:**
```bash
# Verify USE_DATABASE=True
cat .env | grep USE_DATABASE

# Check logs for:
INFO: ✅ Course saved to database! Course ID: abc-123...
# NOT:
INFO: ✅ Course saved to JSON! Course ID: 1

# If saving to JSON, database is not enabled
```

---

### Issue 5: API Key Missing
```
❌ Configuration - OPENAI_API_KEY: NOT SET
```

**Solution:**
```bash
# Add to .env
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE

# Restart application
```

---

## 📊 TESTING CHECKLIST

**Copy and mark as you test:**

```
PHASE 1: ENVIRONMENT
[ ] .env file exists
[ ] USE_DATABASE=True
[ ] DATABASE_URL set
[ ] REDIS_URL set
[ ] OPENAI_API_KEY set

PHASE 2: DATABASE
[ ] test_database_integration.py passes
[ ] All 6 tests PASSED
[ ] Database connection successful
[ ] Course created with UUID
[ ] Quiz created and linked

PHASE 3: SERVICES
[ ] test_all_services.py passes
[ ] All imports successful
[ ] All services initialized
[ ] Database integration confirmed
[ ] Model schemas accept both types

PHASE 4: APPLICATION
[ ] Celery worker connects to Redis
[ ] Application starts successfully
[ ] Logs show "with database support"
[ ] API endpoints respond
[ ] /docs accessible

PHASE 5: INTEGRATION
[ ] PDF upload works
[ ] Course saved to database (UUID)
[ ] Quiz generation works
[ ] Quiz saved to database
[ ] Quiz links to course

VERIFICATION
[ ] All tests passed
[ ] No error messages in logs
[ ] Database contains test data
[ ] Application runs smoothly
```

---

## 🚀 READY FOR AWS DEPLOYMENT?

**If ALL tests passed:**
```
✅ Local testing complete
✅ Database integration working
✅ All services functional
✅ Ready for K8s/AWS deployment
```

**Next Steps:**
1. Review `TODO_BEFORE_DEPLOY.md`
2. Encode K8s secrets
3. Deploy to Kubernetes
4. Deploy to AWS EKS

---

## 📞 QUICK TEST COMMANDS

```bash
# Test 1: Database Integration
python test_database_integration.py

# Test 2: All Services
python test_all_services.py

# Test 3: Start Celery
celery -A celery_app worker --loglevel=info --pool=solo

# Test 4: Start App
python run_profai_websocket_celery.py

# Test 5: Health Check
curl http://localhost:5001/

# Test 6: Get Courses
curl http://localhost:5001/api/courses
```

---

**Expected Total Time:** 30-45 minutes  
**Required:** Database, Redis, API keys configured  
**Result:** Complete confidence before AWS deployment! 🎉
