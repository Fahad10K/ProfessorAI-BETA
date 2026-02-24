# 🚀 TESTING PARALLEL COURSE GENERATION

## 📋 **Prerequisites**

Your system uses **Celery + Redis** for distributed task processing. This enables multiple PDFs to be processed in parallel by multiple workers.

### **Required Services:**
1. ✅ **Redis** - Message broker and result backend
2. ✅ **Celery Workers** - Background task processors
3. ✅ **FastAPI Server** - API endpoints

---

## 🔧 **Setup: Start All Services**

### **Step 1: Start Redis**

#### **Option A: Local Redis (Docker)**
```powershell
# Run Redis in Docker
docker run -d --name redis-profai -p 6379:6379 redis:latest

# Verify Redis is running
docker ps | findstr redis
```

#### **Option B: Cloud Redis (Upstash - Recommended)**
```powershell
# Set environment variable in .env file
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_HOST:6379
```

---

### **Step 2: Start Celery Workers**

Open **3 separate PowerShell terminals** for parallel processing:

#### **Terminal 1: PDF Processing Worker**
```powershell
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Start worker for PDF processing queue
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker1@%h
```

#### **Terminal 2: Second PDF Processing Worker (Optional - for more parallelism)**
```powershell
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Start second worker for even more parallel processing
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker2@%h
```

#### **Terminal 3: Quiz Generation Worker (Optional)**
```powershell
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Start worker for quiz generation
celery -A celery_app worker --loglevel=info --pool=solo -Q quiz_generation -n worker3@%h
```

**Note:** More workers = More parallel processing capacity!

---

### **Step 3: Start FastAPI Server**

#### **Terminal 4: API Server**
```powershell
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Start production API server
python app_celery.py
```

**Expected Output:**
```
✅ All services loaded successfully
✅ All services initialized successfully
INFO:     Uvicorn running on http://0.0.0.0:5001
```

---

## 🧪 **Testing Methods**

### **Method 1: Using PowerShell (curl)**

#### **Test 1: Upload Single PDF**
```powershell
# Upload one PDF
curl -X POST "http://localhost:5001/api/upload-pdfs" `
  -F "files=@C:\path\to\your\document.pdf" `
  -F "course_title=Machine Learning Basics" `
  -F "priority=5"
```

**Expected Response:**
```json
{
  "message": "PDF processing started",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "abc123def456",
  "status": "pending",
  "status_url": "/api/jobs/abc123def456"
}
```

---

#### **Test 2: Upload Multiple PDFs (Parallel Processing)**
```powershell
# Upload 3 PDFs simultaneously - they will be processed in parallel!
curl -X POST "http://localhost:5001/api/upload-pdfs" `
  -F "files=@C:\path\to\document1.pdf" `
  -F "files=@C:\path\to\document2.pdf" `
  -F "files=@C:\path\to\document3.pdf" `
  -F "course_title=Complete AI Course" `
  -F "priority=7"
```

---

#### **Test 3: Check Job Status**
```powershell
# Replace abc123def456 with your actual task_id
curl "http://localhost:5001/api/jobs/abc123def456"
```

**Response Stages:**
```json
// Stage 1: Pending
{
  "task_id": "abc123def456",
  "status": "PENDING",
  "progress": 0,
  "message": "Task is waiting in queue..."
}

// Stage 2: Started
{
  "task_id": "abc123def456",
  "status": "STARTED",
  "progress": 50,
  "message": "Generating course content..."
}

// Stage 3: Success
{
  "task_id": "abc123def456",
  "status": "SUCCESS",
  "progress": 100,
  "message": "Task completed successfully",
  "result": {
    "course_id": "1",
    "course_title": "Machine Learning Basics",
    "modules": 5
  }
}
```

---

#### **Test 4: Monitor Workers**
```powershell
# Check worker statistics
curl "http://localhost:5001/api/worker-stats"
```

**Expected Response:**
```json
{
  "active_workers": {
    "worker1@HOSTNAME": [],
    "worker2@HOSTNAME": []
  },
  "scheduled_tasks": {
    "worker1@HOSTNAME": []
  },
  "active_tasks": {
    "worker1@HOSTNAME": [
      {
        "id": "abc123",
        "name": "tasks.pdf_processing.process_pdf_and_generate_course"
      }
    ]
  }
}
```

---

### **Method 2: Using Python Script**

Create a test script to upload multiple PDFs in parallel:

