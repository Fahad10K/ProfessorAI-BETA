# 🚀 AWS Deployment Guide - Production Ready

**Goal:** Deploy ProfessorAI to AWS EKS with auto-scaling for 5,500+ users

**Prerequisites:**
- ✅ Local testing completed (Redis + Neon working)
- ✅ Docker image builds successfully
- ✅ Kubernetes manifests created
- ✅ Application tested locally

---

## 📋 Deployment Overview

### Architecture

```
Internet
    ↓
AWS ALB (Load Balancer)
    ↓
AWS EKS Cluster
    ├── API Pods (10-50)
    └── Worker Pods (10-100)
    ↓
    ├── Upstash Redis (Message Queue)
    ├── Neon PostgreSQL (Database)
    └── ChromaDB Cloud (Vectors)
```

### Timeline

| Phase | Duration | What You'll Do |
|-------|----------|----------------|
| **Phase 1: AWS Setup** | 1 hour | Create accounts, install tools |
| **Phase 2: ECR & Image** | 30 min | Push Docker image to AWS |
| **Phase 3: EKS Cluster** | 1 hour | Create Kubernetes cluster |
| **Phase 4: Deploy App** | 1 hour | Deploy to production |
| **Phase 5: Configure** | 1 hour | Set up monitoring, scaling |
| **Phase 6: Go Live** | 30 min | DNS, SSL, final testing |
| **Total** | **5-6 hours** | |

---

## 🎯 PHASE 1: AWS Setup (1 hour)

### Step 1.1: Create AWS Account

```
1. Go to: https://aws.amazon.com
2. Click "Create an AWS Account"
3. Fill in details:
   - Email
   - Password
   - Account name: "profai-production"
4. Add payment method (credit card)
5. Verify phone number
6. Choose Support Plan: "Basic (Free)"
```

**Cost Alert:** Set up billing alerts immediately!

### Step 1.2: Set Up Billing Alerts

```
1. Go to: AWS Console → Billing Dashboard
2. Click "Billing preferences"
3. Enable:
   ☑ Receive PDF Invoice By Email
   ☑ Receive Free Tier Usage Alerts
   ☑ Receive Billing Alerts
4. Save preferences

5. Go to CloudWatch → Alarms → Create Alarm
6. Select Metric: Billing → Total Estimated Charge
7. Threshold: $100 (or your budget)
8. Create alarm
```

### Step 1.3: Install AWS CLI

**Windows:**
```powershell
# Download installer
# https://awscli.amazonaws.com/AWSCLIV2.msi

# Run installer
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# Verify
aws --version
```

**macOS:**
```bash
brew install awscli
aws --version
```

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

### Step 1.4: Configure AWS CLI

```bash
aws configure

# Enter when prompted:
AWS Access Key ID: <from IAM console>
AWS Secret Access Key: <from IAM console>
Default region name: us-east-1
Default output format: json
```

**Get Access Keys:**
```
1. Go to: AWS Console → IAM
2. Click your username → Security credentials
3. Click "Create access key"
4. Choose "CLI"
5. Copy Access Key ID and Secret Access Key
```

### Step 1.5: Install kubectl

**Windows:**
```powershell
# Download kubectl
curl -LO "https://dl.k8s.io/release/v1.28.0/bin/windows/amd64/kubectl.exe"

# Add to PATH
# Move kubectl.exe to C:\Windows\System32\

# Verify
kubectl version --client
```

**macOS:**
```bash
brew install kubectl
kubectl version --client
```

**Linux:**
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client
```

### Step 1.6: Install eksctl

**Windows:**
```powershell
choco install eksctl
# Or download from: https://github.com/weaveworks/eksctl/releases

eksctl version
```

**macOS:**
```bash
brew tap weaveworks/tap
brew install weaveworks/tap/eksctl
eksctl version
```

**Linux:**
```bash
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin
eksctl version
```

---

## 🎯 PHASE 2: Push Docker Image to ECR (30 min)

### Step 2.1: Create ECR Repository

```bash
# Create repository
aws ecr create-repository \
  --repository-name profai \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true

