# 🧪 LOCAL TESTING GUIDE

Test all changes locally before deploying to EC2.

---

## 📋 **CHANGES TO TEST**

1. ✅ **Conversational Chat** - LangChain memory
2. ✅ **Hybrid RAG** - Vector + BM25 + Reranking
3. ✅ **Quiz Generation** - Improved parsing
4. ✅ **Document Upload** - ChromaDB verification

---

## 🔧 **STEP 1: INSTALL DEPENDENCIES**

Open PowerShell in your project directory:

```powershell
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Install new dependencies
pip install sentence-transformers==2.2.2
pip install rank-bm25==0.2.2
pip install langchain==0.1.0

# Verify installation
pip list | Select-String -Pattern "sentence|rank|langchain"
```

Expected output:
```
langchain                  0.1.0
rank-bm25                  0.2.2
sentence-transformers      2.2.2
```

---

## 🚀 **STEP 2: START LOCAL SERVER**

### **Option A: Direct Python (Recommended for Testing)**

```powershell
# Make sure .env is configured
# Check if you have all API keys set
Get-Content .env | Select-String -Pattern "API_KEY"

# Start FastAPI server
python -m uvicorn app_celery:app --host 0.0.0.0 --port 5001 --reload
```

### **Option B: Docker (if you prefer)**

```powershell
docker-compose up -d
docker logs -f profai-api
```

---

## ✅ **STEP 3: VERIFY SERVER IS RUNNING**

Open another PowerShell window:

```powershell
# Test health endpoint
curl http://localhost:5001/health

# Should return: {"status": "healthy"}
```

Or open in browser: `http://localhost:5001/docs`

---

## 🧪 **TEST 1: HYBRID RAG RETRIEVAL**

### **A. Check Logs for Initialization**

Watch your server logs. You should see:

```
📚 Creating hybrid retriever with X documents for BM25
✅ Cross-encoder reranker initialized
✅ Hybrid retriever with vector + BM25 + reranking initialized
✅ Vectorstore loaded and RAG chain initialized
```

If you see warnings:
```
⚠️ Could not initialize BM25 retriever: ...
ℹ️ Using vector-only (BM25 unavailable)
```

**This is OK!** It means no documents are loaded yet. System falls back to vector-only.

---

### **B. Test RAG Query**

```powershell
# Test chat endpoint (uses RAG)
curl -X POST http://localhost:5001/api/chat `
  -H 'Content-Type: application/json' `
  -d '{\"message\": \"What is machine learning?\", \"language\": \"en-IN\"}'
```

**Watch the logs** for:
```
🔍 Hybrid retrieval for query: 'What is machine learning?'
  📊 Vector search: X docs
  📊 BM25 search: X docs      ← Should see this if BM25 is working
🔀 RRF merged X vector + X BM25 = X unique docs
🎯 Reranked X docs, top score: 0.XXXX
  ✅ Final: 4 documents
    1. [source.pdf] Preview of document...
```

---

## 🧪 **TEST 2: CONVERSATIONAL CHAT MEMORY**

### **A. Create Session and Test Context**

```powershell
# Message 1: Ask about Python
curl -X POST http://localhost:5001/api/chat `
  -H 'Content-Type: application/json' `
  -d '{\"message\": \"What is Python?\", \"language\": \"en-IN\", \"session_id\": \"test_session_001\"}'
```

**Watch logs** for:
```
Chat query: What is Python?... (session: test_session_001)
```

---

```powershell
# Message 2: Follow-up (should remember Python)
curl -X POST http://localhost:5001/api/chat `
  -H 'Content-Type: application/json' `
  -d '{\"message\": \"Show me an example\", \"language\": \"en-IN\", \"session_id\": \"test_session_001\"}'
```

**Watch logs** for:
```
💬 Using conversation context from memory
Chat query: Show me an example... (session: test_session_001)
```

**Expected response:** Should give a Python example (not ask "example of what?")

---

```powershell
# Message 3: Different session (should NOT remember)
curl -X POST http://localhost:5001/api/chat `
  -H 'Content-Type: application/json' `
  -d '{\"message\": \"Show me an example\", \"language\": \"en-IN\", \"session_id\": \"different_session\"}'
```

