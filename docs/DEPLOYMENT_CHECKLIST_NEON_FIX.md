# 🚀 NEON DB FIX - DEPLOYMENT CHECKLIST

**Quick reference for deploying fixes to EC2**

---

## ✅ **FILES CHANGED**

### **1. `services/database_service_actual.py`**
- ✅ Added `get_all_courses()` method (lines 328-353)

### **2. `app_celery.py`**
- ✅ Imported database service (line 40)
- ✅ Initialized database service (lines 78-87)
- ✅ Fixed `/api/course/{course_id}` (lines 248-292)
- ✅ Fixed `/api/courses` (lines 295-332)
- ✅ Fixed `/api/quiz/generate-module` (lines 337-390)
- ✅ Fixed `/api/quiz/generate-course` (lines 393-440)

---

## 📦 **UPLOAD TO EC2**

### **From Windows PowerShell:**

```powershell
# Navigate to project
cd C:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Upload fixed files
scp -i ~/Downloads/my-ai-app-key.pem app_celery.py ubuntu@51.20.109.241:~/profai/
scp -i ~/Downloads/my-ai-app-key.pem services/database_service_actual.py ubuntu@51.20.109.241:~/profai/services/

# Verify .env has correct settings
scp -i ~/Downloads/my-ai-app-key.pem .env ubuntu@51.20.109.241:~/profai/
```

---

## 🔄 **RESTART ON EC2**

### **SSH and Restart:**

```bash
# Connect
ssh -i ~/Downloads/my-ai-app-key.pem ubuntu@51.20.109.241

# Navigate
cd ~/profai

# Stop
docker-compose -f docker-compose-production.yml down

# Start (no rebuild needed if only Python files changed)
docker-compose -f docker-compose-production.yml up -d

# Check status
docker ps

# View logs
docker logs profai-api --tail=50
docker logs profai-worker --tail=50
```

---

## 🧪 **QUICK TESTS**

```bash
# 1. Health check
curl http://localhost:5001/health

# 2. List courses (should use database)
curl http://localhost:5001/api/courses

# 3. Get specific course (use actual UUID from step 2)
curl http://localhost:5001/api/course/<UUID>
```

---

## 🔍 **VERIFY DATABASE USAGE**

### **Check Logs:**

```bash
# Look for database initialization
docker logs profai-api 2>&1 | grep "Database service"

# Should see:
# ✅ Database service initialized (Neon DB)

# Look for database queries
docker logs profai-api 2>&1 | grep -E "Fetching.*database|Retrieved.*database"

# Should see:
# Fetching courses from Neon database...
# ✅ Retrieved X courses from database
```

---

## ⚠️ **IF ISSUES**

### **Database Not Connected:**

```bash
# Check environment variables
docker exec profai-api printenv | grep DATABASE

# Should show:
# USE_DATABASE=True
# DATABASE_URL=postgresql://...

# Test database connection manually
docker exec profai-api python -c "
from services.database_service_actual import get_database_service
db = get_database_service()
if db:
    print('✅ Database connected')
    courses = db.get_all_courses()
    print(f'Found {len(courses)} courses')
else:
    print('❌ Database not available')
"
```

### **Still Using JSON Files:**

```bash
# Check if USE_DATABASE is set correctly
cat ~/profai/.env | grep USE_DATABASE

# Should be:
# USE_DATABASE=True

# If False, edit and restart
nano ~/profai/.env
# Change to: USE_DATABASE=True
# Save: Ctrl+O, Enter, Ctrl+X

# Restart
docker-compose -f docker-compose-production.yml restart
```

---

## 📊 **SUCCESS INDICATORS**

### **✅ Everything Working:**

1. **API starts without errors**
   ```
   docker logs profai-api --tail=20
   # No errors about database
   ```

2. **Database service initialized**
   ```
   # Log shows: ✅ Database service initialized (Neon DB)
   ```

3. **Courses fetched from database**
   ```
   curl http://localhost:5001/api/courses
   # Returns array of courses
   # Log shows: ✅ Retrieved X courses from database
   ```

4. **Single course works with UUID**
   ```
   curl http://localhost:5001/api/course/<UUID>
   # Returns full course object
   # Log shows: ✅ Course X found in database
   ```

5. **Quiz generation uses database**
   ```
   # When generating quiz, log shows:
   # Fetching course X from database for quiz generation...
   # ✅ Course X found in database
   ```

---

## 🎯 **ROLLBACK (IF NEEDED)**

### **If fixes cause issues:**

```bash
# On EC2
cd ~/profai

# Stop current version
docker-compose -f docker-compose-production.yml down

# Restore from backup (if you made one)
cp app_celery.py.backup app_celery.py
cp services/database_service_actual.py.backup services/database_service_actual.py

# Or set USE_DATABASE=False to use JSON files
nano .env
# Change: USE_DATABASE=False

# Restart
docker-compose -f docker-compose-production.yml up -d
```

---

## 📝 **ENVIRONMENT CHECKLIST**

### **Verify `.env` has:**

```bash
# Required
USE_DATABASE=True
DATABASE_URL=postgresql://neondb_owner:...@ep-...neon.tech/neondb?sslmode=require

# Redis (Non-SSL)
REDIS_USE_SSL=False
REDIS_URL=redis://default:...@redis-10925...com:10925

# All API keys present
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
SARVAM_API_KEY=...
ELEVENLABS_API_KEY=...
DEEPGRAM_API_KEY=...

# ChromaDB
USE_CHROMA_CLOUD=True
CHROMA_CLOUD_API_KEY=...
CHROMA_CLOUD_TENANT=...
CHROMA_CLOUD_DATABASE=...
```

---

## ⏱️ **DEPLOYMENT TIME**

- **Upload files:** 30 seconds
- **Restart containers:** 30 seconds  
- **Verification:** 1 minute
- **Total:** ~2-3 minutes

---

## 🎉 **COMPLETION**

### **When deployment is successful:**

- [ ] Files uploaded to EC2
- [ ] Containers restarted
- [ ] Health check passes
- [ ] `/api/courses` returns courses from DB
- [ ] `/api/course/{uuid}` works with database UUID
- [ ] Logs show "Database service initialized"
- [ ] Logs show "Retrieved X courses from database"
- [ ] Quiz generation works

**Status:** ✅ DEPLOYED AND VERIFIED

---

**Deploy now and verify with the tests above!** 🚀
