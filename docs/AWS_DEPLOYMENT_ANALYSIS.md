# 🔍 AWS Deployment Analysis & Prerequisites

**Date:** October 25, 2025  
**Status:** Pre-AWS Deployment Review

---

## 🚨 CRITICAL ISSUE: Ingestion Pipeline is NOT Concurrent

### ❌ Current State - BLOCKING & SEQUENTIAL

#### **The Problem:**

```python
# app.py line 100-123
@app.post("/api/upload-pdfs")
async def upload_and_process_pdfs(files, course_title):
    # This is async BUT...
    course_data = await document_service.process_pdfs_and_generate_course(files, course_title)
    return course_data

# document_service.py line 24-26
async def process_pdfs_and_generate_course(self, pdf_files, course_title):
    # Just wraps a SYNC function - no real async!
    return self.process_uploaded_pdfs(pdf_files, course_title)

# document_service.py line 28-131
def process_uploaded_pdfs(self, pdf_files, course_title):
    # COMPLETELY SYNCHRONOUS:
    # 1. Save files (blocking I/O)
    # 2. Extract text from PDFs (blocking)
    # 3. Chunk documents (CPU intensive)
    # 4. Create vector store (blocking API calls)
    # 5. Generate curriculum (blocking LLM call)
    # 6. Generate content for EACH topic sequentially (blocking LLM calls)
    # 7. Save to JSON (blocking I/O)
```

#### **What This Means:**

| Scenario | What Happens | Impact |
|----------|-------------|---------|
| **User 1 uploads PDF** | Server starts processing (takes 2-5 minutes) | ✅ Works |
| **User 2 uploads PDF while User 1 processing** | Request BLOCKS until User 1 finishes | ❌ User 2 waits 5+ minutes |
| **10 users upload simultaneously** | All wait in queue, sequential processing | ❌ 10th user waits 50+ minutes! |
| **Large PDF (100 pages)** | Blocks entire server for 10+ minutes | ❌ Server unresponsive |

#### **Confirming the Issue:**

```python
# course_generator.py lines 182-196
for module in curriculum.modules:
    for sub_topic in module.sub_topics:
        # SEQUENTIAL LLM calls - one at a time!
        content = content_chain.invoke({"topic": sub_topic.title})
        sub_topic.content = content
```

**Example:**
- 10 modules × 5 topics each = 50 LLM calls
- Each LLM call = 5-10 seconds
- Total time = 4-8 minutes PER course
- **All other requests BLOCKED during this time!**

---

### ✅ REQUIRED FIX: Async Task Queue

#### **What You Need:**

1. **Background Task Queue** - Process uploads asynchronously
2. **Job Status Tracking** - Show progress to users
3. **Parallel LLM Calls** - Speed up content generation
4. **Database** - Track job status and results

#### **Recommended Architecture:**

```
User uploads PDF
    ↓
FastAPI creates background job
    ↓
Returns job_id immediately (1 second)
    ↓
User polls /api/jobs/{job_id} for status
    ↓
Background worker processes PDF
    ↓
Stores result in database
    ↓
User gets completed course
```

#### **Implementation Options:**

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **Celery + Redis** | Industry standard, battle-tested | Requires Redis server | Production |
| **FastAPI BackgroundTasks** | Built-in, simple | Not persistent, lost on restart | Light workloads |
| **AWS SQS + Lambda** | Serverless, auto-scales | More complex, AWS-specific | Cloud-native |
| **RQ (Redis Queue)** | Simpler than Celery | Requires Redis | Good middle ground |

---

## 📊 Data Storage Analysis

### Current State: Local File System

```
./data/
├── courses/
│   └── course_output.json (348KB)  ← ALL courses in ONE JSON file
├── quizzes/
│   └── course_3f03f288.json (22KB)
├── quiz_answers/
│   └── course_1_quiz_1.json (1.5KB)
├── documents/
│   └── (uploaded PDFs - temporary)
└── vectorstore/
    └── (FAISS index - if local mode)
```

### ❌ Problems with Current Approach:

1. **Single JSON File for All Courses**
   - Append-only, grows indefinitely
   - Concurrent writes = data corruption risk
   - No indexing, slow search
   - Lost if pod crashes during write

