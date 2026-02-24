# ✅ STAGE 2: KUBERNETES MANIFESTS - COMPLETED!

## 🎉 What We Created

### 📁 k8s/ Folder Structure:

```
k8s/
├── 1-namespace.yaml          ✅ Created
├── 2-configmap.yaml          ✅ Created
├── 3-secrets.yaml            ✅ Created (needs your API keys)
├── 4-persistent-volume.yaml  ✅ Created
├── 5-deployment.yaml         ✅ Created
├── 6-service.yaml            ✅ Created
├── 7-ingress.yaml            ✅ Created
├── 8-hpa.yaml                ✅ Created
├── encode-secrets.ps1        ✅ Helper script
└── README.md                 ✅ Complete guide
```

---

## 📚 What Each File Does (Simple Explanation)

### **1-namespace.yaml** - Your Workspace
```
Think of it as: Creating a separate room in a house
What it does: Isolates ProfessorAI from other apps
Kubernetes concept: Namespace
```

### **2-configmap.yaml** - Settings File
```
Think of it as: A config.ini file
What it does: Stores non-secret settings (ports, model names, etc.)
Kubernetes concept: ConfigMap
```

### **3-secrets.yaml** - Password Vault
```
Think of it as: A locked safe for passwords
What it does: Stores API keys (Base64 encoded)
Kubernetes concept: Secret
⚠️ ACTION NEEDED: You must add your actual API keys here!
```

### **4-persistent-volume.yaml** - Hard Drive
```
Think of it as: External hard drive for your computer
What it does: 10GB storage for courses, quizzes, vector data
Kubernetes concept: PersistentVolumeClaim (PVC)
Why needed: Data survives pod restarts
```

### **5-deployment.yaml** - App Instructions
```
Think of it as: Recipe for running your app
What it does:
  - Run 3 copies of your app
  - Each gets 2GB-4GB RAM, 1-2 CPU cores
  - Health checks every 30 seconds
  - Rolling updates (zero downtime)
Kubernetes concept: Deployment
```

### **6-service.yaml** - Phone Number
```
Think of it as: A permanent phone number that routes to your app
What it does:
  - ClusterIP: Internal communication (app-to-app)
  - LoadBalancer: External access (internet → your app)
  - Sticky sessions for WebSocket
Kubernetes concept: Service
```

### **7-ingress.yaml** - Front Door Router
```
Think of it as: A smart mailbox that routes packages
What it does:
  - Routes /api → API service
  - Routes /ws → WebSocket service
  - Routes / → Web interface
  - Handles CORS, file uploads, timeouts
Kubernetes concept: Ingress
```

### **8-hpa.yaml** - Auto-Pilot
```
Think of it as: Thermostat that adjusts temperature automatically
What it does:
  - Monitors CPU and memory
  - Scales from 2 to 10 pods
  - If CPU > 70%, add more pods
  - If CPU < 70%, remove pods
Kubernetes concept: HorizontalPodAutoscaler (HPA)
```

---

## 🔑 Key Kubernetes Concepts You Learned

| Concept | What It Is | Real-World Analogy |
|---------|------------|-------------------|
| **Namespace** | Isolated workspace | Separate folders on computer |
| **ConfigMap** | Non-secret config | Settings file |
| **Secret** | Encrypted data | Password manager |
| **PVC** | Persistent storage | External hard drive |
| **Deployment** | App definition | Recipe with instructions |
| **Replica** | Multiple copies | Backup singers |
| **Pod** | Running container | Individual worker |
| **Service** | Network endpoint | Phone number |
| **LoadBalancer** | External access | Company receptionist |
| **Ingress** | HTTP routing | Mail sorter |
| **HPA** | Auto-scaler | Thermostat |

---

## 📊 How Kubernetes Works (Architecture)

