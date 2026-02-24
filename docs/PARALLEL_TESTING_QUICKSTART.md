# ⚡ QUICK START: Test Parallel Course Generation

## 🎯 **3-Minute Setup**

### **Step 1: Start Redis** (1 terminal)
```powershell
# Option A: Docker (recommended)
docker run -d --name redis-profai -p 6379:6379 redis:latest

# Option B: Use Upstash (add to .env)
# REDIS_URL=rediss://default:password@host:6379
```

### **Step 2: Start Workers** (2-3 terminals)
```powershell
# Terminal 1: Worker #1
cd Prof_AI
.\start_celery_worker.ps1 -WorkerNumber 1

# Terminal 2: Worker #2 (optional, for more parallelism)
cd Prof_AI
.\start_celery_worker.ps1 -WorkerNumber 2
```

### **Step 3: Start API Server** (1 terminal)
```powershell
# Terminal 3: API
cd Prof_AI
python app_celery.py
```

### **Step 4: Run Tests**
```powershell
# Terminal 4: Test script
cd Prof_AI

# Edit test_parallel_upload.py and update PDF_FILES paths first!
# Then run:
python test_parallel_upload.py
```

---

## 🧪 **Quick Manual Test**

### **Upload PDFs:**
```powershell
# Upload single PDF
curl -X POST "http://localhost:5001/api/upload-pdfs" `
  -F "files=@C:\path\to\your.pdf" `
  -F "course_title=Test Course"

# Response:
# {
#   "task_id": "abc123...",
#   "status": "pending"
# }
```

### **Check Status:**
```powershell
# Replace abc123 with your task_id
curl "http://localhost:5001/api/jobs/abc123..."

# Response shows progress:
# {
#   "status": "STARTED",
#   "progress": 50,
#   "message": "Generating course..."
# }
```

---

## ✅ **Verify Parallel Processing**

### **How to Confirm It's Working:**

1. **Start 2 workers** in separate terminals
2. **Upload 2 PDFs** simultaneously:
   ```powershell
   # Terminal A
   curl -X POST "http://localhost:5001/api/upload-pdfs" -F "files=@doc1.pdf" -F "course_title=Course 1"
   
   # Terminal B (run at same time)
   curl -X POST "http://localhost:5001/api/upload-pdfs" -F "files=@doc2.pdf" -F "course_title=Course 2"
   ```

3. **Watch worker logs** - You should see:
   ```
   Worker 1: Processing Course 1...
   Worker 2: Processing Course 2...  ← Both at same time!
   ```

4. **Check completion time:**
   - Sequential (1 worker): 10 minutes total
   - Parallel (2 workers): 5 minutes total ⚡

---

## 📊 **Monitor Active Processing**

```powershell
# Check worker stats
curl "http://localhost:5001/api/worker-stats"

# See active workers and current tasks
```

---

## 🎓 **Expected Results**

### **✅ Success Indicators:**
- Multiple workers show in stats
- Worker logs show different tasks simultaneously
- Total time is less than sum of individual times
- Each upload gets unique task_id

### **❌ Common Issues:**

**"Connection refused"**
→ Redis not running. Start Redis first.

**"No workers available"**
→ Start at least 1 Celery worker.

**Tasks stuck in PENDING**
→ Workers not listening to correct queue. Check logs.

---

## 🚀 **Next Steps**

After successful testing:
1. **Scale workers** for higher throughput
2. **Deploy to K8s** with auto-scaling
3. **Add monitoring** with Celery Flower
4. **Production setup** with proper Redis (Upstash)

---

## 📚 **Full Documentation**

For detailed information, see:
- `TESTING_PARALLEL_COURSE_GENERATION.md` - Complete guide
- `test_parallel_upload.py` - Automated test script
- `start_celery_worker.ps1` - Worker startup script

---

## 💡 **Pro Tips**

1. **More workers = More parallelism**
   - 1 worker = 1 PDF at a time
   - 3 workers = 3 PDFs simultaneously

2. **Use priorities for important courses**
   ```powershell
   -F "priority=10"  # High priority (processed first)
   ```

3. **Monitor with Flower**
   ```powershell
   pip install flower
   celery -A celery_app flower --port=5555
   # Open: http://localhost:5555
   ```

---

## 🎉 **You're Ready!**

Your parallel course generation system is production-ready and can scale horizontally! 🚀
