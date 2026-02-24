# 📦 DEPENDENCY UPDATES - SUMMARY

All required files updated for hybrid RAG deployment.

---

## ✅ **FILES UPDATED**

### **1. `requirements.txt`** ✅

**Added:**
```txt
# --- Hybrid RAG & Reranking ---
# Sentence transformers for cross-encoder reranking
sentence-transformers==2.2.2
# BM25 for sparse/keyword-based retrieval
rank-bm25==0.2.2
```

**Location:** Lines 138-142

---

### **2. `config.py`** ✅

**Added:**
```python
# Increased RETRIEVAL_K from 2 to 4 for better context
RETRIEVAL_K = 4

# --- Hybrid RAG Settings ---
HYBRID_RETRIEVAL_K = 10      # Documents to retrieve before reranking
HYBRID_ALPHA = 0.6           # 60% vector, 40% BM25 weight
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

**Location:** Lines 77-87

---

### **3. `Dockerfile`** ✅

**No changes needed!** 

The Dockerfile already:
- Copies `requirements.txt` (line 24)
- Runs `pip install -r requirements.txt` (line 26)

This means the new dependencies will be automatically installed when building the Docker image.

---

### **4. `docker-compose.yml`** ✅

**No changes needed!**

This file uses the Dockerfile which installs from requirements.txt.

---

### **5. `docker-compose-production.yml`** ✅

**No changes needed!**

This file also uses the Dockerfile which installs from requirements.txt.

---

## 🔄 **HOW IT WORKS**

### **Dependency Installation Flow:**

```
requirements.txt (updated)
    ↓
Dockerfile: COPY requirements.txt /tmp/
    ↓
Dockerfile: RUN pip install -r /tmp/requirements.txt
    ↓
Docker image contains all dependencies
    ↓
docker-compose.yml builds image
    ↓
