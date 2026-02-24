# 🚀 Complete Docker & Kubernetes Commands Reference
## ProfessorAI - Stage 1-3 Commands

---

## 📋 Stage 1: Docker Commands

### Build Docker Image
```powershell
docker build -t profai:latest .
```
**What it does:** Builds image from Dockerfile, tags as `profai:latest`  
**When:** After code changes, before K8s deployment

### Run with Docker Compose
```powershell
# Start (build + run)
docker-compose up --build

# Start in background
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f profai
```
**What it does:** Starts container, mounts volumes, exposes ports 5001 & 8765  
**When:** Local testing before Kubernetes

### Docker Inspection
```powershell
docker images                    # List images
docker ps                        # Running containers
docker logs -f profai-local      # View logs
docker exec -it profai-local bash  # Shell into container
docker stats profai-local        # Resource usage
```

---

## 📋 Stage 2: Prepare Kubernetes Manifests

### Encode API Keys
```powershell
cd k8s
.\encode-secrets.ps1

# OR manually:
$key = "your-api-key"
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($key))
```
**What it does:** Converts API keys to Base64 for secrets.yaml  
**When:** First-time setup, when updating keys

### Files Created
```
k8s/
├── 1-namespace.yaml          # Workspace isolation
├── 2-configmap.yaml          # Non-secret config
├── 3-secrets.yaml            # API keys (update with your Base64 values)
├── 4-persistent-volume.yaml  # 10GB storage
├── 5-deployment.yaml         # App definition (2 pods, 512MB-1GB RAM each)
├── 6-service.yaml            # LoadBalancer + ClusterIP
├── 7-ingress.yaml            # HTTP routing
└── 8-hpa.yaml                # Auto-scale 2-10 pods
```

---

## 📋 Stage 3: Deploy to Kubernetes

### Enable Kubernetes (One-Time)
1. Docker Desktop → Settings → Kubernetes
2. Check "Enable Kubernetes"
3. Apply & Restart

### Deploy All Resources
```powershell
# Apply all manifests
kubectl apply -f k8s/

# OR one by one:
kubectl apply -f k8s/1-namespace.yaml
kubectl apply -f k8s/2-configmap.yaml
kubectl apply -f k8s/3-secrets.yaml
kubectl apply -f k8s/4-persistent-volume.yaml
kubectl apply -f k8s/5-deployment.yaml
kubectl apply -f k8s/6-service.yaml
kubectl apply -f k8s/7-ingress.yaml
kubectl apply -f k8s/8-hpa.yaml
```
**What it does:** Creates all K8s resources in `profai` namespace  
**Order matters:** Namespace → ConfigMap/Secrets → PVC → Deployment → Services → Ingress → HPA

### View Status
```powershell
kubectl get all -n profai          # All resources
kubectl get pods -n profai         # Just pods
kubectl get services -n profai     # Just services
kubectl get hpa -n profai          # Autoscaler status
```

### View Logs
```powershell
kubectl logs -n profai -l app=profai -f           # All pods, follow
kubectl logs -n profai <pod-name>                 # Specific pod
kubectl logs -n profai <pod-name> --previous      # Crashed pod logs
```

### Access Application
```powershell
# Port forward (easiest for local)
kubectl port-forward -n profai svc/profai-service 5001:5001

# Then access:
# http://localhost:5001 - Main UI
# http://localhost:5001/docs - API docs
# http://localhost:5001/api/courses - Test API
```

---

## 📊 Monitoring Commands

### Install Metrics Server
```powershell
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Fix for Docker Desktop (TLS cert issue)
kubectl patch deployment metrics-server -n kube-system --patch '
spec:
  template:
    spec:
      containers:
      - name: metrics-server
        args:
        - --kubelet-insecure-tls
'
```

### View Metrics
```powershell
kubectl top nodes                  # Node CPU/memory
kubectl top pods -n profai         # Pod CPU/memory
kubectl get hpa -n profai          # Autoscaler metrics
kubectl describe hpa profai-hpa -n profai  # Detailed HPA info
```

---

## ⚙️ Operations Commands

### Scaling
```powershell
# Manual scale
kubectl scale deployment profai-deployment --replicas=5 -n profai

# Watch scaling
kubectl get pods -n profai -w

# Check autoscaler
kubectl get hpa -n profai
```

### Rolling Updates
```powershell
# Apply updated config
kubectl apply -f k8s/5-deployment.yaml

# Restart deployment
kubectl rollout restart deployment/profai-deployment -n profai

# Check rollout status
kubectl rollout status deployment/profai-deployment -n profai

# Rollback
kubectl rollout undo deployment/profai-deployment -n profai
```

### Update Configuration
```powershell
# Edit ConfigMap
kubectl edit configmap profai-config -n profai

# Edit Secrets
kubectl edit secret profai-secrets -n profai

# Restart to apply changes
kubectl rollout restart deployment/profai-deployment -n profai
```

---

## 🔍 Debugging Commands

### Pod Issues
```powershell
# Why is pod pending/failing?
kubectl describe pod <pod-name> -n profai

# View events
kubectl get events -n profai --sort-by='.lastTimestamp'

# Shell into pod
kubectl exec -it <pod-name> -n profai -- bash

# Test API inside pod
kubectl exec -it <pod-name> -n profai -- curl localhost:5001/api/courses
```

### Network Issues
```powershell
# Check service endpoints
kubectl get endpoints profai-service -n profai

# Describe service
kubectl describe service profai-service -n profai

# Test DNS
kubectl run -it --rm debug --image=alpine -n profai -- sh
# Inside: apk add curl && curl http://profai-service:5001
```

### Resource Issues
```powershell
# Check node capacity
kubectl describe node <node-name>

# Lower resource requests if needed
kubectl edit deployment profai-deployment -n profai
```

---

## 📋 Quick Reference Cheat Sheet

```powershell
# ===== DEPLOY =====
kubectl apply -f k8s/                        # Deploy all
kubectl get all -n profai                    # Check status
kubectl logs -n profai -l app=profai -f      # View logs
kubectl port-forward -n profai svc/profai-service 5001:5001  # Access

# ===== SCALE =====
kubectl scale deployment profai-deployment --replicas=3 -n profai
kubectl get hpa -n profai

# ===== UPDATE =====
kubectl apply -f k8s/5-deployment.yaml
kubectl rollout restart deployment/profai-deployment -n profai

# ===== DEBUG =====
kubectl describe pod <pod-name> -n profai
kubectl exec -it <pod-name> -n profai -- bash
kubectl top pods -n profai

# ===== CLEANUP (SEE SHUTDOWN_GUIDE.md) =====
kubectl scale deployment profai-deployment --replicas=0 -n profai  # Stop
kubectl delete namespace profai              # Delete all
```

---

## 📚 Key Concepts

**Namespace**: Isolated workspace (`profai`)  
**Pod**: Running container (ephemeral)  
**Deployment**: Manages pods, ensures desired state  
**Service**: Stable network endpoint, load balances  
**ConfigMap**: Non-secret configuration  
**Secret**: API keys (Base64 encoded)  
**PVC**: Persistent storage (10GB for data)  
**HPA**: Auto-scales 2-10 pods based on CPU/memory  

**Resource Requests vs Limits:**
- **Request**: Guaranteed minimum (512MB RAM, 0.25 CPU)
- **Limit**: Maximum allowed (1GB RAM, 0.5 CPU)

**Health Checks:**
- **Liveness**: Restarts if fails
- **Readiness**: Removes from load balancer if fails
- **Startup**: Gives time to start (up to 5 minutes)

---

**Next:** See `SHUTDOWN_GUIDE.md` for cleanup commands