2. **No Data Persistence in Kubernetes**
   - PersistentVolume is local to node
   - Pod restarts on different node = data lost
   - No backups

3. **Vector Store**
   - Using ChromaDB Cloud (good!) OR
   - Local FAISS (bad for production - not shared across pods)

### ✅ REQUIRED: Move to Database

#### **Option 1: PostgreSQL on AWS RDS** (RECOMMENDED)

**Pros:**
- ✅ Relational data (courses, modules, quizzes)
- ✅ ACID transactions
- ✅ Automatic backups
- ✅ Multi-AZ deployment
- ✅ Free tier available

**Cons:**
- ⚠️ Requires schema design
- ⚠️ Migration needed

**Schema Design:**
```sql
courses (
  id SERIAL PRIMARY KEY,
  title VARCHAR(255),
  created_at TIMESTAMP,
  course_data JSONB  -- Store full course structure
)

modules (
  id SERIAL PRIMARY KEY,
  course_id INT REFERENCES courses(id),
  week INT,
  title VARCHAR(255),
  content TEXT
)

quizzes (
  id SERIAL PRIMARY KEY,
  course_id INT REFERENCES courses(id),
  quiz_data JSONB
)

quiz_answers (
  id SERIAL PRIMARY KEY,
  quiz_id INT REFERENCES quizzes(id),
  user_id VARCHAR(100),
  answers JSONB,
  score INT
)

job_status (
  id SERIAL PRIMARY KEY,
  job_id UUID UNIQUE,
  status VARCHAR(50),  -- pending, processing, completed, failed
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  result JSONB
)
```

#### **Option 2: Neon PostgreSQL** (Serverless)

**Pros:**
- ✅ Serverless (auto-scales)
- ✅ Generous free tier
- ✅ Fast cold starts
- ✅ PostgreSQL compatible

**Cons:**
- ⚠️ Third-party service
- ⚠️ Potential vendor lock-in

#### **Option 3: DynamoDB** (AWS Native)

**Pros:**
- ✅ Serverless, auto-scales
- ✅ Pay per request
- ✅ No servers to manage

**Cons:**
- ❌ NoSQL learning curve
- ❌ Complex queries difficult
- ❌ Not ideal for relational data

#### **My Recommendation: PostgreSQL on AWS RDS**

Why:
1. Your data is relational (courses → modules → topics)
2. Free tier available (db.t3.micro)
3. Automatic backups
4. Easy to query and manage
5. Battle-tested for production

---

## 🔐 Secrets Management

### Current State: Base64 in secrets.yaml

```yaml
# k8s/3-secrets.yaml
data:
  OPENAI_API_KEY: "eW91ci1vcGVuYWktYXBpLWtleS1oZXJl"  # Base64, NOT encrypted!
  SARVAM_API_KEY: "..."
  GROQ_API_KEY: "..."
  ELEVENLABS_API_KEY: "..."
```

### ❌ Problems:

1. **Base64 is NOT encryption** - Anyone can decode
2. **Stored in Git** - Security risk
3. **Hard to rotate** - Must rebuild manifests
4. **No audit trail** - Who accessed which key?

### ✅ REQUIRED: AWS Secrets Manager

#### **Migration:**

```yaml
# Instead of this in secrets.yaml:
data:
  OPENAI_API_KEY: "eW91ci1..."

# Use this in deployment.yaml:
env:
- name: OPENAI_API_KEY
  valueFrom:
    secretKeyRef:
      name: aws-secrets
      key: openai_api_key
```

#### **Setup:**

```bash
# Store secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name profai/openai-api-key \
  --secret-string "sk-proj-your-actual-key"

# Install AWS Secrets CSI Driver in K8s
kubectl apply -f https://raw.githubusercontent.com/aws/secrets-store-csi-driver-provider-aws/main/deployment/aws-provider-installer.yaml

# Create SecretProviderClass
# Secrets auto-sync to K8s
```

**Benefits:**
- ✅ Encrypted at rest
- ✅ Rotation without downtime
- ✅ Audit logging
- ✅ IAM permissions
- ✅ No secrets in Git

