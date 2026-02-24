# ProfAI Troubleshooting Guide

## Quick Fixes for Common Issues

### 1. Buttons Not Working in index.html

**Problem:** Buttons are not responding, course not loading
**Solution:**
```bash
# 1. Verify servers are running
python verify_setup.py

# 2. Check browser console for errors (F12)
# 3. Test with debug page
# Open: http://localhost:5001/test_index_debug.html
```

### 2. WebSocket Connection Issues

**Problem:** "Disconnected" status, no real-time features
**Solution:**
```bash
# Check if WebSocket server is running on port 8765
netstat -an | findstr 8765

# Restart servers
python start_profai.py
```

### 3. Course Loading Problems

**Problem:** "No courses available" or loading errors
**Solution:**
```bash
# 1. Check if course files exist
dir data\courses\course_output.json

# 2. Upload PDFs via upload page
# Open: http://localhost:5001/upload.html

# 3. Test API directly
curl http://localhost:5001/api/courses
```

### 4. Audio Not Playing

**Problem:** Text responses work but no audio
**Solution:**
- Check browser audio permissions
- Verify Sarvam API key in .env file
- Test with: http://localhost:5001/profai-websocket-test.html

## Step-by-Step Debugging

### Step 1: Run Verification Script
```bash
python verify_setup.py
```

### Step 2: Check Debug Page
Open: `http://localhost:5001/test_index_debug.html`
- Click "Test API Connection"
- Click "Test WebSocket" 
- Click "Test Load Courses"

### Step 3: Check Browser Console
Press F12 and look for errors in Console tab

### Step 4: Restart Services
```bash
# Stop all services (Ctrl+C)
# Then restart
python start_profai.py
```

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Connection lost" | WebSocket server down | Restart with `python start_profai.py` |
| "No courses available" | No PDFs uploaded | Upload PDFs via upload page |
| "Service not available" | Missing API keys | Check .env file |
| "Microphone access denied" | Browser permissions | Allow microphone access |

## Contact Support
If issues persist, check the logs in the terminal where you started the servers.