#### **test_parallel_upload.py**
```python
import requests
import time
import json
from pathlib import Path

# Configuration
API_URL = "http://localhost:5001"
PDF_FILES = [
    r"C:\path\to\document1.pdf",
    r"C:\path\to\document2.pdf",
    r"C:\path\to\document3.pdf",
]

def upload_pdf(file_path, course_title, priority=5):
    """Upload a single PDF and return task ID"""
    url = f"{API_URL}/api/upload-pdfs"
    
    with open(file_path, 'rb') as f:
        files = {'files': (Path(file_path).name, f, 'application/pdf')}
        data = {
            'course_title': course_title,
            'priority': priority
        }
        
        response = requests.post(url, files=files, data=data)
        return response.json()

def check_status(task_id):
    """Check status of a task"""
    url = f"{API_URL}/api/jobs/{task_id}"
    response = requests.get(url)
    return response.json()

def test_parallel_upload():
    """Upload multiple PDFs and monitor progress"""
    print("🚀 Starting parallel course generation test...\n")
    
    # Upload all PDFs
    tasks = []
    for i, pdf_path in enumerate(PDF_FILES):
        print(f"📤 Uploading: {Path(pdf_path).name}")
        result = upload_pdf(pdf_path, f"Course {i+1}", priority=5+i)
        tasks.append({
            'file': Path(pdf_path).name,
            'task_id': result['task_id'],
            'job_id': result['job_id']
        })
        print(f"   ✅ Task ID: {result['task_id']}")
        print()
    
    print(f"📊 Monitoring {len(tasks)} parallel tasks...\n")
    
    # Monitor all tasks
    completed = 0
    while completed < len(tasks):
        for task in tasks:
            if task.get('completed'):
                continue
                
            status = check_status(task['task_id'])
            
            if status['status'] == 'SUCCESS':
                task['completed'] = True
                completed += 1
                result = status.get('result', {})
                print(f"✅ {task['file']}: COMPLETED")
                print(f"   Course ID: {result.get('course_id')}")
                print(f"   Modules: {result.get('modules')}")
                print()
            elif status['status'] == 'FAILURE':
                task['completed'] = True
                completed += 1
                print(f"❌ {task['file']}: FAILED")
                print(f"   Error: {status.get('error')}")
                print()
            else:
                progress = status.get('progress', 0)
                message = status.get('message', 'Processing...')
                print(f"⏳ {task['file']}: {progress}% - {message}")
        
        if completed < len(tasks):
            time.sleep(5)  # Check every 5 seconds
            print()
    
    print("🎉 All parallel tasks completed!")

if __name__ == "__main__":
    test_parallel_upload()
```

**Run the script:**
```powershell
python test_parallel_upload.py
```

---

### **Method 3: Using Postman**

1. **Import Collection:**
   - Create new request
   - Method: `POST`
   - URL: `http://localhost:5001/api/upload-pdfs`

2. **Set Body (form-data):**
   - Key: `files` | Type: `File` | Value: Select PDF file
   - Key: `files` | Type: `File` | Value: Select another PDF
   - Key: `course_title` | Type: `Text` | Value: "Test Course"
   - Key: `priority` | Type: `Text` | Value: "5"

3. **Send Request & Get task_id**

4. **Monitor Status:**
   - Create GET request
   - URL: `http://localhost:5001/api/jobs/{task_id}`
   - Send periodically to check progress

---

## 📊 **Monitoring & Debugging**

### **1. Check Celery Worker Logs**

Watch the worker terminal to see real-time processing:

```
[2024-11-30 19:30:15,123: INFO] Task started: tasks.pdf_processing.process_pdf_and_generate_course
[2024-11-30 19:30:16,456: INFO] [Job abc123] Processing 3 PDF files
[2024-11-30 19:30:20,789: INFO] Extracting text from PDFs...
[2024-11-30 19:30:45,234: INFO] Generating course content...
[2024-11-30 19:31:15,567: INFO] [Job abc123] Course generated successfully: 1
[2024-11-30 19:31:15,890: INFO] Task completed successfully
```

---

### **2. Monitor Redis Queue**

```powershell
# Connect to Redis CLI (if using local Redis)
docker exec -it redis-profai redis-cli

# Check queue length
LLEN celery

# Check active tasks
KEYS celery-task-meta-*
```

---

### **3. Check Worker Stats via API**

```powershell
curl "http://localhost:5001/api/worker-stats"
```

---

### **4. Celery Flower (Web Monitoring - Optional)**

```powershell
# Install Flower
pip install flower

# Start Flower dashboard
celery -A celery_app flower --port=5555

# Open browser: http://localhost:5555
```

**Flower Dashboard shows:**
- ✅ Active workers
- ✅ Task success/failure rates
- ✅ Real-time task monitoring
- ✅ Worker resource usage

---

## 🎯 **Testing Parallel Processing**

### **Scenario 1: Sequential Processing (1 Worker)**

