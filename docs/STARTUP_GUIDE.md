# ProfessorAI - Quick Start Guide

## Prerequisites

1. **Python 3.11+** installed
2. **Redis** (local or Upstash cloud)
3. **PostgreSQL** (Neon cloud recommended)
4. **API Keys**:
   - OpenAI API Key
   - Sarvam AI API Key (for TTS)
   - Groq API Key
   - ChromaDB Cloud (optional)

## Setup Steps

### 1. Create `.env` file

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

**Minimum required variables:**
```env
# API Keys (REQUIRED)
OPENAI_API_KEY=sk-proj-your-key-here
SARVAM_API_KEY=your-sarvam-key
GROQ_API_KEY=your-groq-key

# Database (REQUIRED if using database)
USE_DATABASE=True
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require

# Redis (REQUIRED for Celery)
REDIS_URL=redis://localhost:6379/0
# OR for Upstash:
# REDIS_URL=rediss://default:pass@endpoint.upstash.io:6379

# Server
HOST=0.0.0.0
PORT=5001
DEBUG=True
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Database Migration (if using PostgreSQL)

```bash
python migrate_json_to_db.py
```

### 4. Start the Application

#### Option A: Simple Mode (No Celery - For Testing)
```bash
python app.py
```

#### Option B: Production Mode (With Celery Workers)

**Terminal 1 - Start Celery Worker:**
```bash
celery -A celery_app worker --loglevel=info --pool=solo
```

**Terminal 2 - Start Application:**
```bash
python run_profai_websocket_celery.py
```

### 5. Access the Application

- **API Documentation**: http://localhost:5001/docs
- **Health Check**: http://localhost:5001/health
- **WebSocket**: ws://localhost:8765

## Common Issues & Solutions

### Issue 1: "No module named 'dotenv'"
**Solution:**
```bash
pip install python-dotenv
```

### Issue 2: "Redis connection refused"
**Solution:**
- Make sure Redis is running (local) OR
- Use Upstash Redis (cloud, free tier available)
- Check REDIS_URL in .env

### Issue 3: "OPENAI_API_KEY not found"
**Solution:**
- Create `.env` file from `.env.example`
- Add your actual API keys

### Issue 4: "Cannot connect to database"
**Solution:**
- Set `USE_DATABASE=False` in `.env` to use JSON files instead
- OR fix your `DATABASE_URL` in `.env`

### Issue 5: Services initialization fails
**Solution:**
- Check all API keys are valid
- Ensure network connectivity
- Check logs for specific service errors

## Architecture Overview

### Components:
1. **FastAPI Server** (Port 5001) - REST API
2. **WebSocket Server** (Port 8765) - Real-time communication
3. **Celery Workers** - Background task processing
4. **Redis** - Message broker for Celery
5. **PostgreSQL** - Data persistence (optional)
6. **ChromaDB Cloud** - Vector database (optional)

### Services:
- **ChatService** - RAG-based Q&A
- **DocumentService** - PDF processing & course generation
- **AudioService** - Text-to-speech (Sarvam AI)
- **TeachingService** - Educational content generation
- **QuizService** - Quiz management

## File Structure

```
Prof_AI/
├── app.py                          # Simple FastAPI server
├── app_celery.py                   # Production server with Celery
├── run_profai_websocket_celery.py  # Production entry point
├── websocket_server.py             # WebSocket handler
├── config.py                       # Configuration
├── celery_app.py                   # Celery configuration
├── migrate_json_to_db.py           # Database migration
├── services/                       # Business logic
│   ├── chat_service.py
│   ├── document_service.py
│   ├── audio_service.py
│   ├── teaching_service.py
│   ├── quiz_service.py
│   └── database_service_new.py
├── tasks/                          # Celery tasks
│   ├── pdf_processing.py
│   └── quiz_generation.py
├── models/                         # Data models
└── data/                           # Data storage
    ├── courses/
    ├── quizzes/
    └── documents/
```

## Testing the API

### 1. Health Check
```bash
curl http://localhost:5001/health
```

### 2. Get Courses
```bash
curl http://localhost:5001/api/courses
```

### 3. Upload PDF (with Celery)
```bash
curl -X POST http://localhost:5001/api/upload-pdfs \
  -F "files=@document.pdf" \
  -F "course_title=My Course"
```

### 4. Check Job Status
```bash
curl http://localhost:5001/api/jobs/{task_id}
```

## Development Tips

1. **Use Simple Mode First**: Start with `app.py` to test without Celery complexity
2. **Check Logs**: Monitor console output for error messages
3. **Test Services**: Use `/health` endpoint to verify service availability
4. **Environment**: Keep `.env` file secure, never commit it to git

## Production Deployment

For production deployment to AWS ECS/EKS, see:
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Local orchestration
- `k8s/` folder - Kubernetes manifests (coming soon)

## Support

For issues, check:
1. Application logs in console
2. Celery worker logs
3. Redis connection
4. Database connection
5. API key validity
