# 🛑 Shutdown & Cleanup Guide
## How to Stop ProfessorAI Services

---

## ⚠️ Important Notes

**Data Persistence:**
- Your data is in `./data/` folder (mounted as volume)
- Data survives container/pod shutdowns
- Only lost if you delete PersistentVolumeClaim or run `docker-compose down -v`

**Recommended Approach:**
- For **daily shutdown**: Option 1 (Scale to 0)
- For **cleanup**: Option 2 or 3
- For **fresh start**: Option 4

---

## Option 1: Stop Pods (Keep Everything) ✅ RECOMMENDED

### Stop Kubernetes Pods
```powershell
# Scale deployment to 0 (stops all pods)
kubectl scale deployment profai-deployment --replicas=0 -n profai

# Verify pods stopped
kubectl get pods -n profai
# Output: No resources found
```

**What this does:**
- ✅ Stops all running pods
- ✅ Preserves all configuration (ConfigMaps, Secrets, Services)
- ✅ Preserves all data in PersistentVolume
- ✅ Quick to restart tomorrow

**Resource usage:** Minimal (only K8s control plane)

**To restart tomorrow:**
```powershell
kubectl scale deployment profai-deployment --replicas=2 -n profai
```

---

### Stop Docker Containers (if using docker-compose)
```powershell
# Stop containers
docker-compose down

# Verify stopped
docker ps
# Should not show profai-local
```

**What this does:**
- ✅ Stops Docker containers
- ✅ Preserves data in `./data/` folder
- ✅ Preserves Docker image

**To restart:**
```powershell
docker-compose up -d
```

---

## Option 2: Delete Deployment (Keep Config)

```powershell
# Delete deployment only
kubectl delete deployment profai-deployment -n profai

# All pods will terminate
# Services, ConfigMaps, Secrets, PVC remain
```

**What this does:**
- ✅ Removes deployment and pods
- ✅ Keeps Services, ConfigMaps, Secrets
- ✅ Keeps PersistentVolume (data safe)

**To redeploy:**
```powershell
kubectl apply -f k8s/5-deployment.yaml
```

---

## Option 3: Delete All Resources (Keep Namespace)

```powershell
# Delete all application resources
kubectl delete all --all -n profai

# Also delete ConfigMaps, Secrets, PVC
kubectl delete configmap --all -n profai
kubectl delete secret --all -n profai
kubectl delete pvc --all -n profai
kubectl delete hpa --all -n profai

# Namespace still exists
```

**What this does:**
- ❌ Deletes all pods, services, deployments
- ❌ Deletes ConfigMaps, Secrets
- ⚠️ Deletes PVC (**data loss if not backed up**)
- ✅ Keeps namespace structure

**To redeploy:**
```powershell
kubectl apply -f k8s/
```

---

## Option 4: Complete Cleanup (Nuclear Option) 🔥

```powershell
# Delete entire namespace and everything in it
kubectl delete namespace profai
```

**What this does:**
- ❌ Deletes EVERYTHING:
  - All pods
  - All services
  - All deployments
  - All ConfigMaps
  - All Secrets
  - All PersistentVolumeClaims
  - The namespace itself
- ⚠️ **PERMANENT DATA LOSS** (PVC deleted)

**⚠️ WARNING:** Cannot undo! All data in K8s PersistentVolume lost.

**Note:** Your local `./data/` folder (Docker) is NOT affected.

**To redeploy:**
```powershell
kubectl apply -f k8s/
```

---

## Disable Kubernetes Completely

### Option A: Keep Enabled (Minimal Resources)
- Just scale deployments to 0
- K8s control plane uses ~200-300MB RAM when idle
- Fastest to restart tomorrow

### Option B: Disable in Docker Desktop
1. Open Docker Desktop
2. Settings → Kubernetes
3. **Uncheck "Enable Kubernetes"**
4. Apply & Restart

**What this does:**
- Stops entire K8s cluster
- Frees ~500MB-1GB RAM
- Requires re-enabling and redeployment

---

## Verify Shutdown

### Check Kubernetes Resources
```powershell
# Should show "No resources found" after Option 1
kubectl get all -n profai

# Should show namespace exists after Option 1-3
kubectl get namespace profai

# Should show error after Option 4
kubectl get namespace profai
# Error: namespace "profai" not found
```

### Check Docker Containers
```powershell
# Should not show profai-local if stopped
docker ps

# Check all containers (including stopped)
docker ps -a
```

### Check System Resources
```powershell
# Windows Task Manager
# Look for:
# - Docker Desktop process
# - com.docker.backend
# - kubelet (if K8s enabled)
```

---

## Data Backup (Optional)

### Before Complete Cleanup
```powershell
# Backup data from pods
kubectl cp profai/<pod-name>:/app/data ./backup-data -n profai

# OR backup Docker volume
# Your ./data folder already has everything
# Just copy ./data folder elsewhere
```

