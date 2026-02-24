# ✅ AWS DEPLOYMENT CHECKLIST

**Use this as your guide while deploying!**

Print this or keep it open in another window.

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### Local Testing
- [ ] Application runs locally with `python run_profai_websocket_celery.py`
- [ ] Docker image builds: `docker-compose -f docker-compose-production.yml build`
- [ ] All API keys added to `.env` file
- [ ] Redis Labs Cloud connection tested
- [ ] Database connection tested (if using Neon)

### Requirements
- [ ] AWS account created
- [ ] Credit card added to AWS (required)
- [ ] Billing alerts set up ($100-200 threshold)
- [ ] AWS CLI installed: `aws --version`
- [ ] kubectl installed: `kubectl version --client`
- [ ] eksctl installed: `eksctl version`
- [ ] Docker installed and running
- [ ] Helm installed (for Load Balancer Controller)

---

## 🚀 DEPLOYMENT STEPS

### PHASE 1: AWS Setup (30 min)

- [ ] **1.1** AWS account created
- [ ] **1.2** Billing alerts configured
- [ ] **1.3** IAM user created (`profai-deployer`)
- [ ] **1.4** AWS CLI configured: `aws configure`
- [ ] **1.5** Test AWS access: `aws sts get-caller-identity`

**Time Check:** ⏱️ 30 minutes elapsed

---

### PHASE 2: Push Docker Image (30 min)

- [ ] **2.1** ECR repository created:
  ```bash
  aws ecr create-repository --repository-name profai --region us-east-1
  ```
  - [ ] Note ECR URI: `______________________________`

- [ ] **2.2** Login to ECR:
  ```bash
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
  ```

- [ ] **2.3** Build image:
  ```bash
  docker build -t profai:latest .
  ```

- [ ] **2.4** Tag image:
  ```bash
  docker tag profai:latest YOUR_ECR_URI:latest
  docker tag profai:latest YOUR_ECR_URI:v1.0.0
  ```

- [ ] **2.5** Push image (takes 5-10 min):
  ```bash
  docker push YOUR_ECR_URI:latest
  docker push YOUR_ECR_URI:v1.0.0
  ```

- [ ] **2.6** Verify images in ECR:
  ```bash
  aws ecr describe-images --repository-name profai
  ```

**Time Check:** ⏱️ 60 minutes elapsed (1 hour)

---

### PHASE 3: Create EKS Cluster (60 min)

- [ ] **3.1** Create `eks-cluster.yaml` config file
  - [ ] Set cluster name: `profai-cluster`
  - [ ] Set region: `us-east-1`
  - [ ] Configure node group: `t3.large`

- [ ] **3.2** Create cluster (15-20 min wait):
  ```bash
  eksctl create cluster -f eks-cluster.yaml
  ```
  - [ ] Wait for success message
  - [ ] Note: This is the longest wait!

- [ ] **3.3** Configure kubectl:
  ```bash
  aws eks update-kubeconfig --name profai-cluster --region us-east-1
  kubectl get nodes
  ```
  - [ ] See 3 nodes in Ready state

- [ ] **3.4** Install AWS Load Balancer Controller:
  - [ ] Download IAM policy
  - [ ] Create IAM policy
  - [ ] Create service account
  - [ ] Install with Helm
  - [ ] Verify controller running

**Time Check:** ⏱️ 120 minutes elapsed (2 hours)

---

### PHASE 4: Update Kubernetes Files (20 min)

- [ ] **4.1** Update image URLs in deployment files:
  - [ ] `k8s/5-api-deployment.yaml` line 23: `image: YOUR_ECR_URI:latest`
  - [ ] `k8s/10-worker-deployment.yaml` line 23: `image: YOUR_ECR_URI:latest`

- [ ] **4.2** Verify Redis configuration in ConfigMap:
  - [ ] `k8s/2-configmap.yaml` has Redis Labs host
  - [ ] Port is `10925`
  - [ ] SSL is enabled

- [ ] **4.3** Encode secrets using PowerShell:
  ```powershell
  cd k8s
  .\encode-secrets.ps1
  ```
  - [ ] Encode OPENAI_API_KEY
  - [ ] Encode ELEVENLABS_API_KEY
  - [ ] Encode DEEPGRAM_API_KEY
  - [ ] Encode DATABASE_URL (Neon)
  - [ ] Encode GROQ_API_KEY (optional)
  - [ ] Encode CHROMA_CLOUD_API_KEY (optional)

- [ ] **4.4** Update `k8s/3-secrets.yaml` with encoded values
  - [ ] OPENAI_API_KEY
  - [ ] ELEVENLABS_API_KEY
  - [ ] DEEPGRAM_API_KEY
  - [ ] DATABASE_URL
  - [ ] REDIS_URL (already configured ✅)
  - [ ] REDIS_PASSWORD (already configured ✅)

