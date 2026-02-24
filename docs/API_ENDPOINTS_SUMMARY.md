# ProfAI API Endpoints - Complete List

## ✅ Production API (app_celery.py) - ALL ENDPOINTS RESTORED

### **Celery Background Processing**
- **POST** `/api/upload-pdfs` - Upload PDFs and process with Celery workers (async)
- **GET** `/api/jobs/{task_id}` - Get Celery task status  
- **GET** `/api/worker-stats` - Get Celery worker statistics

### **Course Management**
- **GET** `/api/courses` - List all available courses
- **GET** `/api/course/{course_id}` - Get specific course details ✅ ADDED

### **Quiz Endpoints** ✅ ALL ADDED
- **POST** `/api/quiz/generate-module` - Generate 20-question module quiz
- **POST** `/api/quiz/generate-course` - Generate 40-question course quiz
- **POST** `/api/quiz/submit` - Submit quiz answers for evaluation
- **GET** `/api/quiz/{quiz_id}` - Get quiz (without answers)

### **Chat & Communication** ✅ ALL ADDED
- **POST** `/api/chat` - Text-only chat (RAG-based Q&A)
- **POST** `/api/chat-with-audio` - Chat with automatic audio response
- **POST** `/api/transcribe` - Audio transcription (STT)

### **Teaching Mode** ✅ ADDED
- **POST** `/api/start-class` - Start class session with teaching content + audio

### **System Endpoints**
- **GET** `/` - Root endpoint (API info)
- **GET** `/health` - Health check with service status

---

## 📊 Comparison: Before vs After

### **Before Fix (6 endpoints):**
1. POST /api/upload-pdfs
2. GET /api/jobs/{task_id}
3. GET /api/worker-stats
4. GET /api/courses
5. GET /
6. GET /health

### **After Fix (16 endpoints):**
✅ All 6 original endpoints
✅ **+10 NEW endpoints added:**
1. GET /api/course/{course_id}
2. POST /api/quiz/generate-module
3. POST /api/quiz/generate-course  
4. POST /api/quiz/submit
5. GET /api/quiz/{quiz_id}
6. POST /api/chat
7. POST /api/chat-with-audio
8. POST /api/transcribe
9. **POST /api/start-class** ← Teaching Mode (you requested this!)
10. (More can be added as needed)

---

## 🎯 Key Features Now Available

### **1. Teaching Mode API** (`/api/start-class`)
```json
POST /api/start-class
{
  "course_id": "1",
  "module_index": 0,
  "sub_topic_index": 0,
  "language": "en-IN",
  "content_only": false
}
```
**Response:** Audio stream (MP3) of teaching content

**With content_only=true:**
```json
{
  "content_preview": "Welcome to...",
  "full_content_length": 1500,
  "module_title": "Introduction",
  "sub_topic_title": "Getting Started"
}
```

### **2. Quiz Generation**
```json
POST /api/quiz/generate-module
{
  "course_id": "1",
  "module_week": 1
}
```

### **3. Chat with Audio**
```json
POST /api/chat-with-audio
{
  "message": "Explain photosynthesis",
  "language": "en-IN"
}
```
**Response:**
```json
{
  "answer": "Photosynthesis is...",
  "audio_data": "base64_encoded_audio",
  "metadata": {...}
}
```

---

## 🔧 Services Required

All endpoints require these services to be initialized:
- ✅ **ChatService** - RAG-based Q&A
- ✅ **AudioService** - TTS (Sarvam AI)
- ✅ **TeachingService** - Educational content generation
- ✅ **QuizService** - Quiz management
- ✅ **Celery** - Background task processing

---

## 🚀 How to Test

### **1. Start Celery Worker:**
```bash
celery -A celery_app worker --loglevel=info --pool=solo
```

### **2. Start Production API:**
```bash
python run_profai_websocket_celery.py
```

### **3. Access Swagger UI:**
Open: http://localhost:5001/docs

### **4. Test Teaching Mode:**
```bash
curl -X POST http://localhost:5001/api/start-class \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "1",
    "module_index": 0,
    "sub_topic_index": 0,
    "language": "en-IN",
    "content_only": true
  }'
```

---

## 📝 Notes

- All endpoints support multiple languages (11 Indian languages + English)
- Audio responses use Sarvam AI TTS
- Quiz generation uses GPT-5 for high-quality questions
- Teaching content is optimized for educational delivery
- All services have 3-retry logic with graceful degradation

---

## 🎉 Status: COMPLETE

**All missing endpoints have been restored to app_celery.py**
