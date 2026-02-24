# 🚀 TODAY'S ACTION PLAN - Go Live!

**Goal:** Set up Redis + Celery + PostgreSQL and test production architecture

**Time Estimate:** 4-6 hours  
**Date:** November 3, 2025

---

## ✅ Pre-Flight Checklist

What you already have:
- [x] Docker installed
- [x] Kubernetes manifests created
- [x] Celery code written (`celery_app.py`, `worker.py`, `app_celery.py`)
- [x] Database schema designed (`migrations/001_initial_schema.sql`)
- [x] Current data in JSON files (`data/courses/course_output.json`)

What you need:
- [ ] Neon PostgreSQL account
- [ ] Redis (Upstash Cloud or local)
- [ ] Database migrated
- [ ] Celery workers running
- [ ] Everything tested

---

## 📋 Step-by-Step Plan

### STEP 1: Set Up Neon PostgreSQL (10 minutes)

**1.1 Create Neon Account**
```
1. Go to: https://neon.tech
2. Click "Sign Up" (use GitHub or Google)
3. Verify email
4. Create new project: "profai"
5. Choose region: US East (closest to you)
```

**1.2 Get Connection String**
```
1. In Neon dashboard, click your project
2. Go to "Connection Details"
3. Copy the connection string:
   postgresql://username:password@ep-xxx-xxx.us-east-2.aws.neon.tech/profai?sslmode=require
```

**1.3 Test Connection**
```bash
# Install psycopg2
pip install psycopg2-binary

# Test connection
python -c "
import psycopg2
conn = psycopg2.connect('YOUR_CONNECTION_STRING')
print('✅ Connected to Neon!')
conn.close()
"
```

**1.4 Save to .env**
```env
# Add to your .env file
DATABASE_URL=postgresql://username:password@ep-xxx.us-east-2.aws.neon.tech/profai?sslmode=require
USE_DATABASE=True
```

---

### STEP 2: Run Database Migration (15 minutes)

**2.1 Connect to Neon**
```bash
# Option A: Using psql (if installed)
psql "postgresql://username:password@ep-xxx.neon.tech/profai?sslmode=require"

# Option B: Using Neon SQL Editor (web)
# Go to Neon dashboard → SQL Editor
```

**2.2 Run Migration Script**
```bash
# If using psql
psql "YOUR_DATABASE_URL" < migrations/001_initial_schema.sql

# If using Neon SQL Editor:
# Copy/paste contents of migrations/001_initial_schema.sql
# Click "Run"
```

**2.3 Verify Tables Created**
```sql
-- Run this query to check
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Should show:
-- users
-- courses
-- modules
-- topics
-- quizzes
-- quiz_questions
-- quiz_responses
-- job_queue
-- source_files
-- user_progress
```

**2.4 Check Seed Data**
```sql
SELECT * FROM users;

-- Should show 3 users:
-- admin_001
-- teacher_001
-- student_001
```

---

### STEP 3: Set Up Redis (15 minutes)

**Option A: Upstash Cloud (RECOMMENDED - Free tier)**

```
1. Go to: https://upstash.com
2. Sign up (free tier: 10,000 commands/day)
3. Click "Create Database"
   - Name: profai-redis
   - Region: US East
   - Type: Regional
4. Get connection details:
   - Endpoint: useast1-xxx.upstash.io
   - Port: 6379
   - Password: xxxxx
```

**Add to .env:**
```env
REDIS_HOST=useast1-xxx.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=your_password_here
REDIS_DB=0
```

**Option B: Local Docker (For testing)**

```bash
# Start Redis container
docker run -d --name profai-redis \
  -p 6379:6379 \
  redis:7-alpine

# Test connection
redis-cli ping
# Should return: PONG
```

**Add to .env:**
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
```

---

### STEP 4: Migrate Existing JSON Data (30 minutes)

**4.1 Create Migration Script**

I'll create this for you in the next file: `migrate_json_to_db.py`

**4.2 Run Migration**
```bash
# This will:
# - Read data/courses/course_output.json
# - Insert courses, modules, topics into PostgreSQL
# - Preserve course_ids
# - Create backup of JSON files

python migrate_json_to_db.py
```

**4.3 Verify Migration**
```sql
-- Check courses migrated
SELECT course_id, title FROM courses;

-- Check modules
SELECT m.course_id, m.week, m.title 
FROM modules m 
ORDER BY m.course_id, m.week;

-- Check topics
SELECT t.title 
FROM topics t 
JOIN modules m ON t.module_id = m.id 
LIMIT 10;
```

---

### STEP 5: Update Application Code (20 minutes)

**5.1 Uncomment Database Service**

Edit `services/database_service.py`:
```python
# Change line 13:
USE_DATABASE = True  # Was False

# Change line 14:
DATABASE_URL = os.getenv("DATABASE_URL")  # From config
```

**5.2 Update Config**

Already done! Just ensure `.env` has:
```env
USE_DATABASE=True
DATABASE_URL=postgresql://...
```

**5.3 Install Dependencies**
```bash
pip install -r requirements.txt

