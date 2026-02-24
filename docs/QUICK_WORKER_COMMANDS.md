# ⚡ QUICK WORKER MANAGEMENT COMMANDS

## 🚀 **DEPLOYMENT**

### **Deploy to EC2**
```bash
# SSH to EC2
ssh -i ~/Downloads/my-ai-app-key.pem ubuntu@51.20.109.241

# Navigate to project
cd ~/profai

# Stop old containers
docker-compose -f docker-compose-production.yml down

# Rebuild with new worker config
docker-compose -f docker-compose-production.yml build

# Start 5 workers
docker-compose -f docker-compose-production.yml up -d

# Verify all 6 containers running (1 API + 5 workers)
docker ps
```

---

## 📊 **MONITORING**

### **Check All Containers**
```bash
docker ps
# Should show: profai-api, profai-worker-1, profai-worker-2, profai-worker-3, profai-worker-4, profai-worker-5
```

### **Monitor Resource Usage**
```bash
docker stats
# Shows CPU%, Memory Usage for each container
```

### **Check Worker Status**
```bash
docker exec -it profai-worker-1 python monitor_workers.py
```

### **Check Individual Worker Logs**
```bash
# Worker 1
docker logs profai-worker-1 --tail=50 -f

# Worker 2
docker logs profai-worker-2 --tail=50 -f

# All workers (combined)
docker logs profai-worker-1 --tail=20 & \
docker logs profai-worker-2 --tail=20 & \
docker logs profai-worker-3 --tail=20 & \
docker logs profai-worker-4 --tail=20 & \
docker logs profai-worker-5 --tail=20
```

### **Check API Logs**
```bash
docker logs profai-api --tail=100 -f
```

---

## 🔧 **TROUBLESHOOTING**

### **Restart All Services**
```bash
docker-compose -f docker-compose-production.yml restart
```

### **Restart Single Worker**
```bash
docker restart profai-worker-3
```

### **Rebuild After Code Changes**
```bash
# Stop
docker-compose -f docker-compose-production.yml down

# Rebuild
docker-compose -f docker-compose-production.yml build

# Start
docker-compose -f docker-compose-production.yml up -d
```

### **Check Redis Connection**
```bash
docker exec -it profai-worker-1 python -c "from celery_app import celery_app; print(celery_app.control.inspect().ping())"
```

### **View Worker Queue Status**
```bash
docker exec -it profai-worker-1 python -c "from celery_app import celery_app; i = celery_app.control.inspect(); print('Active:', i.active()); print('Reserved:', i.reserved())"
```

---

## 📈 **PERFORMANCE TESTING**

### **Test Single PDF Processing**
```bash
# Upload 1 PDF via API
curl -X POST http://51.20.109.241:5001/api/upload-pdfs \
  -F "files=@test.pdf" \
  -F "course_title=Test Course"

# Watch worker logs
docker logs profai-worker-1 -f
```

### **Test 5 Concurrent PDFs**
```bash
# Upload 5 PDFs simultaneously
# Then check which workers picked them up
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

### **Check Processing Speed**
```bash
# Upload PDF and time it
time curl -X POST http://51.20.109.241:5001/api/upload-pdfs \
  -F "files=@test.pdf" \
  -F "course_title=Speed Test"
```

---

## 🛑 **STOP/START WORKERS**

### **Stop All**
```bash
docker-compose -f docker-compose-production.yml down
```

### **Start All**
```bash
docker-compose -f docker-compose-production.yml up -d
```

### **Scale Workers (if needed)**
```bash
# Reduce to 3 workers temporarily
docker-compose -f docker-compose-production.yml up -d --scale worker-1=1 --scale worker-2=1 --scale worker-3=1 --scale worker-4=0 --scale worker-5=0
```

---

## 📱 **HEALTH CHECKS**

### **API Health**
```bash
curl http://51.20.109.241:5001/health
```

### **Container Health**
```bash
docker ps --filter "health=unhealthy"
# Should return empty if all healthy
```

### **Memory Check (prevent OOM)**
```bash
docker stats --no-stream | awk '{if ($4 ~ /%/) {split($4, a, "%"); if (a[1] > 90) print $2, a[1]"%"}}'
# Warns if any container using >90% memory
```

---

## 🎯 **QUICK DIAGNOSTICS**

### **Problem: Workers not picking up tasks**

```bash
# 1. Check Redis connection
docker logs profai-worker-1 | grep -i "redis\|connected"

# 2. Check worker registration
docker exec -it profai-worker-1 python -c "from celery_app import celery_app; print(celery_app.control.inspect().registered())"

# 3. Check queue
docker exec -it profai-worker-1 python monitor_workers.py
```

### **Problem: High memory usage**

```bash
# 1. Check current usage
docker stats --no-stream

# 2. Restart workers to clear memory
docker restart profai-worker-1 profai-worker-2 profai-worker-3 profai-worker-4 profai-worker-5

# 3. Verify memory back to normal
docker stats --no-stream
```

### **Problem: Slow PDF processing**

```bash
# 1. Check how many workers are active
docker exec -it profai-worker-1 python monitor_workers.py

# 2. Check CPU usage
docker stats --no-stream | grep worker

# 3. Check if queue is backing up
docker logs profai-api | grep -i "queue\|task"
```

---

## 📊 **EXPECTED NORMAL STATE**

### **`docker ps` Output:**
```
6 containers running:
  - profai-api (ports 5001, 8765)
  - profai-worker-1
  - profai-worker-2
  - profai-worker-3
  - profai-worker-4
  - profai-worker-5
```

### **`docker stats` Output (Idle):**
```
NAME              CPU%    MEM
profai-api        5%      800MB
profai-worker-1   2%      350MB
profai-worker-2   2%      350MB
profai-worker-3   2%      350MB
profai-worker-4   2%      350MB
profai-worker-5   2%      350MB
---
Total:            ~17%    ~2.5GB
```

### **`docker stats` Output (Processing 5 PDFs):**
```
NAME              CPU%    MEM
profai-api        10%     900MB
profai-worker-1   25%     1.2GB  ← Processing
profai-worker-2   25%     1.1GB  ← Processing
profai-worker-3   25%     1.2GB  ← Processing
profai-worker-4   25%     1.1GB  ← Processing
profai-worker-5   25%     1.2GB  ← Processing
---
Total:            ~135%   ~6.7GB ✅ (within 8GB limit!)
```

---

## 🎉 **SUCCESS INDICATORS**

✅ **All 6 containers running** (`docker ps`)  
✅ **Workers connected to Redis** (check logs)  
✅ **Memory usage stable** (<8GB total)  
✅ **CPU usage balanced** across workers  
✅ **Tasks processing** (monitor script shows activity)  
✅ **No OOM kills** (`docker ps` shows long uptimes)  

---

**Keep this file handy for day-to-day operations!** 📌