# Note the repositoryUri from output
# Example: 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai
```

### Step 2.2: Login to ECR

```bash
# Get login password
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Should see: Login Succeeded
```

### Step 2.3: Build and Tag Image

```bash
# Navigate to your project
cd c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Build image
docker build -t profai:latest .

# Tag for ECR (replace with your repository URI)
docker tag profai:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:latest

# Also tag with version
docker tag profai:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:v1.0.0
```

### Step 2.4: Push to ECR

```bash
# Push latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:latest

# Push versioned
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:v1.0.0

# Verify
aws ecr describe-images --repository-name profai --region us-east-1
```

---

## 🎯 PHASE 3: Create EKS Cluster (1 hour)

### Step 3.1: Create Cluster Configuration

Create file: `eks-cluster-config.yaml`

```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig

metadata:
  name: profai-cluster
  region: us-east-1
  version: "1.28"

# VPC Configuration
vpc:
  cidr: 10.0.0.0/16
  nat:
    gateway: Single  # Use Single for cost savings, HighlyAvailable for production

# IAM Configuration
iam:
  withOIDC: true

# Node Groups
nodeGroups:
  # API Node Group (lightweight)
  - name: api-nodes
    instanceType: t3.large
    minSize: 3
    maxSize: 10
    desiredCapacity: 3
    volumeSize: 50
    privateNetworking: true
    labels:
      role: api
    tags:
      nodegroup-role: api
    iam:
      withAddonPolicies:
        autoScaler: true
        cloudWatch: true
        ebs: true

  # Worker Node Group (heavy processing)
  - name: worker-nodes
    instanceType: t3.xlarge
    minSize: 3
    maxSize: 20
    desiredCapacity: 5
    volumeSize: 100
    privateNetworking: true
    labels:
      role: worker
    tags:
      nodegroup-role: worker
    iam:
      withAddonPolicies:
        autoScaler: true
        cloudWatch: true
        ebs: true

# Addons
addons:
  - name: vpc-cni
  - name: coredns
  - name: kube-proxy
  - name: aws-ebs-csi-driver

# CloudWatch Logging
cloudWatch:
  clusterLogging:
    enableTypes: ["api", "audit", "authenticator", "controllerManager", "scheduler"]
```

### Step 3.2: Create Cluster

```bash
# Create cluster (takes 15-20 minutes)
eksctl create cluster -f eks-cluster-config.yaml

# Monitor progress
# You'll see logs as cluster is created

# Expected output:
# [✓] EKS cluster "profai-cluster" in "us-east-1" region is ready
```

### Step 3.3: Configure kubectl

```bash
# Update kubeconfig
aws eks update-kubeconfig --name profai-cluster --region us-east-1

# Verify connection
kubectl get nodes

# Should see 8 nodes (3 api + 5 worker)
```

### Step 3.4: Install Cluster Autoscaler

```bash
# Create IAM policy
cat > cluster-autoscaler-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:DescribeAutoScalingInstances",
        "autoscaling:DescribeLaunchConfigurations",
        "autoscaling:DescribeTags",
        "autoscaling:SetDesiredCapacity",
        "autoscaling:TerminateInstanceInAutoScalingGroup",
        "ec2:DescribeLaunchTemplateVersions"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name AmazonEKSClusterAutoscalerPolicy \
  --policy-document file://cluster-autoscaler-policy.json

# Deploy autoscaler
kubectl apply -f https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml

# Annotate service account
kubectl annotate serviceaccount cluster-autoscaler \
  -n kube-system \
  eks.amazonaws.com/role-arn=arn:aws:iam::ACCOUNT_ID:role/AmazonEKSClusterAutoscalerRole
```

---

## 🎯 PHASE 4: Deploy Application (1 hour)

### Step 4.1: Update Kubernetes Manifests

Update image in all deployment files:

**k8s/5-api-deployment.yaml:**
```yaml
containers:
- name: api
  image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:latest
  # Change from: profai:latest
```

**k8s/10-worker-deployment.yaml:**
```yaml
containers:
- name: worker
  image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:latest
  # Change from: profai:latest
```

### Step 4.2: Create Secrets

**Encode your secrets:**
```bash
# Encode Redis URL
echo -n "rediss://default:ASv0AAInc..." | base64

# Encode Database URL
echo -n "postgresql://user:pass@host/db" | base64