**Time Check:** ⏱️ 140 minutes elapsed (2h 20m)

---

### PHASE 5: Deploy Application (30 min)

- [ ] **5.1** Create namespace:
  ```bash
  kubectl apply -f k8s/1-namespace.yaml
  ```

- [ ] **5.2** Apply ConfigMap:
  ```bash
  kubectl apply -f k8s/2-configmap.yaml
  ```

- [ ] **5.3** Apply Secrets:
  ```bash
  kubectl apply -f k8s/3-secrets.yaml
  ```
  - [ ] Verify: `kubectl get secret -n profai`

- [ ] **5.4** Create Persistent Volume:
  ```bash
  kubectl apply -f k8s/4-persistent-volume.yaml
  ```
  - [ ] Verify: `kubectl get pvc -n profai`

- [ ] **5.5** Deploy API:
  ```bash
  kubectl apply -f k8s/5-api-deployment.yaml
  ```
  - [ ] Wait for pods: `kubectl get pods -n profai -w`
  - [ ] Check logs: `kubectl logs -f deployment/profai-api -n profai`

- [ ] **5.6** Deploy Workers:
  ```bash
  kubectl apply -f k8s/10-worker-deployment.yaml
  ```
  - [ ] Verify workers running

- [ ] **5.7** Create Service:
  ```bash
  kubectl apply -f k8s/6-service.yaml
  ```

- [ ] **5.8** Create Ingress (Load Balancer):
  ```bash
  kubectl apply -f k8s/7-ingress.yaml
  ```
  - [ ] Wait 2-3 min for ALB provisioning
  - [ ] Get URL: `kubectl get ingress -n profai`
  - [ ] Note Load Balancer URL: `______________________________`

- [ ] **5.9** Apply HPA (Auto-scaling):
  ```bash
  kubectl apply -f k8s/8-hpa.yaml
  ```

**Time Check:** ⏱️ 170 minutes elapsed (2h 50m)

---

### PHASE 6: Verify Deployment (20 min)

- [ ] **6.1** Check all pods running:
  ```bash
  kubectl get pods -n profai
  ```
  - [ ] 10 API pods running
  - [ ] 10 Worker pods running
  - [ ] All show 1/1 Ready

- [ ] **6.2** Check services:
  ```bash
  kubectl get svc -n profai
  ```

- [ ] **6.3** Check ingress has address:
  ```bash
  kubectl get ingress -n profai
  ```
  - [ ] Shows Load Balancer URL

- [ ] **6.4** Test health endpoint:
  ```bash
  curl http://YOUR_ALB_URL/health
  ```
  - [ ] Returns: `{"status":"healthy"}`

- [ ] **6.5** Check API logs for errors:
  ```bash
  kubectl logs deployment/profai-api -n profai --tail=100
  ```
  - [ ] No Redis connection errors
  - [ ] No database errors
  - [ ] Server started successfully

- [ ] **6.6** Check Worker logs:
  ```bash
  kubectl logs deployment/profai-worker -n profai --tail=100
  ```
  - [ ] Celery worker started
  - [ ] Connected to Redis
  - [ ] No errors

- [ ] **6.7** Test upload endpoint:
  ```bash
  curl -X POST http://YOUR_ALB_URL/api/upload-pdf \
    -F "files=@test.pdf" \
    -F "course_title=Test Course"
  ```
  - [ ] Returns task_id
  - [ ] No errors

**Time Check:** ⏱️ 190 minutes elapsed (3h 10m)

---

### PHASE 7: Set Up Monitoring (30 min)

- [ ] **7.1** Create CloudWatch Dashboard:
  - [ ] Go to AWS Console → CloudWatch → Dashboards
  - [ ] Create dashboard: `ProfAI-Production`
  - [ ] Add CPU widget
  - [ ] Add Memory widget
  - [ ] Add Pod Count widget

- [ ] **7.2** Set up CloudWatch alarms:
  - [ ] High CPU alarm (>80%)
  - [ ] High Memory alarm (>85%)
  - [ ] Pod crash alarm

- [ ] **7.3** Enable Container Insights:
  ```bash
  aws eks create-addon --cluster-name profai-cluster --addon-name amazon-cloudwatch-observability
  ```

- [ ] **7.4** Verify metrics appearing in CloudWatch:
  - [ ] Check dashboard shows data
  - [ ] Metrics updating every 5 minutes

**Time Check:** ⏱️ 220 minutes elapsed (3h 40m)

---