---

## 🗂️ Other Configuration Requirements

### 1. Environment-Specific ConfigMaps

**Current:** One configmap for all environments

**Needed:** Separate configs for dev/staging/prod

```
k8s/
├── base/
│   ├── deployment.yaml
│   └── service.yaml
├── overlays/
│   ├── dev/
│   │   └── configmap.yaml (DEBUG=True, small resources)
│   ├── staging/
│   │   └── configmap.yaml (DEBUG=False, medium resources)
│   └── prod/
│       └── configmap.yaml (DEBUG=False, full resources)
```

### 2. Resource Limits for Production

**Current (local testing):**
```yaml
resources:
  requests:
    memory: 512Mi
    cpu: 250m
  limits:
    memory: 1Gi
    cpu: 500m
```

**Production (AWS):**
```yaml
resources:
  requests:
    memory: 2Gi    # Increased for LLM processing
    cpu: 1000m
  limits:
    memory: 4Gi
    cpu: 2000m
```

### 3. Logging Configuration

**Needed:**
- CloudWatch Logs integration
- Structured JSON logging
- Log levels by environment
- Log retention policies

### 4. Monitoring & Alerts

**Required AWS Services:**
- CloudWatch Container Insights
- X-Ray for distributed tracing
- Prometheus + Grafana (optional)
- Alert on errors, high latency, pod restarts

---

## 📋 AWS Deployment Prerequisites

### Account & Access

| Requirement | Status | Notes |
|-------------|--------|-------|
| **AWS Account** | ⏳ Need to verify | Free tier sufficient initially |
| **AWS CLI installed** | ⏳ Need to install | Version 2.x required |
| **AWS credentials configured** | ⏳ Need to setup | Access key + Secret key |
| **kubectl installed** | ✅ Already have | From Stage 3 |
| **Docker installed** | ✅ Already have | From Stage 1 |
| **eksctl installed** | ⏳ Need to install | For EKS cluster creation |

### AWS Services We'll Use

| Service | Purpose | Cost Estimate (Free Tier) |
|---------|---------|---------------------------|
| **ECR** | Docker image registry | Free for 500MB/month |
| **EKS** | Kubernetes cluster | $0.10/hour ($72/month) |
| **RDS** | PostgreSQL database | Free tier: db.t3.micro |
| **Secrets Manager** | API keys storage | $0.40/secret/month |
| **CloudWatch** | Logs & monitoring | Free tier: 5GB/month |
| **ALB** | Load balancer | ~$16/month |
| **EBS** | Persistent volumes | Free tier: 30GB |
| **VPC** | Networking | Free |

**Estimated Monthly Cost:** ~$90-100 (after free tier expires)

### Domain & SSL (Optional but Recommended)

| Item | Status | Notes |
|------|--------|-------|
| **Domain name** | ⏳ Optional | e.g., profai.yourdomain.com |
| **Route 53** | ⏳ If using domain | DNS hosting |
| **ACM Certificate** | ⏳ If using HTTPS | Free SSL certificate |

---

## 🚀 Recommended Deployment Order

### Phase 1: Critical Fixes (Before AWS) ⚠️ MUST DO FIRST

1. **Fix Ingestion Pipeline**
   - Implement background task queue (Celery + Redis)
   - Add job status tracking
   - Parallelize LLM calls
   - Estimated time: 4-6 hours

2. **Migrate to Database**
   - Design PostgreSQL schema
   - Migrate existing JSON data
   - Update all read/write operations
   - Estimated time: 4-6 hours

3. **Update Application Code**
   - Replace file I/O with database calls
   - Add proper error handling
   - Implement retry logic
   - Estimated time: 2-3 hours

### Phase 2: AWS Infrastructure Setup

4. **Set up AWS Account & CLI**
   - Create/verify AWS account
   - Install AWS CLI
   - Configure credentials
   - Estimated time: 30 minutes

5. **Create ECR Repository**
   - Push Docker image
   - Tag for versioning
   - Estimated time: 30 minutes

6. **Set up RDS PostgreSQL**
   - Create database instance
   - Configure security groups
   - Initialize schema
   - Estimated time: 1 hour