# Encode API keys
echo -n "sk-proj-..." | base64
```

**Update k8s/3-secrets.yaml:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: profai-secrets
  namespace: profai
type: Opaque
data:
  REDIS_URL: <base64 encoded>
  DATABASE_URL: <base64 encoded>
  OPENAI_API_KEY: <base64 encoded>
  SARVAM_API_KEY: <base64 encoded>
  GROQ_API_KEY: <base64 encoded>
  CHROMA_CLOUD_API_KEY: <base64 encoded>
```

### Step 4.3: Deploy to EKS

```bash
# Deploy in order
kubectl apply -f k8s/1-namespace.yaml
kubectl apply -f k8s/2-configmap.yaml
kubectl apply -f k8s/3-secrets.yaml
kubectl apply -f k8s/4-persistent-volume.yaml

# Don't deploy Redis (using Upstash)
# Skip: kubectl apply -f k8s/9-redis.yaml

# Deploy application
kubectl apply -f k8s/5-api-deployment.yaml
kubectl apply -f k8s/6-service.yaml
kubectl apply -f k8s/7-ingress.yaml
kubectl apply -f k8s/8-hpa.yaml
kubectl apply -f k8s/10-worker-deployment.yaml

# Verify deployment
kubectl get all -n profai
```

### Step 4.4: Verify Pods Running

```bash
# Check pods
kubectl get pods -n profai

# Should see:
# profai-api-xxxxx (10 pods)
# profai-worker-xxxxx (10 pods)

# Check logs
kubectl logs -f deployment/profai-api -n profai
kubectl logs -f deployment/profai-worker -n profai

# Should see:
# ✅ Connected to Redis
# ✅ Connected to Database
```

---

## 🎯 PHASE 5: Configure Load Balancer & Monitoring (1 hour)

### Step 5.1: Install AWS Load Balancer Controller

```bash
# Download IAM policy
curl -o iam-policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json

# Create IAM policy
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam-policy.json

# Create IAM service account
eksctl create iamserviceaccount \
  --cluster=profai-cluster \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn=arn:aws:iam::ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy \
  --override-existing-serviceaccounts \
  --approve

# Install controller
kubectl apply -k "github.com/aws/eks-charts/stable/aws-load-balancer-controller/crds?ref=master"

helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=profai-cluster \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

### Step 5.2: Get Load Balancer URL

```bash
# Get ALB URL
kubectl get ingress -n profai

# Output will show:
# NAME              CLASS    HOSTS   ADDRESS                          PORTS
# profai-ingress    <none>   *       k8s-profai-xxxxx.us-east-1.elb.amazonaws.com   80, 443

# Test it
curl http://k8s-profai-xxxxx.us-east-1.elb.amazonaws.com/health
```

### Step 5.3: Set Up CloudWatch Monitoring

```bash
# Install CloudWatch Container Insights
aws eks create-addon \
  --cluster-name profai-cluster \
  --addon-name amazon-cloudwatch-observability

# Verify
kubectl get pods -n amazon-cloudwatch
```

### Step 5.4: Set Up CloudWatch Alarms

**Create alarms file: `cloudwatch-alarms.sh`**

```bash
#!/bin/bash

# High CPU Alarm (API Pods)
aws cloudwatch put-metric-alarm \
  --alarm-name profai-api-high-cpu \
  --alarm-description "Alert when API CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EKS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High CPU Alarm (Worker Pods)
aws cloudwatch put-metric-alarm \
  --alarm-name profai-worker-high-cpu \
  --alarm-description "Alert when Worker CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/EKS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High Memory Alarm
aws cloudwatch put-metric-alarm \
  --alarm-name profai-high-memory \
  --alarm-description "Alert when memory exceeds 85%" \
  --metric-name MemoryUtilization \
  --namespace AWS/EKS \
  --statistic Average \
  --period 300 \
  --threshold 85 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