```
┌─────────────────────────────────────────────────────────┐
│               KUBERNETES CLUSTER                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │  NAMESPACE: profai                               │ │
│  │                                                  │ │
│  │  ┌────────────────────────────────────────────┐ │ │
│  │  │  INGRESS (Traffic Router)                  │ │ │
│  │  │  - Routes /api, /ws, /                     │ │ │
│  │  └───────────────┬────────────────────────────┘ │ │
│  │                  │                               │ │
│  │  ┌───────────────▼────────────────────────────┐ │ │
│  │  │  SERVICE (Load Balancer)                   │ │ │
│  │  │  - Distributes traffic                     │ │ │
│  │  │  - Ports: 5001 (API), 8765 (WebSocket)    │ │ │
│  │  └───────────────┬────────────────────────────┘ │ │
│  │                  │                               │ │
│  │      ┌──────────┴──────────┬─────────────┐     │ │
│  │      │                     │             │     │ │
│  │  ┌───▼────┐ ┌───▼────┐ ┌───▼────┐             │ │
│  │  │ POD 1  │ │ POD 2  │ │ POD 3  │  ← HPA      │ │
│  │  │        │ │        │ │        │   manages   │ │
│  │  │FastAPI │ │FastAPI │ │FastAPI │   2-10 pods │ │
│  │  │Port:   │ │Port:   │ │Port:   │             │ │
│  │  │5001    │ │5001    │ │5001    │             │ │
│  │  │8765    │ │8765    │ │8765    │             │ │
│  │  └───┬────┘ └───┬────┘ └───┬────┘             │ │
│  │      │          │          │                   │ │
│  │      └──────────┴──────────┘                   │ │
│  │                  │                             │ │
│  │  ┌───────────────▼────────────────────────┐   │ │
│  │  │  PERSISTENT VOLUME (10GB)              │   │ │
│  │  │  - /app/data/courses/                  │   │ │
│  │  │  - /app/data/quizzes/                  │   │ │
│  │  │  - /app/data/quiz_answers/             │   │ │
│  │  └────────────────────────────────────────┘   │ │
│  │                                                │ │
│  │  ┌────────────────────────────────────────┐   │ │
│  │  │  CONFIGMAP (Settings)                  │   │ │
│  │  │  - PORT=5001                           │   │ │
│  │  │  - LLM_MODEL=gpt-4o-mini               │   │ │
│  │  └────────────────────────────────────────┘   │ │
│  │                                                │ │
│  │  ┌────────────────────────────────────────┐   │ │
│  │  │  SECRET (API Keys)                     │   │ │
│  │  │  - OPENAI_API_KEY (base64)             │   │ │
│  │  │  - SARVAM_API_KEY (base64)             │   │ │
│  │  └────────────────────────────────────────┘   │ │
│  │                                                │ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🚦 Traffic Flow

```
USER                KUBERNETES CLUSTER
 │
 │  1. HTTP Request: http://profai.local/api/courses
 ├──────────────────────────────────────────────────┐
 │                                                   │
 │  2. Ingress receives request                     │
 │     - Checks path: /api                          │
 │     - Routes to: profai-service                  │
 │                                                   │
 │  3. Service (LoadBalancer)                       │
 │     - Picks a healthy pod                        │
 │     - Uses round-robin                           │
 │                                                   │
 │  4. Pod handles request                          │
 │     - FastAPI processes /api/courses             │
 │     - Reads from /app/data/courses/              │
 │     - Uses PersistentVolume                      │
 │                                                   │
 │  5. Response returns                             │
 │     Pod → Service → Ingress → User               │
 │                                                   │
 └◄──────────────────────────────────────────────────┘
    Response: { courses: [...] }
```

---

## 🔄 Auto-Scaling Example

```
TIME: 10:00 AM
CPU Usage: 30%
Pods Running: 2 (minimum)

TIME: 10:15 AM
⚠️ Traffic spike!
CPU Usage: 80%
HPA: "CPU > 70%, need more pods!"
Action: Starting Pod 3...
Pods Running: 3

TIME: 10:20 AM
CPU Usage: 85%
HPA: "Still high, add more!"
Action: Starting Pod 4 and 5...
Pods Running: 5

TIME: 11:00 AM
Traffic decreases
CPU Usage: 40%
HPA: "CPU < 70%, can reduce"
Action: Wait 5 minutes (stabilization)...
Then: Stop Pod 5
Pods Running: 4

