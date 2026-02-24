# 🧪 LOCAL TESTING - STEP BY STEP GUIDE

Test your 5-worker setup locally before deploying to EC2.

---

## 📋 **STEP 1: VERIFY FILES**

Check that all modified files are present:

```powershell
# In your project directory
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Check modified files exist
ls worker.py
ls celery_app.py
ls docker-compose-production.yml
ls test_workers_local.py
ls monitor_workers.py
ls start_all_workers.ps1
```

**Expected:** All files should exist ✅

---

## 🔌 **STEP 2: TEST REDIS CONNECTION**

Verify your Redis connection works:

```powershell
python -c "from celery_app import celery_app; print('✅ Celery app loaded successfully')"
```

**Expected Output:**
```
✅ Celery: Using Redis URL: rediss://...@redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10925
✅ Celery app loaded successfully
```

**If you see errors:**
- Check `.env` file has `REDIS_URL` configured
- Verify Redis Labs connection string is correct

---

## 🚀 **STEP 3: START ALL WORKERS**

### **Method 1: Automated (Recommended)**

```powershell
# Start all 5 workers at once
.\start_all_workers.ps1
```

This will open 5 PowerShell windows, one for each worker.

**Wait 10 seconds** for all workers to connect to Redis.

---

### **Method 2: Manual (Alternative)**

Open 5 separate PowerShell terminals and run:

**Terminal 1:**
```powershell
$env:WORKER_NUM="1"
python worker.py
```

**Terminal 2:**
```powershell
$env:WORKER_NUM="2"
python worker.py
```

**Terminal 3:**
```powershell
$env:WORKER_NUM="3"
python worker.py
```

**Terminal 4:**
```powershell
$env:WORKER_NUM="4"
python worker.py
```

**Terminal 5:**
```powershell
$env:WORKER_NUM="5"
python worker.py
```

---

## ✅ **STEP 4: VERIFY WORKERS STARTED**

In each worker window, you should see:

```
[INFO/MainProcess] Connected to redis://...
[INFO/MainProcess] celery@worker1 ready.
```

**Key indicators:**
- ✅ "Connected to redis"
- ✅ "celery@workerX ready"
- ✅ No error messages

**If you see errors:**
- Check Redis connection
- Verify `.env` file settings
- Check if port is already in use

---

## 🧪 **STEP 5: RUN TEST SUITE**

Open a NEW PowerShell window (keep workers running!) and run:

```powershell
python test_workers_local.py
```

**Expected Output:**

```
🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪
  LOCAL WORKER TESTING SUITE - 5 WORKERS
🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪🧪

================================================================================
  TEST 1: Celery Configuration
================================================================================
📡 Testing Redis connection...
✅ Redis connected: 5 workers detected
   - worker1@DESKTOP
   - worker2@DESKTOP
   - worker3@DESKTOP
   - worker4@DESKTOP
   - worker5@DESKTOP

📋 Celery Configuration:
   - Broker: rediss://...
   - Task Queues: ['pdf_processing', 'quiz_generation']
   - Worker Prefetch: 1
   - Max Tasks Per Child: 20

================================================================================
  TEST 2: Worker Registration
================================================================================
✅ Found 5 active workers:

Worker: worker1@DESKTOP
   Registered Tasks: 2
   - tasks.pdf_processing.process_pdf_and_generate_course
   - tasks.quiz_generation.generate_quiz

(... workers 2-5 similar ...)

================================================================================
  TEST 3: Worker Statistics
================================================================================
✅ Worker Statistics:

Worker: worker1@DESKTOP
   Pool: prefork
   Max Concurrency: 1
   Total Tasks: {}

(... workers 2-5 similar ...)

✅ All 5 workers are running!

================================================================================
  TEST 4: Queue Status
================================================================================
✅ No active tasks (workers are idle)
✅ No tasks in queue (all workers available)

================================================================================
  TEST 5: Send Test Task (Optional)
================================================================================
⚠️  Send a test task to workers? This will test actual processing. (y/N): n
⏭️  Skipping test task

================================================================================
  TEST SUMMARY
================================================================================

  ✅ PASS - Celery Config
  ✅ PASS - Worker Registration
  ✅ PASS - Worker Stats
  ✅ PASS - Queue Status
  ✅ PASS - Test Task

📊 Results: 5/5 tests passed

🎉 All tests passed! Your setup is ready for EC2 deployment!
```