echo "✅ CloudWatch alarms created"
```

Run it:
```bash
bash cloudwatch-alarms.sh
```

---

## 🎯 PHASE 6: Go Live! (30 min)

### Step 6.1: Set Up Domain (Optional)

**If you have a domain:**

```bash
# Get Load Balancer URL
ALB_URL=$(kubectl get ingress profai-ingress -n profai -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo "Your ALB URL: $ALB_URL"

# Add CNAME record in your DNS:
# api.yourdomain.com → k8s-profai-xxxxx.us-east-1.elb.amazonaws.com
```

**Update ingress for custom domain:**

```yaml
# k8s/7-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: profai-ingress
  namespace: profai
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID
spec:
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: profai-service
            port:
              number: 5001
```

### Step 6.2: Set Up SSL Certificate (Optional)

```bash
# Request certificate in AWS Certificate Manager
aws acm request-certificate \
  --domain-name api.yourdomain.com \
  --validation-method DNS \
  --region us-east-1

# Follow email/DNS validation
# Then update ingress with certificate ARN (see above)
```

### Step 6.3: Final Testing

```bash
# Get your public URL
ALB_URL=$(kubectl get ingress profai-ingress -n profai -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Test health endpoint
curl http://$ALB_URL/health

# Test upload (with your PDF)
curl -X POST http://$ALB_URL/api/upload-pdfs \
  -F "files=@test.pdf" \
  -F "course_title=Production Test"

# Should return task_id immediately!
```

### Step 6.4: Load Testing

```bash
# Install k6 (load testing tool)
# Windows: choco install k6
# macOS: brew install k6
# Linux: snap install k6

# Create load test
cat > loadtest.js <<EOF
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },   // Ramp to 100 users
    { duration: '5m', target: 100 },   // Stay at 100
    { duration: '2m', target: 500 },   // Ramp to 500
    { duration: '5m', target: 500 },   // Stay at 500
    { duration: '2m', target: 0 },     // Ramp down
  ],
};

export default function () {
  let res = http.get('http://YOUR_ALB_URL/health');
  check(res, { 'status was 200': (r) => r.status == 200 });
  sleep(1);
}
EOF

# Run load test
k6 run loadtest.js
```

---

## 📊 Monitoring & Maintenance

### CloudWatch Dashboard

```
1. Go to: AWS Console → CloudWatch → Dashboards
2. Create dashboard: "ProfAI-Production"
3. Add widgets:
   - EKS Cluster CPU
   - EKS Cluster Memory
   - Pod Count
   - Request Count
   - Error Rate
   - Task Queue Length (from Redis)
```

### Useful Commands

```bash
# View all resources
kubectl get all -n profai

# Scale API pods manually
kubectl scale deployment profai-api --replicas=20 -n profai

# Scale worker pods manually
kubectl scale deployment profai-worker --replicas=50 -n profai

# View logs
kubectl logs -f deployment/profai-api -n profai --tail=100
kubectl logs -f deployment/profai-worker -n profai --tail=100

# View HPA status
kubectl get hpa -n profai

# View pod metrics
kubectl top pods -n profai

# View node metrics
kubectl top nodes

# Restart deployment (if needed)
kubectl rollout restart deployment/profai-api -n profai
kubectl rollout restart deployment/profai-worker -n profai

# View events
kubectl get events -n profai --sort-by='.lastTimestamp'
```

---

## 💰 Cost Optimization

### Current Estimated Cost (Monthly)

| Service | Config | Cost |
|---------|--------|------|
| **EKS Cluster** | 1 cluster | $73 |
| **API Nodes** | 3-10 × t3.large | $225-750 |
| **Worker Nodes** | 5-20 × t3.xlarge | $750-3,000 |
| **Load Balancer** | ALB | $25 |
| **Data Transfer** | 1TB/month | $90 |
| **CloudWatch** | Logs + Metrics | $50 |
| **Upstash Redis** | Free tier | $0 |
| **Neon PostgreSQL** | Free tier | $0 |
| **ChromaDB Cloud** | Free tier | $0 |
| **Total** | | **$1,213-4,988/month** |

### Cost Savings Tips

1. **Use Spot Instances for Workers:**
```yaml
# In eks-cluster-config.yaml
nodeGroups:
  - name: worker-nodes
    instancesDistribution:
      instanceTypes: ["t3.xlarge", "t3a.xlarge"]
      onDemandBaseCapacity: 2
      onDemandPercentageAboveBaseCapacity: 0
      spotInstancePools: 2