TIME: 11:30 AM
CPU Usage: 25%
HPA: "Much lower, reduce more"
Action: Stop Pod 4 and 3
Pods Running: 2 (minimum)
```

---

## ⚠️ BEFORE YOU TEST (Important)

### 1. Update Secrets:

```bash
cd k8s
.\encode-secrets.ps1
```

Copy the output to `3-secrets.yaml`.

### 2. Enable Kubernetes in Docker Desktop:

- Settings → Kubernetes → Enable Kubernetes

### 3. Verify Docker Image Exists:

```bash
docker images | grep profai
```

Should show: `profai   latest   ...`

---

## 🎯 What You'll Learn in Stage 3

When you test locally with Kubernetes, you'll experience:

1. **Deploying with `kubectl apply`**
2. **Watching pods start and become ready**
3. **Seeing load balancing across multiple pods**
4. **Testing auto-scaling under load**
5. **Debugging with `kubectl logs`**
6. **Understanding rolling updates**
7. **Persistent data across pod restarts**
8. **Service discovery and networking**
9. **Resource management (CPU/Memory)**
10. **Health checks and self-healing**

---

## 📋 Common Kubernetes Commands (Cheat Sheet)

```bash
# View everything
kubectl get all -n profai

# Get pods
kubectl get pods -n profai

# Watch pods (live)
kubectl get pods -n profai -w

# View logs
kubectl logs -n profai -l app=profai -f

# Describe resource
kubectl describe pod <pod-name> -n profai

# Execute command in pod
kubectl exec -it <pod-name> -n profai -- bash

# Scale manually
kubectl scale deployment profai-deployment --replicas=5 -n profai

# Restart deployment
kubectl rollout restart deployment profai-deployment -n profai

# View HPA
kubectl get hpa -n profai

# Port forward
kubectl port-forward -n profai svc/profai-service 5001:5001

# Delete everything
kubectl delete namespace profai
```

---

## ✅ Stage 2 Completion Checklist

- [x] Created 8 Kubernetes manifest files
- [x] Created helper script (encode-secrets.ps1)
- [x] Created comprehensive README
- [x] Documented all concepts
- [x] Explained traffic flow
- [x] Provided troubleshooting guide
- [ ] **NEXT**: Encode API keys in secrets.yaml
- [ ] **NEXT**: Enable Kubernetes in Docker Desktop
- [ ] **NEXT**: Deploy and test locally (Stage 3)

---

## 🚀 Ready for Stage 3?

Once you've:
1. ✅ Encoded your API keys in `3-secrets.yaml`
2. ✅ Enabled Kubernetes in Docker Desktop
3. ✅ Read the `k8s/README.md` guide

**Type "Ready for Stage 3" and I'll guide you through local testing!**

---

## 📚 Additional Learning Resources

### Kubernetes Concepts:
- **Pods**: Smallest deployable unit (container wrapper)
- **ReplicaSet**: Maintains desired number of pods
- **Deployment**: Manages ReplicaSets and updates
- **Service**: Stable networking for pods
- **Ingress**: HTTP(S) routing
- **ConfigMap/Secret**: Configuration management
- **PVC/PV**: Persistent storage
- **HPA**: Horizontal auto-scaling
- **Namespace**: Resource isolation

### Why Kubernetes?
- ✅ Auto-healing (restarts failed pods)
- ✅ Auto-scaling (based on metrics)
- ✅ Zero-downtime deployments
- ✅ Load balancing
- ✅ Service discovery
- ✅ Storage orchestration
- ✅ Self-healing infrastructure
- ✅ Cloud-agnostic (runs anywhere)

---

## 🎓 What Makes This Production-Ready

| Feature | Why It Matters |
|---------|---------------|
| **3 Replicas** | High availability, no single point of failure |
| **Health Checks** | Auto-restart unhealthy pods |
| **Resource Limits** | Prevents one pod from using all resources |
| **Rolling Updates** | Update without downtime |
| **Auto-scaling** | Handle traffic spikes automatically |
| **Persistent Storage** | Data survives pod crashes |
| **Secrets Management** | Secure API keys |
| **Load Balancing** | Distribute traffic evenly |
| **Monitoring** | HPA metrics for scaling decisions |

---

**🎉 Congratulations! Stage 2 Complete!**

You now have a complete, production-ready Kubernetes configuration for ProfessorAI!