# Should install:
# - celery
# - redis
# - psycopg2-binary
# - sqlalchemy
```

---

### STEP 6: Test Locally (1 hour)

**6.1 Start Redis**
```bash
# If using Upstash, already running!
# If using local Docker:
docker start profai-redis
```

**6.2 Start Celery Worker (Terminal 1)**
```bash
# Set environment variables
$env:DATABASE_URL="postgresql://..."
$env:REDIS_HOST="localhost"  # or upstash endpoint
$env:REDIS_PASSWORD="..."    # if using Upstash
$env:USE_DATABASE="True"
$env:OPENAI_API_KEY="sk-proj-..."
$env:GROQ_API_KEY="..."
$env:SARVAM_API_KEY="..."
$env:USE_CHROMA_CLOUD="True"
$env:CHROMA_CLOUD_API_KEY="..."

# Start worker
python worker.py

# Should see:
# [INFO] Celery worker starting...
# [INFO] Connected to Redis
# [INFO] Ready to process tasks
```

**6.3 Start API Server (Terminal 2)**
```bash
# Same environment variables as above

# Start API (production version with Celery)
python run_profai_websocket_celery.py

# Should see:
# [INFO] Starting WebSocket server...
# [INFO] Starting FastAPI server on 0.0.0.0:5001...
# [INFO] Connected to database
# [INFO] Connected to Redis
```

**6.4 Test Upload**
```bash
# Terminal 3
curl -X POST http://localhost:5001/api/upload-pdfs `
  -F "files=@test.pdf" `
  -F "course_title=Test Course"

# Should return IMMEDIATELY:
{
  "message": "PDF processing started",
  "task_id": "abc-123-def",
  "job_id": "xyz-789",
  "status": "pending"
}
```

**6.5 Check Task Status**
```bash
curl http://localhost:5001/api/jobs/abc-123-def

# Response:
{
  "task_id": "abc-123-def",
  "status": "STARTED",  # or PENDING, SUCCESS
  "progress": 45,
  "message": "Generating content..."
}
```

**6.6 Check Database**
```sql
-- New course should be in database
SELECT * FROM courses ORDER BY id DESC LIMIT 1;

-- Modules should exist
SELECT * FROM modules WHERE course_id = (
  SELECT course_id FROM courses ORDER BY id DESC LIMIT 1
);

-- Job should be tracked
SELECT * FROM job_queue ORDER BY created_at DESC LIMIT 1;
```

**6.7 Start Flower (Optional - Monitoring)**
```bash
# Terminal 4
celery -A celery_app flower --port=5555

# Open: http://localhost:5555
# See: Active workers, tasks, queue length
```

---

### STEP 7: Test with Docker Compose (30 minutes)

**7.1 Update .env for Docker**
```env
# .env file for Docker Compose

# Database (Neon Cloud)
DATABASE_URL=postgresql://username:password@ep-xxx.neon.tech/profai?sslmode=require
USE_DATABASE=True

# Redis (Upstash Cloud OR use docker redis service)
REDIS_HOST=useast1-xxx.upstash.io  # or "redis" if using docker service
REDIS_PORT=6379
REDIS_PASSWORD=your_password  # or empty if using docker service
REDIS_DB=0

# API Keys
OPENAI_API_KEY=sk-proj-...
SARVAM_API_KEY=...
GROQ_API_KEY=...

# ChromaDB Cloud
USE_CHROMA_CLOUD=True
CHROMA_CLOUD_API_KEY=...
CHROMA_CLOUD_TENANT=...
CHROMA_CLOUD_DATABASE=...
```

**7.2 Build and Run**
```bash
# Build image
docker-compose -f docker-compose-production.yml build

# Start services
docker-compose -f docker-compose-production.yml up -d

# Check logs
docker-compose -f docker-compose-production.yml logs -f api
docker-compose -f docker-compose-production.yml logs -f worker-1

# Should see:
# api_1      | ✅ Connected to database
# api_1      | ✅ Connected to Redis
# worker-1_1 | ✅ Celery worker ready
```

**7.3 Test**
```bash
# Upload PDF
curl -X POST http://localhost:5001/api/upload-pdfs `
  -F "files=@test.pdf" `
  -F "course_title=Docker Test"

# Check Flower
# Open: http://localhost:5555

# Check logs
docker-compose -f docker-compose-production.yml logs -f worker-1
# Should see task processing
```

**7.4 Scale Workers**
```bash
# Add more workers
docker-compose -f docker-compose-production.yml up -d --scale worker-1=5

# Check
docker-compose -f docker-compose-production.yml ps

# Should show:
# - profai-api (1 instance)
# - profai-worker-1, worker-2, worker-3, worker-4, worker-5 (5 instances)
# - profai-redis (1 instance)
# - profai-flower (1 instance)
```

