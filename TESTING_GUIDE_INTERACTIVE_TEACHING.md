# 🧪 Testing Guide - Interactive Teaching Mode

**Version:** 1.0  
**Date:** February 7, 2026  
**Status:** Ready for Testing

---

## 📋 Pre-Testing Checklist

### **Environment Setup**

- [ ] Server running on port 8765 (WebSocket)
- [ ] Deepgram API key configured in `.env`
- [ ] ElevenLabs API key configured in `.env`
- [ ] OpenAI API key configured in `.env`
- [ ] PostgreSQL database accessible
- [ ] Redis cache running (optional)

### **Verify Services**

```bash
# Check environment variables
grep DEEPGRAM_API_KEY .env
grep ELEVENLABS_API_KEY .env
grep OPENAI_API_KEY .env

# Verify database connection
psql $DATABASE_URL -c "SELECT 1"

# Check if ports are available
netstat -an | grep 8765
```

---

## 🚀 Quick Start Test

### **Step 1: Start Server**

```bash
cd Prof_AI-8126
python run_profai_websocket_celery.py
```

**Expected Output:**
```
✅ WebSocket server starting on 0.0.0.0:8765
✅ Session manager initialized
✅ Services initialized: chat, audio, teaching
```

### **Step 2: Open Client**

1. Open `interactive-teaching-client.html` in Chrome/Edge (requires HTTPS or localhost)
2. Allow microphone access when prompted
3. Verify UI loads correctly

### **Step 3: Basic Connection Test**

1. Click "Start Interactive Teaching"
2. **Expected:**
   - Connection status: ✅ Connected (green)
   - Microphone status: 🎤 Listening (blue)
   - Teaching state: "Initializing" → "Teaching Active"

---

## 🧪 Test Scenarios

### **Test 1: Normal Teaching Flow**

**Objective:** Verify complete teaching cycle without interruptions

**Steps:**
1. Click "Start Interactive Teaching"
2. Wait for teaching audio to complete
3. Observe conversation log

**Expected Results:**
- ✅ Teaching audio streams in chunks
- ✅ Text appears in conversation log
- ✅ "Section complete" message displayed
- ✅ "Continue Lesson" button enabled
- ✅ All messages saved to database

**Validation:**
```sql
-- Check database for messages
SELECT * FROM messages 
WHERE session_id = '<session_id>' 
ORDER BY created_at DESC 
LIMIT 10;
```

---

### **Test 2: User Interruption (Barge-in)**

**Objective:** Verify TTS cancellation when user speaks

**Steps:**
1. Start teaching session
2. While professor is speaking, **speak loudly**: "What is this?"
3. Wait for question to be transcribed
4. Observe response

**Expected Results:**
- ✅ Teaching audio stops within 500ms
- ✅ VAD bar shows activity (animated)
- ✅ Status changes to "Speaking"
- ✅ Message: "👂 Listening to your question..."
- ✅ Your question appears in conversation log
- ✅ Answer is generated and spoken
- ✅ All messages saved to database

**Success Criteria:**
- Barge-in latency < 500ms
- Question transcribed accurately (>95%)
- Answer contextually relevant

---

### **Test 3: Multiple Interruptions**

**Objective:** Verify system handles repeated interruptions

**Steps:**
1. Start teaching
2. Ask question 1: "What is the main topic?"
3. Wait for answer
4. Ask question 2: "Can you explain that?"
5. Wait for answer
6. Ask question 3: "Give me an example"

**Expected Results:**
- ✅ All 3 Q&A cycles complete successfully
- ✅ Conversation history preserved
- ✅ Each answer references previous context
- ✅ 6 messages saved to database (3 user + 3 assistant)

---

### **Test 4: Continue Teaching**

**Objective:** Verify teaching resumes after Q&A

**Steps:**
1. Complete a Q&A cycle
2. Wait for "Answer complete" message
3. Click "Continue Lesson" button
4. Observe teaching resumes

**Expected Results:**
- ✅ Teaching audio resumes
- ✅ Status changes to "Teaching Active"
- ✅ Continue button disabled
- ✅ No audio overlap

---

### **Test 5: Session Persistence**

**Objective:** Verify database storage

**Steps:**
1. Complete teaching session with 2-3 questions
2. Check database