7. **Configure Secrets Manager**
   - Migrate API keys
   - Set up IAM roles
   - Estimated time: 1 hour

### Phase 3: EKS Deployment

8. **Create EKS Cluster**
   - Install eksctl
   - Create cluster with node groups
   - Estimated time: 30 minutes (cluster creation takes 15-20 min)

9. **Deploy Application**
   - Update K8s manifests for AWS
   - Deploy to EKS
   - Configure ALB Ingress
   - Estimated time: 2 hours

10. **Set up Monitoring**
    - CloudWatch Container Insights
    - Logging configuration
    - Alerts
    - Estimated time: 1-2 hours

---

## ⚠️ CRITICAL DECISION NEEDED

### Option A: Fix Issues First (RECOMMENDED)

**Timeline:**
- Day 1: Fix ingestion pipeline (async/queue)
- Day 2: Migrate to database
- Day 3: Deploy to AWS with proper architecture

**Pros:**
- ✅ Production-ready from day 1
- ✅ Handles concurrent users
- ✅ Data persistence
- ✅ No technical debt

**Cons:**
- ⏰ Takes longer to deploy to AWS
- ⏰ More upfront work

### Option B: Deploy to AWS First, Fix Later

**Timeline:**
- Day 1: Deploy current code to AWS
- Day 2+: Fix issues in production

**Pros:**
- ✅ Faster AWS deployment
- ✅ Learn AWS quickly

**Cons:**
- ❌ Production system with known issues
- ❌ Can't handle concurrent users
- ❌ Data loss risk
- ❌ More expensive (running broken system)
- ❌ Technical debt from day 1

---

## 💡 My Strong Recommendation

### DO THIS ORDER:

1. **TODAY: Fix Concurrency** (CRITICAL)
   - Implement FastAPI BackgroundTasks (quick fix)
   - Add job_id tracking
   - Return job_id immediately
   - Process in background
   - Estimated: 2-3 hours

2. **TOMORROW: Set up Database**
   - Use Neon PostgreSQL (easiest, free tier)
   - Migrate JSON data
   - Update application code
   - Estimated: 4-6 hours

3. **DAY 3: Deploy to AWS**
   - With working concurrency
   - With proper data persistence
   - Production-ready architecture

**Why This Order:**
- You learn the fixes BEFORE deploying
- No surprises in production
- Better understanding of the system
- Cleaner AWS deployment

---

## 📝 Next Steps

### Immediate Actions Needed:

1. **Confirm Understanding**
   - Do you agree the pipeline is blocking?
   - Do you want to fix before AWS or deploy and fix later?

2. **Choose Database**
   - PostgreSQL on AWS RDS?
   - Neon PostgreSQL (serverless)?
   - Keep JSON files (NOT recommended)?

3. **Choose Task Queue**
   - FastAPI BackgroundTasks (simple, quick)?
   - Celery + Redis (production-grade)?
   - AWS SQS + Lambda (cloud-native)?

4. **AWS Account**
   - Do you have AWS account?
   - Have you used AWS before?
   - Need help with free tier setup?

---

## 🎯 Summary

| Issue | Severity | Impact | Fix Required |
|-------|----------|--------|--------------|
| **Blocking ingestion** | 🔴 CRITICAL | Can't handle concurrent users | YES - Before AWS |
| **JSON file storage** | 🟠 HIGH | Data loss risk | YES - Use database |
| **Local vector store** | 🟠 HIGH | Not shared across pods | Switch to Chroma Cloud |
| **Base64 secrets** | 🟡 MEDIUM | Security risk | Use AWS Secrets Manager |
| **No monitoring** | 🟡 MEDIUM | Can't debug issues | Add CloudWatch |

**Bottom Line:** Your application works great for single users locally, but needs architecture changes for production AWS deployment with multiple concurrent users.

**Time Investment:**
- Quick fixes: 6-8 hours
- Proper fixes: 12-16 hours
- AWS deployment: 4-6 hours
- **Total: 2-3 days for production-ready AWS deployment**

---

**Ready to discuss which approach you prefer?** 🚀
