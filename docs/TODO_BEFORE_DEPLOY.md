# ⚠️ TODO BEFORE KUBERNETES DEPLOYMENT

## 🔴 CRITICAL - Must Complete Before Deploying

### 1. Update K8s Secrets with Your Actual Values (10 minutes)

**File:** `k8s/3-secrets.yaml`

**Current Status:** ❌ Contains placeholder values  
**Required:** ✅ Replace with your actual base64-encoded secrets

#### Step-by-Step:

```powershell
# 1. Encode DATABASE_URL
$dbUrl = "YOUR_ACTUAL_NEON_DATABASE_URL_HERE"
# Example: postgresql://user:pass@ep-cool-pond-123456.us-east-2.aws.neon.tech/profai?sslmode=require
$dbUrlEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($dbUrl))
Write-Host "DATABASE_URL: $dbUrlEncoded"

# 2. Encode REDIS_URL
$redisUrl = "YOUR_ACTUAL_UPSTASH_REDIS_URL_HERE"
# Example: rediss://default:Ax9p...@faithful-martin-8847.upstash.io:6379
$redisUrlEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($redisUrl))
Write-Host "REDIS_URL: $redisUrlEncoded"

# 3. Encode other API keys (if not already done)
$openaiKey = "YOUR_OPENAI_API_KEY"
$openaiEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($openaiKey))
Write-Host "OPENAI_API_KEY: $openaiEncoded"

$sarvamKey = "YOUR_SARVAM_API_KEY"
$sarvamEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sarvamKey))
Write-Host "SARVAM_API_KEY: $sarvamEncoded"

$groqKey = "YOUR_GROQ_API_KEY"
$groqEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($groqKey))
Write-Host "GROQ_API_KEY: $groqEncoded"
```

**Then update `k8s/3-secrets.yaml`:**
```yaml
data:
  OPENAI_API_KEY: "<paste_encoded_value_here>"
  SARVAM_API_KEY: "<paste_encoded_value_here>"
  GROQ_API_KEY: "<paste_encoded_value_here>"
  DATABASE_URL: "<paste_encoded_value_here>"
  REDIS_URL: "<paste_encoded_value_here>"
```

---

### 2. Update Worker Deployment (if using separate workers) (5 minutes)

**File:** `k8s/10-worker-deployment.yaml`

**Add these env vars** (same as in `5-deployment.yaml`):
```yaml
env:
  # ... existing env vars ...
  
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: profai-secrets
        key: DATABASE_URL
  - name: REDIS_URL
    valueFrom:
      secretKeyRef:
        name: profai-secrets
        key: REDIS_URL
```

---

### 3. Update API-Only Deployment (if using separate API pods) (5 minutes)

**File:** `k8s/5-api-deployment.yaml`

**Add these env vars** (same as in `5-deployment.yaml`):
```yaml
env:
  # ... existing env vars ...
  
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: profai-secrets
        key: DATABASE_URL
  - name: REDIS_URL
    valueFrom:
      secretKeyRef:
        name: profai-secrets
        key: REDIS_URL
```

---

## 🟡 IMPORTANT - Test Before Deploying to K8s

### 4. Test Database Integration Locally (5 minutes)

```bash
# Navigate to project
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Ensure .env has database enabled
# Add these to .env if not present:
USE_DATABASE=True
DATABASE_URL=postgresql://...@neon.tech/profai?sslmode=require

# Run integration test
python test_database_integration.py
```

**Expected Output:**
```
✅ Database Connection: PASSED
✅ List Courses: PASSED (X courses found)
✅ Create Course: PASSED (ID: abc123...)
✅ Retrieve Course: PASSED
✅ Create Quiz: PASSED
✅ Retrieve Quiz: PASSED

🎉 ALL TESTS PASSED!
```

**If tests fail:** Check your DATABASE_URL in `.env`

---

### 5. Test Local Application with Database (10 minutes)

```bash
# Terminal 1: Start Celery Worker
celery -A celery_app worker --loglevel=info --pool=solo

# Terminal 2: Start Application
python run_profai_websocket_celery.py

# Look for these log messages:
# ✅ DocumentService initialized with database support
# ✅ QuizService initialized with database support
# ✅ AsyncDocumentService initialized with database support
```

**Test endpoints:**
```bash
# Terminal 3: Test API
curl http://localhost:5001/api/courses

# Should return courses (from database if any exist)
```

---

## 🟢 RECOMMENDED - Before Production

### 6. Verify Neon Database Connection (2 minutes)

```bash
# Test connection directly
psql "YOUR_DATABASE_URL"

# Or use Neon UI:
# 1. Go to https://neon.tech
# 2. Select your project
# 3. Go to SQL Editor
# 4. Run: SELECT * FROM courses LIMIT 5;
```

---

### 7. Verify Upstash Redis Connection (2 minutes)

```bash
# In Python
python -c "import redis; r = redis.from_url('YOUR_REDIS_URL'); print('✅ Connected!' if r.ping() else '❌ Failed')"
```

---

### 8. Check K8s Cluster Status (5 minutes)

```bash
# Check if Docker Desktop K8s is running
kubectl cluster-info

# Should show:
# Kubernetes control plane is running at https://kubernetes.docker.internal:6443

# Check available resources
kubectl top nodes

# Should show CPU/Memory availability
```

---

## ⚪ OPTIONAL - Nice to Have

### 9. Mark Deprecated Database Services (2 minutes)

**File:** `services/database_service.py`  
**File:** `services/database_service_new.py`

**Add to top of each file:**
```python
"""
⚠️ DEPRECATED - Use database_service_actual.py instead
This file uses an incorrect schema and should not be used.
"""
```