```

2. **Right-size Pods:**
```bash
# Monitor actual usage
kubectl top pods -n profai

# Adjust resources in deployment files if over-provisioned
```

3. **Use Reserved Instances (1-year):**
- Save 40% on node costs
- Purchase through AWS Console → EC2 → Reserved Instances

4. **Enable Cluster Autoscaler:**
- Already configured
- Scales down unused nodes automatically

5. **Use Free Tiers:**
- ✅ Upstash Redis (10K commands/day)
- ✅ Neon PostgreSQL (512MB)
- ✅ ChromaDB Cloud (check limits)

---

## 🔒 Security Checklist

- [ ] API keys in AWS Secrets Manager (not in code)
- [ ] Security groups properly configured
- [ ] Private subnets for worker nodes
- [ ] Enable WAF on ALB (optional, $5/month)
- [ ] Regular security scans: `aws ecr start-image-scan`
- [ ] HTTPS enabled (SSL certificate)
- [ ] Restrict Kubernetes API access
- [ ] Enable audit logging in CloudWatch
- [ ] Regular backups of Neon database
- [ ] Implement rate limiting in API

---

## 📋 Final Checklist

### Before Going Live

- [ ] Local testing completed successfully
- [ ] Docker image pushed to ECR
- [ ] EKS cluster created and configured
- [ ] All pods running healthy
- [ ] Load balancer accessible
- [ ] Database migrations run
- [ ] CloudWatch monitoring configured
- [ ] Alarms set up
- [ ] Load testing completed
- [ ] SSL certificate configured (if using custom domain)
- [ ] Backup strategy in place
- [ ] Cost alerts configured
- [ ] Documentation updated

### Post-Deployment

- [ ] Monitor CloudWatch dashboards daily
- [ ] Check pod health: `kubectl get pods -n profai`
- [ ] Review logs for errors
- [ ] Monitor costs in AWS Billing
- [ ] Test uploads regularly
- [ ] Verify auto-scaling works
- [ ] Update team on API endpoint
- [ ] Schedule regular backups

---

## 🚨 Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod POD_NAME -n profai

# Common issues:
# - ImagePullBackOff: Wrong ECR URL or permissions
# - CrashLoopBackOff: Check logs
# - Pending: Insufficient resources
```

### Cannot Connect to Database

```bash
# Test from pod
kubectl exec -it POD_NAME -n profai -- python -c "
import psycopg2
conn = psycopg2.connect('$DATABASE_URL')
print('Connected!')
"
```

### High Costs

```bash
# Check node count
kubectl get nodes

# Check pod count
kubectl get pods -n profai | wc -l

# Scale down if too many
kubectl scale deployment profai-worker --replicas=5 -n profai
```

### Slow Performance

```bash
# Check HPA
kubectl get hpa -n profai

# Check metrics
kubectl top pods -n profai

# Scale up if needed
kubectl scale deployment profai-worker --replicas=20 -n profai
```

---

## 🎉 You're Live!

Congratulations! Your application is now running on AWS EKS!

**Your Production URL:**
```
http://k8s-profai-xxxxx.us-east-1.elb.amazonaws.com
```

**Monitor it:**
- CloudWatch: https://console.aws.amazon.com/cloudwatch
- EKS: https://console.aws.amazon.com/eks
- Logs: `kubectl logs -f deployment/profai-api -n profai`

**Scale it:**
- API: 10-50 pods (auto-scales)
- Workers: 10-100 pods (auto-scales)
- Handles 5,500+ concurrent users!

---

## 📞 Support

**Need help?**
- Check logs: `kubectl logs -f deployment/profai-api -n profai`
- Check events: `kubectl get events -n profai`
- Check CloudWatch: AWS Console → CloudWatch → Logs
- AWS Support: https://console.aws.amazon.com/support

**Update deployment:**
```bash
# Build new image
docker build -t profai:v1.0.1 .
docker tag profai:v1.0.1 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:v1.0.1
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:v1.0.1

# Update deployment
kubectl set image deployment/profai-api api=123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:v1.0.1 -n profai
kubectl set image deployment/profai-worker worker=123456789012.dkr.ecr.us-east-1.amazonaws.com/profai:v1.0.1 -n profai
```

---

**You did it! 🚀**