---

## 📊 **STEP 6: MONITOR WORKERS**

Test the monitoring script:

```powershell
python monitor_workers.py
```

**Expected Output:**

```
🔍 CELERY WORKER MONITORING DASHBOARD
====================================

📊 WORKER STATUS
----------------
✅ Found 5 active workers

Worker: worker1@DESKTOP
  Pool: prefork
  Max Concurrency: 1
  Active Tasks: 0

(... workers 2-5 ...)

📋 QUEUE STATUS
----------------
✅ No tasks in queue (all workers available)
```

---

## 🎯 **STEP 7: TEST WITH ACTUAL PDF (Optional)**

If you want to test with a real PDF:

1. **Start your API server:**
   ```powershell
   python run_profai_websocket_celery.py
   ```

2. **Upload a small PDF:**
   ```powershell
   curl -X POST http://localhost:5003/api/upload-pdfs -F "files=@test.pdf" -F "course_title=Test Course"
   ```

3. **Watch a worker process it:**
   - Go to one of the worker windows
   - You should see logs showing PDF processing

4. **Monitor which worker picked it up:**
   ```powershell
   python monitor_workers.py
   ```

---

## ✅ **SUCCESS CRITERIA**

Before deploying to EC2, verify:

- [ ] All 5 worker windows show "celery@workerX ready"
- [ ] `test_workers_local.py` shows 5/5 tests passed
- [ ] `monitor_workers.py` shows 5 active workers
- [ ] No error messages in any worker window
- [ ] Each worker shows `Pool: prefork` and `Max Concurrency: 1`

---

## 🛑 **STOPPING WORKERS**

When done testing:

1. Go to each worker PowerShell window
2. Press `Ctrl+C` to stop that worker
3. Wait for graceful shutdown

**Or** close all worker windows.

---

## ❌ **TROUBLESHOOTING**

### **Problem: Workers can't connect to Redis**

**Symptoms:**
```
[ERROR] Consumer: Cannot connect to redis://...
```

**Fix:**
1. Check `.env` file has correct `REDIS_URL`
2. Verify Redis Labs is accessible:
   ```powershell
   python -c "import redis; r = redis.from_url('YOUR_REDIS_URL'); print(r.ping())"
   ```

---

### **Problem: Only 1 worker shows up**

**Symptoms:**
```
✅ Found 1 active workers
```

**Fix:**
1. Verify all 5 worker windows are open and running
2. Check each shows "celery@workerX ready"
3. Wait 10 seconds after starting all workers

---

### **Problem: ImportError or ModuleNotFoundError**

**Symptoms:**
```
ImportError: cannot import name 'celery_app'
```

**Fix:**
1. Ensure you're in the correct directory:
   ```powershell
   cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI
   ```
2. Activate virtual environment if using one:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

---

### **Problem: Test suite fails**

**Symptoms:**
```
❌ FAIL - Worker Registration
```

**Fix:**
1. Make sure workers are running first
2. Wait 10 seconds after starting workers
3. Run test again

---

## 🎉 **READY FOR EC2 DEPLOYMENT?**

If all tests pass, you're ready to deploy!

**Next steps:**

1. **Upload files to EC2:**
   ```bash
   scp -i ~/Downloads/my-ai-app-key.pem worker.py ubuntu@51.20.109.241:~/profai/
   scp -i ~/Downloads/my-ai-app-key.pem celery_app.py ubuntu@51.20.109.241:~/profai/
   scp -i ~/Downloads/my-ai-app-key.pem docker-compose-production.yml ubuntu@51.20.109.241:~/profai/
   ```

2. **SSH to EC2:**
   ```bash
   ssh -i ~/Downloads/my-ai-app-key.pem ubuntu@51.20.109.241
   ```

3. **Rebuild and restart:**
   ```bash
   cd ~/profai
   docker-compose -f docker-compose-production.yml down
   docker-compose -f docker-compose-production.yml build
   docker-compose -f docker-compose-production.yml up -d
   ```

4. **Verify:**
   ```bash
   docker ps  # Should show 6 containers
   ```

---

**Good luck with testing!** 🚀