**Validation Queries:**
```sql
-- Check user_sessions table
SELECT * FROM user_sessions 
WHERE user_id = '167' 
ORDER BY started_at DESC 
LIMIT 1;

-- Check messages table
SELECT 
    role, 
    content, 
    message_type, 
    course_id,
    created_at
FROM messages 
WHERE session_id = '<session_id>'
ORDER BY created_at;
```

**Expected Results:**
- ✅ Session record with valid `session_id`
- ✅ All user questions saved (role='user')
- ✅ All assistant answers saved (role='assistant')
- ✅ `course_id` correctly set
- ✅ `message_type` = 'voice'
- ✅ Timestamps sequential

---

### **Test 6: End Teaching**

**Objective:** Verify proper cleanup

**Steps:**
1. Start teaching session
2. Click "End Teaching" button
3. Observe cleanup

**Expected Results:**
- ✅ Message: "Teaching session ended"
- ✅ WebSocket closes gracefully
- ✅ Microphone access released
- ✅ All buttons return to initial state
- ✅ No memory leaks (check browser DevTools)

**Server Logs:**
```
🛑 Ending teaching session...
✅ STT service closed
✅ TTS task cancelled
✅ Teaching session ended
🔌 Client disconnected
```

---

### **Test 7: Error Handling**

**Objective:** Verify graceful error handling

#### **7a. STT Service Failure**

**Steps:**
1. Stop server or invalidate `DEEPGRAM_API_KEY`
2. Start teaching session

**Expected Results:**
- ✅ Message: "Voice input not available. Using one-way teaching."
- ✅ Falls back to `handle_start_class()`
- ✅ Teaching continues without voice input

#### **7b. Network Disconnection**

**Steps:**
1. Start teaching session
2. Stop server mid-session
3. Observe client behavior

**Expected Results:**
- ✅ Connection status: "Disconnected"
- ✅ Error message displayed
- ✅ Buttons reset to initial state
- ✅ No JavaScript errors

#### **7c. Microphone Access Denied**

**Steps:**
1. Block microphone in browser settings
2. Try to start teaching

**Expected Results:**
- ✅ Error message: "Microphone access denied"
- ✅ WebSocket closes
- ✅ User prompted to allow access

---

### **Test 8: Audio Quality**

**Objective:** Verify audio is clear and synchronized

**Steps:**
1. Complete teaching session with Q&A
2. Listen to all audio carefully

**Expected Results:**
- ✅ Teaching audio: Clear, no distortion
- ✅ Answer audio: Clear, no distortion
- ✅ No audio overlap or echo
- ✅ Latency < 300ms for first audio chunk
- ✅ No clipping or buffer underruns

---

### **Test 9: VAD Sensitivity**

**Objective:** Verify VAD threshold is appropriate

**Steps:**
1. Test with different speaking volumes:
   - Whisper (very quiet)
   - Normal conversation
   - Loud speaking

**Expected Results:**
- ✅ Whisper: May not trigger (acceptable)
- ✅ Normal: Triggers reliably
- ✅ Loud: Triggers immediately
- ✅ Background noise: Does NOT trigger
- ✅ VAD bar visualizes levels correctly

**Adjustment (if needed):**
```javascript
// In interactive-teaching-client.html
const VAD_THRESHOLD = 0.01;  // Decrease for more sensitivity
const NOISE_GATE = 0.005;    // Decrease to pick up quieter sounds
```

---

### **Test 10: Concurrent Users**

**Objective:** Verify multiple users can use system simultaneously

**Steps:**
1. Open 3 browser tabs/windows
2. Start teaching in all 3 simultaneously
3. Interact with each independently

**Expected Results:**
- ✅ All 3 sessions work independently
- ✅ No cross-talk or interference
- ✅ Each has unique `session_id`
- ✅ Database shows 3 separate sessions
- ✅ Server performance remains stable

---

## 📊 Performance Benchmarks

### **Target Metrics**

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Barge-in Latency** | < 500ms | Time from speech_started to TTS cancel |
| **STT Accuracy** | > 95% | Manual transcript review |
| **Answer Latency** | < 3s | Time from question to answer audio |
| **First Audio Chunk** | < 300ms | Server logs |
| **Message Persistence** | 100% | Database audit |
| **Memory Usage** | < 200MB/session | Browser DevTools |

