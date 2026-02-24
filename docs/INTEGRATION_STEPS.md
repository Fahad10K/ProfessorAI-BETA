# ChatServiceV2 Integration Steps

## 🎯 Quick Integration Guide

### Step 1: Backup Old Implementation
```bash
cd services
mv chat_service.py chat_service_legacy.py
mv chat_service_v2.py chat_service.py
```

### Step 2: Update Imports (if needed)
**File:** `app_celery.py`

Change from:
```python
from services.chat_service import ChatService
```

To (if using V2 class name):
```python
from services.chat_service import ChatServiceV2 as ChatService
```

OR rename the class in chat_service.py from `ChatServiceV2` to `ChatService`

### Step 3: Test Application Startup
```bash
# Activate venv
cd ..
.\Prof_AI\.venv\Scripts\Activate.ps1
cd .\Prof_AI\

# Start application
python app_celery.py
```

### Step 4: Test API Endpoints
```bash
# Test chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "language": "en-IN"}'
```

### Step 5: Verify WebSocket Server
- Check WebSocket connections work
- Test real-time chat
- Verify conversation memory

---

## 🔍 What to Watch For

### Success Indicators:
- ✅ App starts without import errors
- ✅ ChromaDB connects (51,821 documents)
- ✅ Semantic Router initializes
- ✅ Agent creates successfully
- ✅ Chat endpoint responds
- ✅ Conversation memory works

### Potential Issues:
- ⚠️ ChromaDB deprecation warning (cosmetic, ignore)
- ⚠️ Semantic router index warning (cosmetic, ignore)
- ❌ Import errors → Check venv activated
- ❌ Agent creation fails → Check OpenAI API key

---

## 🔄 Rollback Plan

If issues occur:
```bash
cd services
mv chat_service.py chat_service_v2_failed.py
mv chat_service_legacy.py chat_service.py
```

---

## 📋 Post-Integration Checklist

- [ ] Application starts without errors
- [ ] Chat endpoint works
- [ ] WebSocket server functional
- [ ] Conversation memory persists
- [ ] RAG retrieval working
- [ ] Semantic routing classifying correctly
- [ ] General LLM fallback working
- [ ] Greeting handler fast
- [ ] Performance acceptable
- [ ] No memory leaks

---

## 🎯 Next: Fix Remaining Services

After ChatService integration successful, fix these:

1. **rag_service.py** - Uses deprecated chains (not needed with V2!)
2. **hybrid_retriever.py** - Already LangChain 1.0 compatible ✅
3. **document_service.py** - LangChain 1.0 compatible ✅

**Note:** With ChatServiceV2, `rag_service.py` may not be needed anymore since agent handles RAG internally.

---

## 🚀 Ready to Integrate!

Run:
```bash
cd services
mv chat_service.py chat_service_legacy.py
mv chat_service_v2.py chat_service.py
cd ..
python app_celery.py
```
