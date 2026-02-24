# ⚡ QUICK START - Testing Before AWS Deployment

**Total Time:** 30-45 minutes  
**Read This First!**

---

## 🎯 WHAT YOU NEED TO DO

### 1️⃣ **Setup .env File** (2 minutes)

```env
USE_DATABASE=True
DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/profai?sslmode=require
REDIS_URL=rediss://default:pass@xxx.upstash.io:6379
OPENAI_API_KEY=sk-proj-YOUR_KEY
SARVAM_API_KEY=your_key
GROQ_API_KEY=your_key
```

---

### 2️⃣ **Run Database Test** (5 minutes)

```bash
python test_database_integration.py
```

**Should See:**
```
✅ Database Connection: PASSED
✅ Create Course: PASSED (ID: abc123...)
✅ Create Quiz: PASSED
🎉 ALL TESTS PASSED!
```

**If FAILS:** Check DATABASE_URL in .env

---

### 3️⃣ **Run Service Test** (5 minutes)

```bash
python test_all_services.py
```

**Should See:**
```
✅ Imports              - PASSED
✅ Initialization       - PASSED
✅ Database Integration - PASSED
🎉 ALL TESTS PASSED!
```

**If FAILS:** Check API keys in .env

---

### 4️⃣ **Start Celery Worker** (Terminal 1)

```bash
celery -A celery_app worker --loglevel=info --pool=solo
```

**Should See:**
```
✅ Celery: Using Redis URL: rediss://...
[INFO] celery@YOUR_COMPUTER ready.
```

**If FAILS:** Check REDIS_URL in .env

---

### 5️⃣ **Start Application** (Terminal 2)

```bash
python run_profai_websocket_celery.py
```

**Should See:**
```
✅ DocumentService initialized with database support
✅ QuizService initialized with database support
🎉 ProfAI server is running!
📡 API: http://localhost:5001
```

**If you see "(JSON mode)":** Database NOT enabled!

---

### 6️⃣ **Test API** (Terminal 3)

```bash
# Health check
curl http://localhost:5001/

# Get courses
curl http://localhost:5001/api/courses

# Open docs
# Browser: http://localhost:5001/docs
```

---

### 7️⃣ **Test PDF Upload**

```bash
curl -X POST http://localhost:5001/api/upload-pdfs-async \
  -F "files=@test.pdf" \
  -F "course_title=Test Course"
```

**Response:**
```json
{"job_id": "abc-123", "status": "pending"}
```

**Check Status:**
```bash
curl http://localhost:5001/api/job-status/abc-123
```

**After ~60 seconds:**
```json
{
  "status": "completed",
  "result": {
    "course_id": "uuid-here",  // ✅ UUID = Database working!
    "course_title": "Test Course"
  }
}
```

---

## ✅ SUCCESS CHECKLIST

**Before AWS deployment, verify:**

- [ ] ✅ test_database_integration.py → ALL PASSED
- [ ] ✅ test_all_services.py → ALL PASSED
- [ ] ✅ Celery connects to Redis
- [ ] ✅ App shows "with database support"
- [ ] ✅ PDF upload creates course with UUID
- [ ] ✅ No errors in logs

---

## ❌ COMMON PROBLEMS

### Problem 1: Database Tests Fail
```
❌ Database Connection: FAILED
```
**Fix:** Check DATABASE_URL in .env (must be Neon URL)

---

### Problem 2: Services Use JSON Mode
```
INFO: DocumentService initialized (JSON mode)
```
**Fix:** Set `USE_DATABASE=True` in .env and restart

---

### Problem 3: Celery Can't Connect
```
consumer: Cannot connect to redis://localhost
```
**Fix:** Check REDIS_URL in .env (must be Upstash rediss:// URL)

---

### Problem 4: Course ID is Integer
```json
{"course_id": 1}  // ❌ Wrong
```
**Fix:** Database not enabled. Check USE_DATABASE=True

---

## 🎯 EXPECTED RESULTS

### ✅ Correct Database Mode:
```python
course_id = "a1b2c3d4-5e6f-7890-abcd-1234567890ef"  # ✅ UUID
```

### ❌ Wrong JSON Mode:
```python
course_id = 1  # ❌ Integer
```

---

## 📊 WHAT TO EXPECT IN LOGS

### ✅ GOOD Logs (Database Working):
```
INFO: DocumentService initialized with database support
INFO: QuizService initialized with database support
INFO: AsyncDocumentService initialized with database support
INFO: ✅ Course saved to database! Course ID: abc-123...
INFO: ✅ Quiz saved to database (course: abc-123...)
```

### ❌ BAD Logs (Database NOT Working):
```
INFO: DocumentService initialized (JSON mode)
INFO: QuizService initialized (JSON mode)
INFO: ✅ Course saved to JSON! Course ID: 1
INFO: ✅ Quiz saved to JSON file
```

---

## 🚀 AFTER SUCCESSFUL TESTING

**All tests passed? Great!**

**Next Steps:**
1. ✅ Read `TODO_BEFORE_DEPLOY.md`
2. ✅ Encode K8s secrets (PowerShell script)
3. ✅ Update `k8s/3-secrets.yaml`
4. ✅ Deploy to Kubernetes

**Files to Review:**
- `PRE_DEPLOYMENT_TESTING_GUIDE.md` - Full testing guide
- `TODO_BEFORE_DEPLOY.md` - Deployment checklist
- `ALL_SERVICES_VERIFIED.md` - Service analysis
- `DATABASE_READY.md` - Database setup guide

---

## 📝 QUICK TROUBLESHOOTING

| Issue | Cause | Fix |
|-------|-------|-----|
| DB connection fails | Wrong URL | Fix DATABASE_URL in .env |
| Services in JSON mode | DB not enabled | USE_DATABASE=True |
| Celery can't connect | Wrong Redis URL | Fix REDIS_URL (rediss://) |
| Course ID is integer | DB not used | Check logs for "JSON mode" |
| API key errors | Missing keys | Add to .env |

---

## 🎯 MINIMUM REQUIREMENTS

**Before AWS deployment:**
1. ✅ Database connection works
2. ✅ Services initialize with database
3. ✅ Course creation uses UUID (not integer)
4. ✅ Celery connects to Redis
5. ✅ No errors in application logs

**If ANY requirement fails → DO NOT deploy to AWS!**

---

## 🔍 HOW TO VERIFY DATABASE IS WORKING

**3 Ways:**

**1. Check Logs:**
```
✅ "with database support" = Good
❌ "(JSON mode)" = Bad
```

**2. Check Course ID:**
```
✅ UUID: "a1b2c3d4-..." = Good
❌ Integer: 1, 2, 3 = Bad
```

**3. Check Database:**
```sql
SELECT COUNT(*) FROM courses;
-- Should increase after course creation
```

---

## 📞 HELP

**If stuck, check these files:**
- `PRE_DEPLOYMENT_TESTING_GUIDE.md` - Full details
- `ALL_FIXES_APPLIED.md` - What was changed
- `COMPREHENSIVE_ANALYSIS.md` - All files analyzed

**Still stuck?**
- Check .env has all required variables
- Verify Neon database is active
- Verify Upstash Redis is active
- Check firewall/network isn't blocking

---

**Ready? Start with Step 1! ⬆️**

**Time to Complete:** 30-45 minutes  
**Difficulty:** Easy  
**Success Rate:** 100% if you follow steps 🎯