### **Measurement Tools**

```javascript
// Add to client for timing measurements
const timings = {
    questionStart: null,
    answerReceived: null,
    audioStart: null
};

// In handleServerMessage
case 'user_question':
    timings.answerReceived = Date.now();
    console.log('Answer latency:', timings.answerReceived - timings.questionStart);
```

---

## 🐛 Common Issues & Solutions

### **Issue 1: "WebSocket connection failed"**

**Causes:**
- Server not running
- Wrong port (should be 8765)
- Firewall blocking connection

**Solution:**
```bash
# Check if server is running
ps aux | grep websocket

# Check port
netstat -an | grep 8765

# Restart server
python run_profai_websocket_celery.py
```

---

### **Issue 2: "Microphone not working"**

**Causes:**
- Browser permissions denied
- Not using HTTPS/localhost
- Wrong audio device selected

**Solution:**
1. Check browser permissions: `chrome://settings/content/microphone`
2. Use localhost or HTTPS
3. Test microphone in system settings

---

### **Issue 3: "No teaching audio"**

**Causes:**
- ElevenLabs API key invalid
- Network timeout
- Audio service not initialized

**Solution:**
```bash
# Verify API key
curl -H "xi-api-key: $ELEVENLABS_API_KEY" https://api.elevenlabs.io/v1/voices

# Check server logs
tail -f server.log | grep "audio"
```

---

### **Issue 4: "User questions not transcribed"**

**Causes:**
- Deepgram API key invalid
- VAD threshold too high
- Speaking too quietly

**Solution:**
1. Verify `DEEPGRAM_API_KEY` in `.env`
2. Lower VAD threshold in client
3. Speak louder or closer to microphone

---

### **Issue 5: "Database errors"**

**Causes:**
- PostgreSQL not running
- Connection string invalid
- Table schema mismatch

**Solution:**
```bash
# Test database connection
psql $DATABASE_URL -c "SELECT version();"

# Check tables exist
psql $DATABASE_URL -c "\dt"

# Verify schema
psql $DATABASE_URL -c "\d messages"
```

---

## 📝 Test Report Template

```markdown
# Interactive Teaching Test Report

**Date:** [Date]  
**Tester:** [Name]  
**Environment:** [Local/Production]

## Test Results

| Test | Status | Notes |
|------|--------|-------|
| Normal Teaching Flow | ✅/❌ | |
| User Interruption | ✅/❌ | |
| Multiple Interruptions | ✅/❌ | |
| Continue Teaching | ✅/❌ | |
| Session Persistence | ✅/❌ | |
| End Teaching | ✅/❌ | |
| Error Handling | ✅/❌ | |
| Audio Quality | ✅/❌ | |
| VAD Sensitivity | ✅/❌ | |
| Concurrent Users | ✅/❌ | |

## Performance Metrics

- Barge-in Latency: [X]ms
- STT Accuracy: [X]%
- Answer Latency: [X]s
- First Audio Chunk: [X]ms

## Issues Found

1. [Issue description]
   - Severity: High/Medium/Low
   - Steps to reproduce
   - Expected vs Actual

## Recommendations

- [Recommendation 1]
- [Recommendation 2]
```

---

## 🚀 Production Readiness Checklist

Before deploying to production:

- [ ] All tests passing (10/10)
- [ ] Performance benchmarks met
- [ ] Error handling verified
- [ ] Database persistence working
- [ ] Security review completed
- [ ] API keys secured (not in code)
- [ ] HTTPS enabled
- [ ] Rate limiting configured
- [ ] Monitoring/logging setup
- [ ] User documentation written
- [ ] Backup/recovery tested

---

## 📚 Next Steps After Testing

1. ✅ **If all tests pass:**
   - Document any configuration tweaks
   - Deploy to staging environment
   - Run load tests with multiple users
   - Get user feedback

2. ⚠️ **If issues found:**
   - Document all issues in test report
   - Prioritize by severity
   - Fix critical issues first
   - Re-test after fixes

3. 📊 **Performance Optimization:**
   - Profile memory usage
   - Optimize audio buffering
   - Tune VAD parameters per environment
   - Cache frequently accessed course content

---

**Happy Testing!** 🎉

For issues or questions, check server logs and browser DevTools console.