---

### STEP 8: Deploy to Local Kubernetes (Optional - 1 hour)

**8.1 Update ConfigMap**

Edit `k8s/2-configmap.yaml`:
```yaml
data:
  USE_DATABASE: "True"
  # ... other config
```

**8.2 Update Secrets**

Edit `k8s/3-secrets.yaml`:
```yaml
data:
  DATABASE_URL: <base64 encoded connection string>
  REDIS_HOST: <base64 encoded redis host>
  REDIS_PASSWORD: <base64 encoded redis password>
```

**Encode secrets:**
```bash
# Windows PowerShell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("your-database-url"))
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("your-redis-host"))
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("your-redis-password"))
```

**8.3 Deploy**
```bash
# Apply all manifests
kubectl apply -f k8s/1-namespace.yaml
kubectl apply -f k8s/2-configmap.yaml
kubectl apply -f k8s/3-secrets.yaml
kubectl apply -f k8s/4-persistent-volume.yaml

# Don't deploy Redis pod if using Upstash
# kubectl apply -f k8s/9-redis.yaml  # Skip this!

# Deploy API and Workers
kubectl apply -f k8s/5-api-deployment.yaml
kubectl apply -f k8s/6-service.yaml
kubectl apply -f k8s/10-worker-deployment.yaml

# Check status
kubectl get all -n profai

# Check logs
kubectl logs -f deployment/profai-api -n profai
kubectl logs -f deployment/profai-worker -n profai
```

**8.4 Test in K8s**
```bash
# Port forward
kubectl port-forward svc/profai-service 5001:5001 -n profai

# Test upload
curl -X POST http://localhost:5001/api/upload-pdfs `
  -F "files=@test.pdf" `
  -F "course_title=K8s Test"
```

---

## 🎯 Success Criteria

By end of today, you should have:

### ✅ Infrastructure
- [ ] Neon PostgreSQL running with schema
- [ ] Redis running (Upstash or local)
- [ ] All 10 tables created
- [ ] Existing JSON data migrated

### ✅ Application
- [ ] Celery worker running
- [ ] API server using database
- [ ] Background tasks processing
- [ ] Flower dashboard accessible

### ✅ Testing
- [ ] Can upload PDF
- [ ] Task processes in background
- [ ] Results saved to database
- [ ] Can query courses from database

### ✅ Docker
- [ ] Docker Compose working
- [ ] Can scale workers
- [ ] Logs show successful processing

### ✅ Optional (K8s)
- [ ] Deployed to local K8s
- [ ] Pods running healthy
- [ ] Auto-scaling configured

---

## 🚨 Troubleshooting

### Issue: Can't connect to Neon
```bash
# Check connection string format
# Should be: postgresql://user:pass@host/db?sslmode=require

# Test with Python
python -c "
import psycopg2
try:
    conn = psycopg2.connect('YOUR_URL')
    print('✅ Connected!')
except Exception as e:
    print(f'❌ Error: {e}')
"
```

### Issue: Celery worker not starting
```bash
# Check Redis connection
python -c "
import redis
r = redis.Redis(host='localhost', port=6379)
print(r.ping())  # Should return True
"

# Check environment variables
echo $env:REDIS_HOST
echo $env:DATABASE_URL

# Start worker with verbose logging
celery -A celery_app worker --loglevel=debug
```

### Issue: Tables not created
```sql
-- Check if migration ran
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- If empty, run migration again
\i migrations/001_initial_schema.sql
```

---

## 📞 Need Help?

**Check logs:**
```bash
# Worker logs
python worker.py  # Terminal output

# API logs
python run_profai_websocket_celery.py  # Terminal output

# Docker logs
docker-compose -f docker-compose-production.yml logs -f

# K8s logs
kubectl logs -f deployment/profai-worker -n profai
```

**Check status:**
```bash
# Flower dashboard
http://localhost:5555

# Database
SELECT * FROM job_queue ORDER BY created_at DESC;

# Redis (if local)
redis-cli
> KEYS *
> LLEN celery
```

---

## ⏭️ Tomorrow: AWS Deployment

Once everything works locally:
1. Push image to AWS ECR
2. Create EKS cluster
3. Use managed Redis (ElastiCache)
4. Deploy to production
5. Configure monitoring

**For now, focus on getting local setup working!**

---

## 🎉 You Got This!

**Timeline:**
- ☕ 10:00 AM - Set up Neon + Redis (30 min)
- 🔧 10:30 AM - Run migrations (30 min)
- 💾 11:00 AM - Migrate JSON data (30 min)
- 🧪 11:30 AM - Test locally (1 hour)
- 🐳 12:30 PM - Test Docker Compose (30 min)
- ☕ 1:00 PM - Break
- 📦 2:00 PM - Deploy to K8s (optional, 1 hour)
- ✅ 3:00 PM - Done!

**Let's get started! 🚀**