### Backup Kubernetes Configuration
```powershell
# Already saved in k8s/ folder
# Just ensure k8s/ folder is backed up
```

---

## Resource Usage Comparison

| State | RAM Usage | CPU Usage | Restart Time |
|-------|-----------|-----------|--------------|
| **All Running** | ~2-3GB | ~1-2 cores | Instant |
| **Scaled to 0** | ~300MB | Minimal | 30 seconds |
| **K8s Disabled** | ~100MB | Minimal | 2-3 minutes |
| **All Stopped** | 0 | 0 | 5 minutes |

---

## Tomorrow: Restart Commands

### If you used Option 1 (Scale to 0):
```powershell
# Fastest - just scale back up
kubectl scale deployment profai-deployment --replicas=2 -n profai

# Wait for pods
kubectl get pods -n profai -w

# Port forward
kubectl port-forward -n profai svc/profai-service 5001:5001
```

### If you used Option 2 (Deleted Deployment):
```powershell
# Redeploy just the deployment
kubectl apply -f k8s/5-deployment.yaml

# Check status
kubectl get pods -n profai
```

### If you used Option 3 (Deleted All):
```powershell
# Redeploy everything except namespace
kubectl apply -f k8s/2-configmap.yaml
kubectl apply -f k8s/3-secrets.yaml
kubectl apply -f k8s/4-persistent-volume.yaml
kubectl apply -f k8s/5-deployment.yaml
kubectl apply -f k8s/6-service.yaml
kubectl apply -f k8s/7-ingress.yaml
kubectl apply -f k8s/8-hpa.yaml
```

### If you used Option 4 (Deleted Namespace):
```powershell
# Redeploy everything from scratch
kubectl apply -f k8s/
```

### If you disabled Kubernetes:
```powershell
# 1. Enable K8s in Docker Desktop Settings
# 2. Wait for K8s to start (green indicator)
# 3. Verify: kubectl cluster-info
# 4. Deploy: kubectl apply -f k8s/
```

---

## Recommended Daily Workflow

### End of Day:
```powershell
# Option 1: Stop pods (recommended)
kubectl scale deployment profai-deployment --replicas=0 -n profai
docker-compose down

# OR Option 2: Just close terminal
# K8s will keep running (uses minimal resources when idle)
```

### Start of Day:
```powershell
# If you scaled to 0:
kubectl scale deployment profai-deployment --replicas=2 -n profai

# If you stopped Docker:
docker-compose up -d
```

---

## Emergency: System Too Slow

If your computer is running slow:

```powershell
# Quick: Stop pods
kubectl scale deployment profai-deployment --replicas=0 -n profai

# Still slow? Stop Docker
docker-compose down

# Still slow? Disable K8s
# Docker Desktop → Settings → Kubernetes → Disable

# Nuclear: Stop Docker Desktop completely
# Right-click Docker Desktop tray icon → Quit Docker Desktop
```

---

## 🎯 RECOMMENDED FOR TONIGHT

### Execute These Commands:

```powershell
# 1. Stop Kubernetes pods (keeps config)
kubectl scale deployment profai-deployment --replicas=0 -n profai

# 2. Verify stopped
kubectl get pods -n profai
# Should show: No resources found

# 3. Stop Docker Compose (if running)
docker-compose down

# 4. Verify Docker stopped
docker ps
# Should not show profai-local

# 5. Check what's still running
kubectl get all -n profai
# Should show services/deployment/replicaset/hpa but no pods
```

### What You'll Have Tomorrow:
- ✅ All K8s configuration preserved
- ✅ All data in `./data/` folder safe
- ✅ Docker image ready to use
- ✅ Quick restart (30 seconds)

### Tomorrow Morning:
```powershell
# Just scale back up
kubectl scale deployment profai-deployment --replicas=2 -n profai

# Watch pods start
kubectl get pods -n profai -w

# Access app
kubectl port-forward -n profai svc/profai-service 5001:5001
```

---

## Summary Table

| Option | Command | Data Safe? | Restart Time | Use When |
|--------|---------|------------|--------------|----------|
| **Scale to 0** | `kubectl scale ... --replicas=0` | ✅ Yes | 30 sec | Daily shutdown |
| **Delete Deploy** | `kubectl delete deployment` | ✅ Yes | 1 min | Need to redeploy |
| **Delete All** | `kubectl delete all --all` | ⚠️ No (if delete PVC) | 2 min | Fresh start |
| **Delete NS** | `kubectl delete namespace` | ❌ No | 3 min | Complete reset |
| **Disable K8s** | Docker Settings | ✅ Yes | 5 min | Free RAM |

---

**✅ All set for tomorrow's AWS deployment!**