---

### 10. Update K8s README (10 minutes)

**File:** `k8s/README.md`

**Add section:**
```markdown
## Database Configuration

### Prerequisites
1. Neon PostgreSQL database (create at https://neon.tech)
2. Upstash Redis (create at https://upstash.com)

### Setup Secrets
1. Encode your DATABASE_URL:
   ```powershell
   [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("YOUR_DB_URL"))
   ```

2. Update `3-secrets.yaml` with encoded values

3. Apply secrets:
   ```bash
   kubectl apply -f 3-secrets.yaml
   ```

### Verify
```bash
kubectl exec deployment/profai-deployment -n profai -- env | grep DATABASE_URL
```
```

---

## 📋 DEPLOYMENT CHECKLIST

Copy this to track your progress:

```
PRE-DEPLOYMENT:
[ ] 1. Encoded DATABASE_URL and updated k8s/3-secrets.yaml
[ ] 2. Encoded REDIS_URL and updated k8s/3-secrets.yaml
[ ] 3. Encoded all API keys and updated k8s/3-secrets.yaml
[ ] 4. Updated worker deployment with DB env vars (if applicable)
[ ] 5. Updated API deployment with DB env vars (if applicable)
[ ] 6. Tested database integration locally (python test_database_integration.py)
[ ] 7. Tested local application with database enabled
[ ] 8. Verified Neon database connection
[ ] 9. Verified Upstash Redis connection
[ ] 10. Checked K8s cluster is running (kubectl cluster-info)

LOCAL K8S DEPLOYMENT:
[ ] 11. Apply namespace: kubectl apply -f k8s/1-namespace.yaml
[ ] 12. Apply configmap: kubectl apply -f k8s/2-configmap.yaml
[ ] 13. Apply secrets: kubectl apply -f k8s/3-secrets.yaml
[ ] 14. Apply PVC: kubectl apply -f k8s/4-persistent-volume.yaml
[ ] 15. Apply deployment: kubectl apply -f k8s/5-deployment.yaml
[ ] 16. Apply service: kubectl apply -f k8s/6-service.yaml
[ ] 17. Apply ingress: kubectl apply -f k8s/7-ingress.yaml (optional)
[ ] 18. Apply HPA: kubectl apply -f k8s/8-hpa.yaml

VERIFICATION:
[ ] 19. Check pods are running: kubectl get pods -n profai
[ ] 20. Check logs: kubectl logs -f deployment/profai-deployment -n profai
[ ] 21. Port forward: kubectl port-forward svc/profai-service 5001:5001 -n profai
[ ] 22. Test API: curl http://localhost:5001/api/courses
[ ] 23. Upload PDF and verify course in database
[ ] 24. Generate quiz and verify in database

OPTIONAL:
[ ] 25. Mark deprecated database services
[ ] 26. Update K8s README with database setup
```

---

## 🚨 TROUBLESHOOTING

### Issue: Pods are CrashLooping
```bash
# Check logs
kubectl logs deployment/profai-deployment -n profai

# Common causes:
# 1. DATABASE_URL not set or invalid
# 2. Missing secrets
# 3. Database connection refused
```

### Issue: Database connection fails
```bash
# Check if DATABASE_URL env var is present
kubectl exec deployment/profai-deployment -n profai -- env | grep DATABASE_URL

# Test connection manually
kubectl exec -it deployment/profai-deployment -n profai -- python -c "from services.database_service_actual import get_database_service; db = get_database_service(); print('✅ Connected!' if db else '❌ Failed')"
```

### Issue: Secrets not found
```bash
# Check if secrets exist
kubectl get secrets -n profai

# Check secret contents (base64 encoded)
kubectl get secret profai-secrets -n profai -o yaml

# Reapply if needed
kubectl delete secret profai-secrets -n profai
kubectl apply -f k8s/3-secrets.yaml
```

---

## 📞 QUICK REFERENCE

### Get Your Secrets:
- **Neon Dashboard:** https://console.neon.tech
- **Upstash Dashboard:** https://console.upstash.com
- **OpenAI Keys:** https://platform.openai.com/api-keys

### Encode Commands:
```powershell
# DATABASE_URL
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("postgres://..."))

# REDIS_URL
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("rediss://..."))

# API Keys
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("sk-..."))
```

### Test Database:
```bash
python test_database_integration.py
```

### Start Local:
```bash
# Terminal 1
celery -A celery_app worker --loglevel=info --pool=solo

# Terminal 2
python run_profai_websocket_celery.py
```

### Deploy K8s:
```bash
kubectl apply -f k8s/
kubectl get pods -n profai
kubectl logs -f deployment/profai-deployment -n profai
```

---

## ✅ COMPLETION CRITERIA

You're ready to deploy when:

✅ All secrets are encoded and updated in `k8s/3-secrets.yaml`  
✅ Local database test passes (`test_database_integration.py`)  
✅ Local application starts with database support  
✅ K8s cluster is running  
✅ All checklist items are completed  

**Then proceed with K8s deployment!** 🚀

---

## 📝 NOTES

- **Secrets are base64 encoded, NOT encrypted** - For production, consider AWS Secrets Manager or HashiCorp Vault
- **Database URL format:** `postgresql://user:pass@host.neon.tech/dbname?sslmode=require`
- **Redis URL format:** `rediss://default:password@host.upstash.io:6379`
- **Testing locally first** prevents debugging in K8s (much harder)
- **Check logs frequently** during deployment to catch issues early

---

**Last Updated:** After comprehensive analysis and fixes  
**Next Action:** Complete items 1-10, then deploy! 🎯