Start **1 worker** and upload **3 PDFs**:

```powershell
# Worker 1 only
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker1@%h
```

**Result:** Tasks processed **one after another** (sequential)
- PDF 1: 0-5 minutes
- PDF 2: 5-10 minutes
- PDF 3: 10-15 minutes
- **Total: ~15 minutes**

---

### **Scenario 2: Parallel Processing (3 Workers)**

Start **3 workers** and upload **3 PDFs**:

```powershell
# Terminal 1
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker1@%h

# Terminal 2
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker2@%h

# Terminal 3
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker3@%h
```

**Result:** Tasks processed **simultaneously** (parallel)
- PDF 1: Worker 1 → 0-5 minutes
- PDF 2: Worker 2 → 0-5 minutes
- PDF 3: Worker 3 → 0-5 minutes
- **Total: ~5 minutes** ⚡

**3x FASTER!** 🚀

---

## 🎓 **Verification Checklist**

After testing, verify:

- [ ] Redis is running and accepting connections
- [ ] Celery workers are active and processing tasks
- [ ] FastAPI server is responding
- [ ] Upload endpoint returns task_id
- [ ] Status endpoint shows progress updates
- [ ] Multiple uploads create separate tasks
- [ ] Workers process tasks in parallel (check logs)
- [ ] Generated courses appear in `/api/courses`
- [ ] Course content is accessible via `/api/course/{course_id}`

---

## 🐛 **Common Issues**

### **Issue 1: "Connection refused" error**

**Cause:** Redis not running

**Solution:**
```powershell
# Start Redis
docker run -d --name redis-profai -p 6379:6379 redis:latest

# Or check REDIS_URL in .env
```

---

### **Issue 2: Tasks stuck in PENDING**

**Cause:** No workers running

**Solution:**
```powershell
# Start at least one worker
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing
```

---

### **Issue 3: Workers crash or timeout**

**Cause:** Task takes too long or memory issue

**Solution:**
- Increase `task_time_limit` in `celery_app.py`
- Start more workers with smaller workloads
- Check worker logs for specific errors

---

### **Issue 4: Can't import celery_app**

**Cause:** Python path issue

**Solution:**
```powershell
# Run from Prof_AI directory
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Make sure celery_app.py exists
ls celery_app.py
```

---

## 📈 **Performance Testing**

### **Load Test: 10 Simultaneous Uploads**

```python
# load_test.py
import requests
import concurrent.futures
from pathlib import Path

def upload_pdf(index):
    url = "http://localhost:5001/api/upload-pdfs"
    pdf_path = r"C:\path\to\test.pdf"
    
    with open(pdf_path, 'rb') as f:
        files = {'files': (f'test_{index}.pdf', f, 'application/pdf')}
        data = {'course_title': f'Course {index}', 'priority': 5}
        
        response = requests.post(url, files=files, data=data)
        return response.json()

# Upload 10 PDFs in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(upload_pdf, i) for i in range(10)]
    results = [f.result() for f in futures]

print(f"✅ Submitted {len(results)} tasks")
for r in results:
    print(f"Task {r['task_id']}: {r['status']}")
```

**Run:**
```powershell
python load_test.py
```

---

## 🎉 **Success Indicators**

You'll know parallel processing is working when:

1. ✅ **Multiple workers show activity simultaneously**
2. ✅ **Worker logs show different tasks at same time**
3. ✅ **Total processing time < sum of individual times**
4. ✅ **API returns different task_ids for each upload**
5. ✅ **All courses appear in `/api/courses` endpoint**

---

## 📚 **Next Steps**

After successful testing:

1. **Scale Workers:** Add more workers for higher throughput
2. **Add Monitoring:** Set up Flower dashboard
3. **Production Deployment:** Deploy to Kubernetes with auto-scaling
4. **Database Integration:** Store course data in PostgreSQL
5. **Add Webhooks:** Notify users when processing completes

---

## 🚀 **Quick Start Command Summary**

```powershell
# Terminal 1: Redis
docker run -d --name redis-profai -p 6379:6379 redis:latest

# Terminal 2: Worker 1
cd Prof_AI
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker1@%h

# Terminal 3: Worker 2
cd Prof_AI
celery -A celery_app worker --loglevel=info --pool=solo -Q pdf_processing -n worker2@%h

# Terminal 4: API Server
cd Prof_AI
python app_celery.py

# Terminal 5: Test Upload
curl -X POST "http://localhost:5001/api/upload-pdfs" `
  -F "files=@C:\path\to\test.pdf" `
  -F "course_title=Test Course"
```

**You're ready to test parallel course generation! 🎓⚡**