**Expected response:** Should ask "example of what?" (no context from previous session)

---

## 🧪 **TEST 3: QUIZ GENERATION**

### **Prerequisite:** You need a course in your database or `course_output.json`

```powershell
# Test course quiz generation
curl -X POST http://localhost:5001/api/quiz/generate-course `
  -H 'Content-Type: application/json' `
  -d '{\"course_id\": 5, \"module_week\": 1}'
```

**Watch logs** for:
```
Generating 40-question course quiz
Sending part 1 quiz prompt to LLM...
LLM Response Part 1 (first 500 chars): Q1. ...
Parsed 20 questions from part 1
Sending part 2 quiz prompt to LLM...
Parsed 20 questions from part 2
Quiz generated successfully with 40 questions
```

**Check response:**
```json
{
  "quiz_id": "...",
  "total_questions": 40,  // NOT 0!
  "questions": [...]
}
```

---

## 🧪 **TEST 4: DOCUMENT UPLOAD & CHROMADB VERIFICATION**

### **Upload a PDF**

```powershell
# Create test request (replace with actual file path)
$pdfPath = "C:\path\to\your\test.pdf"
$bytes = [System.IO.File]::ReadAllBytes($pdfPath)
$base64 = [Convert]::ToBase64String($bytes)

# Upload PDF
curl -X POST http://localhost:5001/api/courses/upload `
  -H 'Content-Type: application/json' `
  -d "{\"pdf_files\": [{\"filename\": \"test.pdf\", \"content\": \"$base64\"}], \"course_title\": \"Test Course\"}"
```

**Watch logs** for:
```
STEP 1: Saving uploaded files...
STEP 2: Extracting text and chunking...
STEP 3: Creating vector store...
Creating/updating ChromaDB Cloud collection 'profai_documents' with X documents.
Processing batch 1: 200 documents
✅ VERIFICATION: ChromaDB now contains X total documents
📋 Sample documents in collection:
   1. Chapter 1: Introduction...
   2. Section 2.1: ...
```

---

## 🧪 **TEST 5: CHAT WITH AUDIO**

```powershell
curl -X POST http://localhost:5001/api/chat-with-audio `
  -H 'Content-Type: application/json' `
  -d '{\"message\": \"Explain neural networks\", \"language\": \"en-IN\", \"session_id\": \"audio_test\"}'
```

**Expected response:**
```json
{
  "answer": "...",
  "audio_url": "http://localhost:5001/audio/...",
  "session_id": "audio_test"
}
```

---

## 📊 **VERIFICATION CHECKLIST**

After running all tests, verify:

### **✅ Hybrid RAG Working:**
- [ ] Logs show "Vector search: X docs"
- [ ] Logs show "BM25 search: X docs" (if documents loaded)
- [ ] Logs show "RRF merged"
- [ ] Logs show "Reranked X docs, top score: Y"
- [ ] Logs show final 4 documents with previews

### **✅ Conversational Chat Working:**
- [ ] Logs show "Chat query: ... (session: test_session_001)"
- [ ] Logs show "💬 Using conversation context from memory"
- [ ] Follow-up questions understand context
- [ ] Different sessions are isolated

### **✅ Quiz Generation Working:**
- [ ] Logs show "Parsed 20 questions from part 1"
- [ ] Logs show "Parsed 20 questions from part 2"
- [ ] Response has `"total_questions": 40`
- [ ] Questions array is not empty

### **✅ Document Upload Working:**
- [ ] Logs show "✅ VERIFICATION: ChromaDB now contains X documents"
- [ ] Logs show sample documents
- [ ] No upload errors

---

## 🔧 **TROUBLESHOOTING**

### **Issue: ImportError for sentence_transformers**

```powershell
pip install sentence-transformers rank-bm25
```

Restart server.

---

### **Issue: "Could not initialize BM25 retriever"**

**Expected on first run** if no documents are in ChromaDB.

**To fix:** Upload a PDF document. After upload, BM25 will work.

**Temporary workaround:** System falls back to vector-only (still works!).

---

### **Issue: "ChromaDB collection is EMPTY"**

You need to upload course content first:
1. Use the PDF upload endpoint
2. Or ensure `course_output.json` exists with course data

