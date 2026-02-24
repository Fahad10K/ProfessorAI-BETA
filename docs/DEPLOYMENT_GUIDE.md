# 🚀 DEPLOYMENT GUIDE - Direct File Update

## Files to Update on Server

### **6 Files Need Replacement:**

1. `models/schemas.py`
2. `services/quiz_service.py`
3. `services/database_service_actual.py`
4. `services/rag_service.py`
5. `config.py`
6. `app_celery.py`

---

## 📋 Step-by-Step Deployment Instructions

### **Step 1: Connect to Your Server**

```bash
# SSH into your server
ssh your-username@your-server-ip

# Example:
# ssh ubuntu@3.110.123.45
# OR
# ssh root@profai.example.com
```

---

### **Step 2: Navigate to Application Directory**

```bash
# Find your application path
cd /path/to/ProfessorAI_0.2_AWS_Ready/Prof_AI

# Common paths:
# cd /home/ubuntu/ProfessorAI_0.2_AWS_Ready/Prof_AI
# cd /var/www/profai/Prof_AI
# cd /opt/profai/Prof_AI
```

---

### **Step 3: Create Backup**

```bash
# Create backup directory with timestamp
mkdir -p backups/$(date +%Y%m%d_%H%M%S)

# Backup all 6 files
cp models/schemas.py backups/$(date +%Y%m%d_%H%M%S)/
cp services/quiz_service.py backups/$(date +%Y%m%d_%H%M%S)/
cp services/database_service_actual.py backups/$(date +%Y%m%d_%H%M%S)/
cp services/rag_service.py backups/$(date +%Y%m%d_%H%M%S)/
cp config.py backups/$(date +%Y%m%d_%H%M%S)/
cp app_celery.py backups/$(date +%Y%m%d_%H%M%S)/

echo "✅ Backup created in backups/$(date +%Y%m%d_%H%M%S)/"
```

---

### **Step 4: Upload Updated Files**

#### **Option A: Using SCP (from your local machine)**

```bash
# Open NEW terminal on your LOCAL machine (Windows PowerShell)
cd C:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI

# Upload files one by one
scp models/schemas.py your-username@your-server:/path/to/Prof_AI/models/
scp services/quiz_service.py your-username@your-server:/path/to/Prof_AI/services/
scp services/database_service_actual.py your-username@your-server:/path/to/Prof_AI/services/
scp services/rag_service.py your-username@your-server:/path/to/Prof_AI/services/
scp config.py your-username@your-server:/path/to/Prof_AI/
scp app_celery.py your-username@your-server:/path/to/Prof_AI/

# Example:
# scp models/schemas.py ubuntu@3.110.123.45:/home/ubuntu/Prof_AI/models/
```

#### **Option B: Using FTP/SFTP Client (FileZilla, WinSCP)**

1. Connect to your server using FTP/SFTP
2. Navigate to application directory
3. Upload the 6 files to their respective locations:
   - `models/schemas.py` → `models/`
   - `services/quiz_service.py` → `services/`
   - `services/database_service_actual.py` → `services/`
   - `services/rag_service.py` → `services/`
   - `config.py` → root directory
   - `app_celery.py` → root directory

#### **Option C: Manual Copy-Paste (if SSH access)**

```bash
# On server, edit each file
nano models/schemas.py
# Delete old content, paste new content from local file
# Press Ctrl+X, then Y, then Enter to save

# Repeat for all 6 files
```

---

### **Step 5: Verify Files Updated**

```bash
# Check file modification times
ls -lh models/schemas.py
ls -lh services/quiz_service.py
ls -lh services/database_service_actual.py
ls -lh services/rag_service.py
ls -lh config.py
ls -lh app_celery.py

# Should show recent timestamp (today's date/time)
```

---

### **Step 6: Check File Permissions**

```bash
# Ensure files are readable
chmod 644 models/schemas.py
chmod 644 services/quiz_service.py
chmod 644 services/database_service_actual.py
chmod 644 services/rag_service.py
chmod 644 config.py
chmod 644 app_celery.py

echo "✅ File permissions set"
```

---

