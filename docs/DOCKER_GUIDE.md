# 🐳 Docker Testing Guide - Stage 1

## ✅ Files Created

- `Dockerfile` - Container build instructions
- `.dockerignore` - Files to exclude from container
- `docker-compose.yml` - Service orchestration
- `test-docker.bat` - Quick testing script

## 🚀 Quick Start

### Option 1: Using the Test Script (Easiest)

```bash
# Double-click test-docker.bat
# OR run in Command Prompt:
test-docker.bat
```

Choose option 2 to build and run.

### Option 2: Manual Commands

```bash
# Navigate to project directory
cd "c:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI"

# Build and start
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

## 🧪 Testing Checklist

Once the container is running, verify:

### 1. Check Container Status
```bash
docker ps
```
Should show `profai-local` container running.

### 2. Check Logs
```bash
docker-compose logs profai
```
Should see:
- ✅ FastAPI server starting
- ✅ WebSocket server starting
- ✅ Services initialized
- ❌ No error messages

### 3. Test API Endpoints

Open browser and test:
- **Main API**: http://localhost:5001
- **API Documentation**: http://localhost:5001/docs
- **Health Check**: http://localhost:5001/

### 4. Test with cURL (PowerShell)
```powershell
# Health check
curl http://localhost:5001/

# Test chat endpoint
$headers = @{
    "Content-Type" = "application/json"
}
$body = @{
    message = "Hello"
    language = "en-IN"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:5001/api/chat -Method Post -Headers $headers -Body $body
```

### 5. Test WebSocket
Open: http://localhost:5001/profai-websocket-test.html

## 📊 Expected Output

When running `docker-compose up`, you should see:

```
Creating network "prof_ai_profai-network" with driver "bridge"
Building profai
[+] Building 120.5s (18/18) FINISHED
Successfully built abc123def456
Successfully tagged profai:latest
Creating profai-local ... done
Attaching to profai-local

profai-local | ========================================
profai-local | 🚀 Starting FastAPI server on http://0.0.0.0:5001
profai-local | 🌐 Starting WebSocket server on ws://0.0.0.0:8765
profai-local | ========================================
profai-local | INFO: Started server process
profai-local | INFO: Uvicorn running on http://0.0.0.0:5001
profai-local | ✅ All services initialized successfully
```

## ⚠️ Common Issues & Solutions

### Issue 1: "Port already in use"
```
Error: bind: address already in use
```

**Solution:**
```bash
# Find process using port
netstat -ano | findstr :5001
netstat -ano | findstr :8765

# Kill process (replace PID)
taskkill /PID <process_id> /F
```

### Issue 2: "Cannot connect to Docker daemon"
```
ERROR: error during connect
```

**Solution:**
- Open Docker Desktop
- Wait for it to fully start (whale icon should be steady)
- Try again

### Issue 3: "Module not found" errors in logs
```
ModuleNotFoundError: No module named 'xyz'
```

**Solution:**
```bash
# Rebuild without cache
docker-compose build --no-cache
docker-compose up
```

### Issue 4: "Permission denied" on volumes
```
Error response from daemon: error while creating mount
```

**Solution:**
1. Open Docker Desktop
2. Settings → Resources → File Sharing
3. Add your project directory
4. Apply & Restart

### Issue 5: ".env file not found" or "API key missing"
```
ValueError: OPENAI_API_KEY is required
```

**Solution:**
- Verify `.env` file exists in project root
- Check it contains all required keys:
  - OPENAI_API_KEY
  - SARVAM_API_KEY
  - GROQ_API_KEY
- Restart container: `docker-compose restart`

## 🛠️ Useful Commands

### Container Management
```bash
# Stop container
docker-compose down

# Restart container
docker-compose restart

# View logs
docker-compose logs -f profai

# Execute command in container
docker exec -it profai-local bash

# Check container stats
docker stats profai-local
```

### Image Management
```bash
# List images
docker images

# Remove image
docker rmi profai:latest

# Clean up unused images
docker image prune -a
```

### Debugging
```bash
# View detailed logs
docker-compose logs --tail=100 profai

# Check container processes
docker top profai-local

# Inspect container
docker inspect profai-local

# Check health status
docker inspect --format='{{.State.Health.Status}}' profai-local
```

## ✅ Success Criteria

Before moving to Stage 2, ensure:

- [ ] Container builds successfully
- [ ] Container starts without errors
- [ ] Can access http://localhost:5001
- [ ] API documentation loads at /docs
- [ ] Logs show both FastAPI and WebSocket starting
- [ ] No error messages in logs
- [ ] Health check passes
- [ ] Can make API requests successfully

## 🎯 What's Next?

Once Stage 1 is complete and working:
- **Stage 2**: Create Kubernetes manifests
- **Stage 3**: Test locally with Minikube/Docker Desktop K8s
- **Stage 4**: Prepare AWS infrastructure
- **Stage 5**: Deploy to AWS ECS
- **Stage 6**: Deploy to AWS EKS (full Kubernetes)

## 📚 What You Learned

1. **Docker Images**: Packaged application with all dependencies
2. **Containers**: Running instances of images
3. **Multi-stage builds**: Smaller, more secure images
4. **Docker Compose**: Manage multiple services easily
5. **Volumes**: Persist data outside containers
6. **Port mapping**: Expose container ports to host
7. **Environment variables**: Configuration management
8. **Health checks**: Monitor container health

## 🆘 Need Help?

If you encounter issues:
1. Check this guide for common solutions
2. View logs: `docker-compose logs -f`
3. Verify Docker Desktop is running
4. Check .env file exists and has correct keys
5. Try rebuilding: `docker-compose build --no-cache`