---

### **Issue: Quiz returns 0 questions**

Check logs for:
```
LLM Response Part 1 (first 500 chars): ...
```

If response doesn't match expected format:
- LLM might be returning different format
- Check `quiz_service.py` parser logs

---

### **Issue: Conversation doesn't remember**

Check:
1. Same `session_id` is being sent in both requests
2. Logs show: `(session: your_session_id)`
3. Logs show: `💬 Using conversation context`

If missing, check `chat_service.py` is updated.

---

### **Issue: Server won't start**

```powershell
# Check if port 5001 is in use
netstat -ano | findstr :5001

# Kill process if needed
taskkill /PID <PID> /F

# Restart server
python -m uvicorn app_celery:app --host 0.0.0.0 --port 5001 --reload
```

---

## 🎯 **MINIMAL TEST SEQUENCE**

If you want to test everything quickly:

```powershell
# 1. Start server
python -m uvicorn app_celery:app --host 0.0.0.0 --port 5001 --reload

# 2. In another terminal, test conversational chat
curl -X POST http://localhost:5001/api/chat -H 'Content-Type: application/json' -d '{\"message\": \"What is AI?\", \"language\": \"en-IN\", \"session_id\": \"quick_test\"}'

curl -X POST http://localhost:5001/api/chat -H 'Content-Type: application/json' -d '{\"message\": \"Give me an example\", \"language\": \"en-IN\", \"session_id\": \"quick_test\"}'

# 3. Check logs for:
# - "💬 Using conversation context from memory" ✅
# - "🔍 Hybrid retrieval" ✅
# - "📊 Vector search" and "📊 BM25 search" ✅
# - "🎯 Reranked X docs" ✅

# 4. If you see all these, you're good to deploy! 🚀
```

---

## 📝 **LOG EXAMPLES**

### **Successful Hybrid RAG Log:**
```
🔍 Hybrid retrieval for query: 'What is AI?'
  📊 Vector search: 10 docs
  📊 BM25 search: 10 docs
🔀 RRF merged 10 vector + 10 BM25 = 14 unique docs
🎯 Reranked 14 docs, top score: 0.8734
  ✅ Final: 4 documents
    1. [ai_intro.pdf] Artificial Intelligence is the simulation of human...
    2. [ml_basics.pdf] AI encompasses machine learning and deep learning...
    3. [history.pdf] The field of AI began in the 1950s...
    4. [applications.pdf] Modern AI applications include computer vision...
```

### **Successful Conversational Chat Log:**
```
Chat query: What is AI?... (session: quick_test)
🔍 Hybrid retrieval for query: 'What is AI?'
[... RAG retrieval logs ...]
[Current Answer] Artificial Intelligence is...

Chat query: Give me an example... (session: quick_test)
💬 Using conversation context from memory
🔍 Hybrid retrieval for query: 'Previous conversation:\nUser: What is AI?\nAssistant: Artificial Intelligence is...\n\nCurrent question: Give me an example'
[... RAG retrieval logs ...]
[Current Answer] Here's an example of AI in action: Image recognition systems...
```

---

## ✅ **READY FOR EC2 DEPLOYMENT**

Once all tests pass locally:

1. ✅ Hybrid RAG retrieves documents correctly
2. ✅ Conversation memory works across messages
3. ✅ Quiz generates 40 questions (not 0)
4. ✅ Document upload verifies in ChromaDB

**Next step:** Follow `RAG_UPGRADE_DEPLOYMENT.md` to deploy to EC2.

---

## 🚀 **QUICK DEPLOY COMMAND**

After successful local testing:

```powershell
# Upload all files to EC2
scp -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem `
  services/hybrid_retriever.py `
  services/rag_service.py `
  services/chat_service.py `
  services/llm_service.py `
  services/quiz_service.py `
  core/cloud_vectorizer.py `
  app_celery.py `
  ubuntu@51.20.109.241:~/profai/

# SSH and update
ssh -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem ubuntu@51.20.109.241
docker exec -it profai-api pip install sentence-transformers rank-bm25
docker restart profai-api
docker logs -f profai-api
```

---

**Happy Testing! 🧪**