### PHASE 8: Optional - Domain & SSL (30 min)

Skip this if you don't have a domain yet!

- [ ] **8.1** Request SSL certificate in AWS ACM
- [ ] **8.2** Add DNS validation records
- [ ] **8.3** Wait for certificate validation
- [ ] **8.4** Update ingress with certificate ARN
- [ ] **8.5** Add CNAME in your DNS: `api.yourdomain.com → ALB_URL`
- [ ] **8.6** Test HTTPS: `https://api.yourdomain.com/health`

**Time Check:** ⏱️ 250 minutes elapsed (4h 10m)

---

## ✅ POST-DEPLOYMENT VERIFICATION

### Functionality Tests
- [ ] Health endpoint works: `/health`
- [ ] Upload PDF works: `/api/upload-pdf`
- [ ] List courses works: `/api/courses`
- [ ] Generate quiz works: `/api/generate-quiz`
- [ ] Chat works: `/api/chat`
- [ ] Text-to-speech works: `/api/text-to-speech`
- [ ] WebSocket connects: `ws://YOUR_ALB_URL:8765`

### Performance Tests
- [ ] Check HPA status: `kubectl get hpa -n profai`
- [ ] Monitor auto-scaling: Watch pods scale under load
- [ ] Check response times: <500ms for API calls
- [ ] Verify concurrent users: Test with k6 load testing

### Cost Verification
- [ ] Check current AWS bill
- [ ] Verify within budget
- [ ] Billing alerts working
- [ ] No unexpected charges

---

## 📊 MONITORING CHECKLIST (Daily)

### Daily Checks
- [ ] Check CloudWatch dashboard
- [ ] Review pod health: `kubectl get pods -n profai`
- [ ] Check for errors in logs
- [ ] Verify auto-scaling working
- [ ] Check AWS costs

### Weekly Checks
- [ ] Review CloudWatch alarms (any triggered?)
- [ ] Check node utilization: `kubectl top nodes`
- [ ] Review pod resource usage
- [ ] Verify backup strategy
- [ ] Update Docker image if needed

### Monthly Checks
- [ ] Review total AWS costs
- [ ] Optimize resource allocation
- [ ] Update Kubernetes version if needed
- [ ] Review security settings
- [ ] Update dependencies

---

## 🚨 TROUBLESHOOTING QUICK GUIDE

### Pods Won't Start
```bash
kubectl describe pod POD_NAME -n profai
kubectl logs POD_NAME -n profai
```

### Can't Connect to Load Balancer
```bash
kubectl get ingress -n profai
kubectl describe ingress profai-ingress -n profai
```

### Redis Connection Failed
```bash
# Check secret exists
kubectl get secret profai-secrets -n profai

# Test from pod
kubectl exec -it POD_NAME -n profai -- env | grep REDIS
```

### High Costs
```bash
# Check node count
kubectl get nodes

# Scale down manually
kubectl scale deployment profai-worker --replicas=5 -n profai
```

---

## 📝 IMPORTANT URLS & COMMANDS

### Your Information
- **AWS Account ID:** `_______________________`
- **ECR Repository:** `_______________________`
- **EKS Cluster:** `profai-cluster`
- **Region:** `us-east-1`
- **Load Balancer URL:** `_______________________`
- **Custom Domain:** `_______________________` (if configured)

### Quick Commands
```bash
# Get pods
kubectl get pods -n profai

# Get logs
kubectl logs -f deployment/profai-api -n profai

# Scale manually
kubectl scale deployment profai-api --replicas=20 -n profai

# Update image
kubectl set image deployment/profai-api api=YOUR_ECR_URI:v1.0.1 -n profai

# Rollback
kubectl rollout undo deployment/profai-api -n profai

# Delete everything (CAREFUL!)
kubectl delete namespace profai
```

---

## 🎉 DEPLOYMENT COMPLETE!

**Your Production Application:**
- ✅ Running on AWS EKS
- ✅ Auto-scaling (10-50 API pods, 10-100 workers)
- ✅ Load balancer configured
- ✅ Redis Labs Cloud connected
- ✅ Neon PostgreSQL ready
- ✅ Monitoring enabled
- ✅ Ready for 5,500+ users!

**Next Steps:**
1. Share Load Balancer URL with team
2. Set up CI/CD pipeline (optional)
3. Configure custom domain (optional)
4. Add authentication (optional)
5. Monitor for 24 hours
6. Celebrate! 🎊

---

**Total Deployment Time:** ~4-5 hours
**Monthly Cost:** $400-900 (optimizable)
**Capacity:** 5,000+ concurrent users

**STATUS:** 🚀 LIVE AND RUNNING!