### **Step 7: Restart Application**

#### **If using Docker:**
```bash
# Check container name
docker ps

# Restart container
docker restart profai-api
# OR
docker-compose restart

# Check logs
docker logs -f profai-api
```

#### **If using Supervisor:**
```bash
# Restart service
sudo supervisorctl restart profai

# Check status
sudo supervisorctl status profai

# View logs
sudo tail -f /var/log/supervisor/profai.log
```

#### **If using systemd:**
```bash
# Restart service
sudo systemctl restart profai

# Check status
sudo systemctl status profai

# View logs
sudo journalctl -u profai -f
```

#### **If using PM2:**
```bash
# Restart application
pm2 restart profai

# Check status
pm2 status

# View logs
pm2 logs profai
```

#### **If running manually:**
```bash
# Find and kill current process
ps aux | grep app_celery
kill <process_id>

# Restart
nohup python app_celery.py > logs/app.log 2>&1 &
```

---

### **Step 8: Verify Deployment**

#### **Test 1: Check Application is Running**
```bash
# Check if application responds
curl http://localhost:5001/

# Or check from browser
# http://your-domain.com/
```

#### **Test 2: Test Quiz Generation**
```bash
curl -X POST http://localhost:5001/api/quiz/generate-module \
  -H "Content-Type: application/json" \
  -d '{"quiz_type":"module","course_id":6,"module_week":2}'

# Expected: 200 OK with quiz data
```

#### **Test 3: Test Quiz Retrieval**
```bash
# Use quiz_id from previous response
curl http://localhost:5001/api/quiz/module_2_xxxxx

# Expected: Quiz data returned from database
```

#### **Test 4: Test Conversation History**
```bash
# Send first message
curl -X POST http://localhost:5001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"what is AI"}'

# Note the session_id from response
# Send follow-up with same session_id
curl -X POST http://localhost:5001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"elaborate more","session_id":"SESSION_ID_HERE"}'

# Expected: Second response uses conversation context
```

---

### **Step 9: Monitor Logs**

```bash
# Watch logs in real-time
tail -f logs/app.log

# Look for these success messages:
# ✅ Created quiz: module_2_xxxxx
# ✅ Quiz saved to database
# ✅ Loaded quiz from database
# 🆕 Generated new session ID: ...
# 💬 Using conversation context from memory
```

---

## ✅ Success Indicators

After deployment, you should see:

1. **Quiz generation works** - No 500 errors
2. **Quiz retrieval works** - Loads from database
3. **Conversation history works** - Session IDs generated and tracked
4. **No garbage responses** - RAG using OpenAI instead of Groq

---

## 🔴 Rollback (If Something Breaks)

```bash
# Restore from backup
BACKUP_DIR=backups/YYYYMMDD_HHMMSS

cp $BACKUP_DIR/schemas.py models/
cp $BACKUP_DIR/quiz_service.py services/
cp $BACKUP_DIR/database_service_actual.py services/
cp $BACKUP_DIR/rag_service.py services/
cp $BACKUP_DIR/config.py .
cp $BACKUP_DIR/app_celery.py .

# Restart application
docker restart profai-api
# OR your restart command
```

---

## 📞 Support

If issues occur:

1. **Check logs:** Look for ERROR messages
2. **Verify file upload:** Ensure all 6 files transferred completely
3. **Check permissions:** Files should be readable (644)
4. **Restart completely:** Sometimes needs full container/service restart

---

## 📝 Deployment Checklist

- [ ] SSH into server
- [ ] Navigate to application directory
- [ ] Create backup of old files
- [ ] Upload 6 updated files
- [ ] Verify files updated (check timestamps)
- [ ] Set file permissions (chmod 644)
- [ ] Restart application service
- [ ] Test quiz generation endpoint
- [ ] Test quiz retrieval endpoint
- [ ] Test conversation history
- [ ] Monitor logs for errors
- [ ] Verify no 500 errors
- [ ] Confirm database storage working

---

**Deployment Date:** _________________

**Deployed By:** _________________

**Server:** _________________

**Status:** ✅ Success / ❌ Issues