Containers have all new libraries
```

---

## 📋 **NEW DEPENDENCIES ADDED**

| Package | Version | Purpose |
|---------|---------|---------|
| `sentence-transformers` | 2.2.2 | Cross-encoder reranking model |
| `rank-bm25` | 0.2.2 | BM25 sparse/keyword search |

---

## 🚀 **DEPLOYMENT METHODS**

### **Method 1: Full Rebuild (Recommended for Production)**

Rebuild Docker image with new dependencies:

```bash
# On EC2
cd ~/profai
docker-compose -f docker-compose-production.yml build --no-cache
docker-compose -f docker-compose-production.yml up -d
```

**Time:** 5-10 minutes (full rebuild)

---

### **Method 2: Quick Install (Faster, Good for Testing)**

Install dependencies in running container:

```bash
# On EC2
docker exec -it profai-api pip install sentence-transformers==2.2.2 rank-bm25==0.2.2
docker restart profai-api
```

**Time:** 2-3 minutes

**Note:** This is temporary. Dependencies will be lost if container is recreated. Use Method 1 for permanent installation.

---

### **Method 3: Local Testing**

Install on your local machine:

```powershell
# Windows PowerShell
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI
pip install sentence-transformers==2.2.2 rank-bm25==0.2.2
```

---

## ✅ **VERIFICATION**

### **After Installation, Verify:**

```bash
# Check installed packages
docker exec -it profai-api pip list | grep -E "sentence|rank"
```

**Expected Output:**
```
rank-bm25                 0.2.2
sentence-transformers     2.2.2
```

---

### **Check Logs for Initialization:**

```bash
docker logs profai-api --tail=50 | grep -E "BM25|cross-encoder|Hybrid"
```

**Expected Output:**
```
📚 Creating hybrid retriever with X documents for BM25
✅ Cross-encoder reranker initialized
✅ Hybrid retriever with vector + BM25 + reranking initialized
```

---

## 📊 **PACKAGE DETAILS**

### **sentence-transformers (2.2.2)**

**Purpose:** Cross-encoder model for reranking retrieved documents

**Model Used:** `cross-encoder/ms-marco-MiniLM-L-6-v2`

**Size:** ~90MB download (first use)

**Performance:**
- First query: 5-10 seconds (model loading)
- Subsequent queries: <1 second

**CPU/RAM:**
- CPU: Minimal (<5% on t3.large)
- RAM: ~200-300MB when loaded

---

### **rank-bm25 (0.2.2)**

**Purpose:** BM25 algorithm for keyword/sparse retrieval

**Algorithm:** Okapi BM25 (best match ranking)

**Size:** <1MB

**Performance:**
- Search: <100ms for 1000s of documents
- Indexing: ~10ms per document

**CPU/RAM:**
- CPU: Minimal (<2% on t3.large)
- RAM: ~50-100MB for index

---

## 🎯 **CONFIGURATION OPTIONS**

All configurable in `config.py`:

```python
RETRIEVAL_K = 4              # Final chunks for LLM
HYBRID_RETRIEVAL_K = 10      # Initial retrieval count
HYBRID_ALPHA = 0.6           # Vector/BM25 weight (0.0-1.0)
RERANKER_MODEL = "..."       # Cross-encoder model
```

### **Tuning Guide:**

**For better keyword matching:**
```python
HYBRID_ALPHA = 0.4  # More weight to BM25
```

**For better semantic matching:**
```python
HYBRID_ALPHA = 0.8  # More weight to vector search
```

**For more context in answers:**
```python
RETRIEVAL_K = 6  # Use 6 chunks instead of 4
```

---

## 🔧 **TROUBLESHOOTING**

### **Issue: "ModuleNotFoundError: No module named 'sentence_transformers'"**

**Solution:**
```bash
docker exec -it profai-api pip install sentence-transformers rank-bm25
docker restart profai-api
```

---

### **Issue: First query is slow (10+ seconds)**

**Expected behavior!** Cross-encoder downloads model on first use (~90MB).

**Solution:** No action needed. Subsequent queries will be fast.

To pre-download model:
```python
from sentence_transformers import CrossEncoder
model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
```

---

### **Issue: "torch not found" or CUDA errors**

BM25 and sentence-transformers work fine on CPU. No GPU needed.

If you see torch errors:
```bash
docker exec -it profai-api pip install torch --index-url https://download.pytorch.org/whl/cpu
```

---

## 📝 **COMPLETE FILE CHECKLIST**

- [x] `requirements.txt` - Updated with new packages
- [x] `config.py` - Added hybrid RAG settings
- [x] `Dockerfile` - Already installs from requirements.txt
- [x] `docker-compose.yml` - Uses Dockerfile (no changes needed)
- [x] `docker-compose-production.yml` - Uses Dockerfile (no changes needed)
- [x] `services/hybrid_retriever.py` - NEW file created
- [x] `services/rag_service.py` - Updated to use hybrid retriever
- [x] `core/cloud_vectorizer.py` - Added upload verification

---

## 🚀 **DEPLOYMENT COMMAND SUMMARY**

### **Upload Files to EC2:**

```powershell
scp -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem `
  requirements.txt `
  config.py `
  Dockerfile `
  docker-compose-production.yml `
  ubuntu@51.20.109.241:~/profai/
```

### **Install & Restart:**

```bash
ssh -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem ubuntu@51.20.109.241

# Quick method (2 mins)
docker exec -it profai-api pip install sentence-transformers rank-bm25
docker restart profai-api

# OR Full rebuild (10 mins, permanent)
cd ~/profai
docker-compose -f docker-compose-production.yml down
docker-compose -f docker-compose-production.yml build --no-cache
docker-compose -f docker-compose-production.yml up -d
```

### **Verify:**

```bash
docker logs profai-api --tail=50
# Look for: "✅ Hybrid retriever with vector + BM25 + reranking initialized"
```

---

## ✅ **ALL SET!**

All dependency files are properly configured. The new libraries will be installed automatically when:

1. Building Docker image (production)
2. Running `pip install -r requirements.txt` (local)
3. Manually installing in container (quick testing)

**No additional configuration files need changes.** 🎉
