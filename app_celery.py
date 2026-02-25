"""
ProfAI - Production API Server with Celery
Uses distributed task queue for scalability

This is the PRODUCTION version that uses Celery workers.
For simple testing, use app.py (ThreadPoolExecutor version).
"""

import logging
import asyncio
import sys
import os
import json
import time
import base64
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from models.schemas import CourseLMS, TTSRequest, QuizRequest, QuizSubmission, QuizDisplay
from celery_app import celery_app
from tasks.pdf_processing import process_pdf_and_generate_course

# Import WebSocket server
from websocket_server import run_websocket_server_in_thread

# Import services
try:
    from services.chat_service import ChatService
    from services.audio_service import AudioService
    from services.teaching_service import TeachingService
    from services.quiz_service import QuizService
    from services.assessment_service import AssessmentService
    from services.database_service_actual import get_database_service as get_old_database_service
    from services.database_service_v2 import get_database_service
    from services.session_manager import get_session_manager
    SERVICES_AVAILABLE = True
    print("✅ All services loaded successfully")
except ImportError as e:
    print(f"⚠️ Some services not available: {e}")
    SERVICES_AVAILABLE = False

# Import API schemas for Swagger documentation
from models.api_schemas import (
    # Session Management
    SessionCheckResponse, SessionCreateRequest, SessionCreateResponse,
    SessionEndRequest, SessionEndResponse, SessionHistoryResponse,
    # Chat
    ChatRequest, ChatResponse, ChatWithAudioRequest, ChatWithAudioResponse,
    # Courses
    CourseItem,
    # Admin Dashboard
    AdminDashboardResponse,
    # General
    ErrorResponse, HealthCheckResponse
)

# Initialize FastAPI app with comprehensive metadata
app = FastAPI(
    title="ProfAI API (Production)",
    description="""# ProfAI - AI-Powered Educational Assistant
    
## Features
- 🤖 **Intelligent Chat** - Context-aware conversations with RAG (Retrieval-Augmented Generation)
- 💬 **Session Management** - Persistent conversation history with database + Redis caching
- 🎓 **Course Management** - Complete course catalog with enrollments and pricing
- 📊 **Admin Dashboard** - Comprehensive analytics and statistics
- 🔊 **Text-to-Speech** - Multi-language audio generation
- 📝 **Quiz Generation** - AI-powered quiz creation and evaluation

## Authentication
Most endpoints require a valid `user_id`. Session management is handled automatically.

## Rate Limiting
Please respect rate limits to ensure service availability for all users.

## Support
For API support, contact the development team.
    """,
    version="2.0.0-production",
    contact={
        "name": "ProfAI Support",
        "email": "support@profai.com",
    },
    license_info={
        "name": "Proprietary",
    },
    tags_metadata=[
        {
            "name": "Session Management",
            "description": "Manage user sessions and conversation history. Sessions are automatically created on first message and persist across server restarts.",
        },
        {
            "name": "Chat",
            "description": "Text and voice chat endpoints with intelligent routing, RAG, and conversation memory.",
        },
        {
            "name": "Courses",
            "description": "Course catalog, enrollment, and content management.",
        },
        {
            "name": "Quiz",
            "description": "AI-powered quiz generation, submission, and evaluation.",
        },
        {
            "name": "Teaching",
            "description": "Interactive teaching content generation and delivery.",
        },
        {
            "name": "Admin",
            "description": "Administrative endpoints for dashboard statistics and management. **Requires admin authentication.**",
        },
        {
            "name": "Health",
            "description": "Service health check and status endpoints.",
        },
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mount static files
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

# Initialize services
chat_service = None
audio_service = None
teaching_service = None
quiz_service = None
database_service = None
session_manager = None

# Initialize database service V2
try:
    database_service = get_database_service()
    logging.info("✅ DatabaseServiceV2 initialized (Neon DB)")
except Exception as e:
    logging.error(f"❌ Failed to initialize database service: {e}")
    database_service = None

# Initialize session manager
try:
    session_manager = get_session_manager(redis_url=config.REDIS_URL)
    logging.info("✅ SessionManager initialized")
except Exception as e:
    logging.error(f"❌ Failed to initialize session manager: {e}")
    session_manager = None

if SERVICES_AVAILABLE:
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Attempting to initialize services (Attempt {attempt + 1}/{MAX_RETRIES})...")
            chat_service = ChatService()
            audio_service = AudioService()
            teaching_service = TeachingService()
            quiz_service = QuizService()
            assessment_service = AssessmentService()
            logging.info("✅ All services initialized successfully")
            break
        except Exception as e:
            logging.warning(f"⚠️ Failed to initialize services on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                # time.sleep is acceptable here since this runs at module-load
                # time before the event loop starts
                time.sleep(RETRY_DELAY)
            else:
                logging.error("❌ All retries failed. Some services will be unavailable.")
                SERVICES_AVAILABLE = False

# ===== COURSE MANAGEMENT ENDPOINTS =====

@app.post("/api/upload-pdfs")
async def upload_and_process_pdfs(
    files: List[UploadFile] = File(...),
    course_title: str = Form(None),
    country: str = Form(None),
    priority: int = Form(5)
):
    """
    Upload PDF files and generate course content using Celery workers.
    Returns immediately with a task_id. Check status with /api/jobs/{task_id}
    
    **Expected Input (multipart/form-data):**
    ```
    files: [PDF file(s)]
    course_title: "Introduction to Python" (optional)
    country: "India" (optional)
    priority: 5 (optional, 1-10)
    ```
    
    **Expected Output:**
    ```json
    {
      "message": "PDF processing started",
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "task_id": "abc123-celery-task-id",
      "status": "pending",
      "status_url": "/api/jobs/abc123-celery-task-id"
    }
    ```
    """
    try:
        logging.info(f"Received {len(files)} PDF files for course: {course_title}")
        
        # Generate job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # Read and encode files as base64 (for Celery serialization)
        pdf_files_data = []
        for file in files:
            content = await file.read()
            pdf_files_data.append({
                'filename': file.filename,
                'content': base64.b64encode(content).decode('utf-8')
            })
        
        # Submit task to Celery
        task = process_pdf_and_generate_course.apply_async(
            args=[job_id, pdf_files_data, course_title, country],
            priority=priority,
            queue='pdf_processing'
        )
        
        logging.info(f"Created Celery task {task.id} for job {job_id}")
        
        return {
            "message": "PDF processing started",
            "job_id": job_id,
            "task_id": task.id,
            "status": "pending",
            "status_url": f"/api/jobs/{task.id}"
        }
        
    except Exception as e:
        logging.error(f"Error starting PDF processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/jobs/{task_id}",
    tags=["Course Management"],
    summary="Get Celery task status",
    description="""Get the current status and result of a Celery task.
    
**How It Works:**
1. Provide the `task_id` received from /api/upload-pdfs
2. Returns current task status and result (if complete)
3. Poll this endpoint to check processing progress

**Status Values:**
- 🔵 **PENDING**: Task waiting in queue
- 🟡 **STARTED**: Task is being processed
- 🟢 **SUCCESS**: Task completed successfully
- 🔴 **FAILURE**: Task failed with error
- 🟠 **RETRY**: Task is being retried

**Use Cases:**
- Track PDF processing progress
- Wait for course generation completion
- Handle errors gracefully
- Display progress to users

**Required:**
- `task_id`: Celery task ID (received from upload endpoint)
    """,
    responses={
        200: {
            "description": "Task status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "abc123-celery-task-id",
                        "status": "SUCCESS",
                        "result": {
                            "course_id": 123,
                            "message": "Course generated successfully"
                        },
                        "error": None
                    }
                }
            }
        },
        500: {"description": "Error retrieving task status", "model": ErrorResponse}
    }
)
async def get_job_status(task_id: str):
    try:
        # Get task result from Celery
        task_result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task_result.state,
        }
        
        if task_result.state == 'PENDING':
            response.update({
                "progress": 0,
                "message": "Task is waiting in queue..."
            })
        elif task_result.state == 'STARTED':
            # Get progress from task meta
            info = task_result.info or {}
            response.update({
                "progress": info.get('progress', 0),
                "message": info.get('message', 'Processing...')
            })
        elif task_result.state == 'SUCCESS':
            result = task_result.result
            response.update({
                "progress": 100,
                "message": "Task completed successfully",
                "result": result.get('result') if isinstance(result, dict) else result
            })
        elif task_result.state == 'FAILURE':
            response.update({
                "progress": 0,
                "message": "Task failed",
                "error": str(task_result.info)
            })
        elif task_result.state == 'RETRY':
            response.update({
                "progress": 0,
                "message": "Task is being retried..."
            })
        
        return response
        
    except Exception as e:
        logging.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/worker-stats",
    tags=["Course Management"],
    summary="Get Celery worker statistics",
    description="""Get real-time statistics about Celery workers and task queues.
    
**How It Works:**
1. Inspects all active Celery workers
2. Returns worker count, task counts, and queue status
3. Useful for monitoring system health

**Features:**
- 👷 **Worker Status**: See which workers are online
- 📊 **Task Metrics**: Active, scheduled, and reserved tasks
- 🔍 **Debugging**: Identify processing bottlenecks
- ⚡ **Real-time**: Current snapshot of worker state

**Use Cases:**
- Admin dashboard monitoring
- System health checks
- Debugging stuck tasks
- Load balancing decisions
    """,
    responses={
        200: {
            "description": "Worker statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "active_workers": {"worker1@hostname": []},
                        "scheduled_tasks": {},
                        "active_tasks": {},
                        "reserved_tasks": {}
                    }
                }
            }
        },
        500: {"description": "Error retrieving worker stats", "model": ErrorResponse}
    }
)
async def get_worker_stats():
    try:
        loop = asyncio.get_event_loop()
        
        # Celery inspector calls are synchronous Redis calls — run in executor
        def _inspect():
            inspector = celery_app.control.inspect()
            return {
                "active_workers": inspector.active(),
                "scheduled_tasks": inspector.scheduled(),
                "active_tasks": inspector.active(),
                "reserved_tasks": inspector.reserved(),
            }
        
        stats = await loop.run_in_executor(None, _inspect)
        return stats
    except Exception as e:
        logging.error(f"Error getting worker stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== COURSE CONTENT ENDPOINTS =====

@app.get(
    "/api/course/{course_id}",
    tags=["Courses"],
    summary="Get complete course content with modules and topics",
    description="""Retrieve full course structure including all modules, topics, and content.
    
**How It Works:**
1. Provide course_id (integer course_number or UUID)
2. Fetches complete course from database
3. Returns nested structure: Course → Modules → Topics
4. Falls back to JSON files if not in database

**Features:**
- 📚 **Complete Structure**: Full course hierarchy in one request
- 🔄 **Flexible ID**: Accepts integer course_number or UUID
- 💾 **Database First**: Queries PostgreSQL, JSON fallback
- 🎯 **Optimized**: Single query with joins for performance

**Use Cases:**
- Display full course content to students
- Generate quizzes from course material
- Export course data
- Teaching module navigation

**Required:**
- `course_id`: Course identifier (integer or UUID string)
  - Example: `2` or `550e8400-e29b-41d4-a716-446655440000`
    """,
    responses={
        200: {
            "description": "Course content retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 2,
                        "title": "Introduction to Python",
                        "description": "Learn Python programming",
                        "level": "Beginner",
                        "modules": [
                            {
                                "id": 10,
                                "week": 1,
                                "title": "Python Basics",
                                "description": "Introduction to Python syntax",
                                "topics": [
                                    {
                                        "id": 50,
                                        "title": "Variables and Data Types",
                                        "content": "...",
                                        "order_index": 1
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        },
        404: {"description": "Course not found", "model": ErrorResponse},
        500: {"description": "Server error", "model": ErrorResponse}
    }
)
async def get_course_content(course_id: str):
    try:
        # Try database first - use get_course_with_content for complete structure
        if database_service:
            logging.info(f"Fetching complete course content for {course_id} from database...")
            course = database_service.get_course_with_content(course_id)
            if course:
                logging.info(f"✅ Course {course_id} found with {len(course.get('modules', []))} modules")
                return course
            else:
                logging.warning(f"⚠️ Course {course_id} not found in database, trying JSON fallback...")
        
        # Fallback to JSON file
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        if isinstance(data, dict) and 'course_title' in data:
            # Single course format
            if str(data.get("course_id", 1)) == str(course_id):
                logging.info(f"✅ Course {course_id} found in JSON file")
                return data
            else:
                raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
        elif isinstance(data, list):
            # Multi-course format - find the specific course
            for course in data:
                if str(course.get("course_id", "")) == str(course_id):
                    logging.info(f"✅ Course {course_id} found in JSON file")
                    return course
            raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
        else:
            raise HTTPException(status_code=500, detail="Invalid course data format")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error loading course {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/courses",
    response_model=List[CourseItem],
    tags=["Courses"],
    summary="Get all courses",
    description="""Retrieve complete list of courses with all metadata.
    
**Returns:**
- Complete course catalog with all columns from database
- Includes: id, title, description, level, teacher_id, course_order, course_number, **country**, file_metadata, created_by, timestamps

**Use Cases:**
- Display course catalog in frontend
- Course selection dropdown
- Analytics and reporting

**Source:**
- Primary: PostgreSQL database (Neon)
- Fallback: JSON files (legacy support)

**Note:** The `country` field indicates where the course is offered/localized.
    """,
    responses={
        200: {"description": "List of courses retrieved successfully"}
    }
)
async def get_courses():
    """Get list of available courses from Neon database with all columns including country."""
    try:
        # Try database first (using V2 service which returns all columns)
        logging.info(f"Database service status: {'Available' if database_service else 'None'}")
        if database_service:
            logging.info("Fetching courses from Neon database...")
            courses = database_service.get_all_courses()
            if courses:
                logging.info(f"✅ Retrieved {len(courses)} courses from database")
                # DatabaseServiceV2 already returns all columns including country
                return courses
            else:
                logging.warning("⚠️ No courses found in database, trying JSON fallback...")
        
        # Fallback to JSON file (legacy support)
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'course_title' in data:
                logging.info("✅ Retrieved 1 course from JSON file")
                return [{
                    "course_id": data.get("course_id", 1),
                    "course_title": data.get("course_title", "Generated Course"),
                    "modules": len(data.get("modules", [])),
                    "country": None  # JSON doesn't have country field
                }]
            elif isinstance(data, list):
                logging.info(f"✅ Retrieved {len(data)} courses from JSON file")
                return [{
                    "course_id": course.get("course_id", i+1),
                    "course_title": course.get("course_title", f"Course {i+1}"),
                    "modules": len(course.get("modules", [])),
                    "country": None  # JSON doesn't have country field
                } for i, course in enumerate(data)]
        
        logging.warning("⚠️ No courses found in database or JSON file")
        return []
    except Exception as e:
        logging.error(f"Error loading courses: {e}")
        return []


# ===== QUIZ ENDPOINTS =====

@app.post(
    "/api/quiz/generate-module",
    tags=["Quiz"],
    summary="Generate 20-question module quiz",
    description="""Generate a 20-question MCQ quiz for a specific course module using AI.
    
**How It Works:**
1. Provide course_id and module_week number
2. Fetches module content from database
3. LLM generates 20 diverse MCQ questions
4. Quiz saved to database with correct answers
5. Returns quiz without answers for student display

**Features:**
- 🤖 **AI-Generated**: Questions created by LLM based on content
- 📝 **20 Questions**: Comprehensive module coverage
- 💾 **Database Storage**: Quiz saved in `quizzes` and `quiz_questions` tables
- 🎯 **Module-Specific**: Focused on single week's content
- ✅ **Immediate Use**: Quiz ready for students right away

**Use Cases:**
- Weekly module assessments
- Self-study practice quizzes
- Progress tracking per module
- Formative assessment

**Required:**
- `quiz_type`: "OBJECTIVE" (MCQ format)
- `course_id`: Course identifier (integer or UUID)
- `module_week`: Module/week number (integer)
    """,
    responses={
        200: {
            "description": "Module quiz generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Module quiz generated successfully",
                        "quiz": {
                            "quiz_id": "module_3_abc123",
                            "title": "Module 3 Quiz: Advanced Topics",
                            "total_questions": 20,
                            "quiz_type": "module"
                        }
                    }
                }
            }
        },
        404: {"description": "Course or module not found", "model": ErrorResponse},
        503: {"description": "Quiz service not available", "model": ErrorResponse}
    }
)
async def generate_module_quiz(request: QuizRequest):
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        # Load course content from database first
        course_content = None
        
        if database_service:
            # Fetch complete course with modules and topics
            logging.info(f"Fetching complete course content for {request.course_id} from database for quiz generation...")
            course_content = database_service.get_course_with_content(request.course_id)
            if course_content:
                logging.info(f"✅ Course {request.course_id} found with {len(course_content.get('modules', []))} modules")
        
        # Fallback to JSON file
        if not course_content:
            logging.warning(f"⚠️ Course {request.course_id} not in database, trying JSON fallback...")
            if not os.path.exists(config.OUTPUT_JSON_PATH):
                raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
            
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                if str(data.get("course_id", 1)) == str(request.course_id):
                    course_content = data
            elif isinstance(data, list):
                for course in data:
                    if str(course.get("course_id", "")) == str(request.course_id):
                        course_content = course
                        break
        
        if not course_content:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
        
        logging.info(f"Generating module quiz for week {request.module_week}")
        quiz = await quiz_service.generate_module_quiz(request.module_week, course_content)
        
        quiz_display = quiz_service.get_quiz_without_answers(quiz.quiz_id)
        if not quiz_display:
            raise HTTPException(status_code=500, detail="Failed to prepare quiz for display")
        
        return {
            "message": "Module quiz generated successfully",
            "quiz": quiz_display.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating module quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/quiz/generate-course",
    tags=["Quiz"],
    summary="Generate 40-question comprehensive course quiz",
    description="""Generate a 40-question MCQ quiz covering the entire course content using AI.
    
**How It Works:**
1. Provide course_id
2. Fetches ALL modules and topics from database
3. LLM generates 40 questions distributed across all modules
4. Quiz saved to database with correct answers
5. Returns quiz without answers for student display

**Features:**
- 🤖 **AI-Generated**: Questions created by LLM from full course
- 📝 **40 Questions**: Comprehensive course coverage
- 💾 **Database Storage**: Quiz saved in `quizzes` and `quiz_questions` tables
- 🎯 **Balanced**: Questions distributed across all modules
- 🏆 **Final Assessment**: Suitable for course completion test

**Use Cases:**
- Final course examination
- Certification assessment
- Course completion test
- Comprehensive knowledge check

**Required:**
- `quiz_type`: "OBJECTIVE" (MCQ format)
- `course_id`: Course identifier (integer or UUID)
    """,
    responses={
        200: {
            "description": "Course quiz generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Course quiz generated successfully",
                        "quiz": {
                            "quiz_id": "course_xyz789",
                            "title": "Final Course Quiz: Introduction to Python",
                            "total_questions": 40,
                            "quiz_type": "course"
                        }
                    }
                }
            }
        },
        404: {"description": "Course not found", "model": ErrorResponse},
        503: {"description": "Quiz service not available", "model": ErrorResponse}
    }
)
async def generate_course_quiz(request: QuizRequest):
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        # Load course content from database first
        course_content = None
        
        if database_service:
            # Fetch complete course with modules and topics
            logging.info(f"Fetching complete course content for {request.course_id} from database for course quiz generation...")
            course_content = database_service.get_course_with_content(request.course_id)
            if course_content:
                logging.info(f"✅ Course {request.course_id} found with {len(course_content.get('modules', []))} modules")
        
        # Fallback to JSON file
        if not course_content:
            logging.warning(f"⚠️ Course {request.course_id} not in database, trying JSON fallback...")
            if not os.path.exists(config.OUTPUT_JSON_PATH):
                raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
            
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'course_title' in data:
                if str(data.get("course_id", 1)) == str(request.course_id):
                    course_content = data
            elif isinstance(data, list):
                for course in data:
                    if str(course.get("course_id", "")) == str(request.course_id):
                        course_content = course
                        break
        
        if not course_content:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
        
        logging.info(f"Generating comprehensive course quiz")
        quiz = await quiz_service.generate_course_quiz(course_content)
        
        quiz_display = quiz_service.get_quiz_without_answers(quiz.quiz_id)
        if not quiz_display:
            raise HTTPException(status_code=500, detail="Failed to prepare quiz for display")
        
        return {
            "message": "Course quiz generated successfully",
            "quiz": quiz_display.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating course quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quiz/submit")
async def submit_quiz(submission: QuizSubmission):
    """
    Submit quiz answers and get evaluation results.
    
    **Expected Input (JSON):**
    ```json
    {
      "quiz_id": "module_3_abc123",
      "user_id": 1,
      "answers": {
        "module_3_abc123_q1": "A",
        "module_3_abc123_q2": "B",
        "module_3_abc123_q3": "C"
      }
    }
    ```
    
    **Expected Output:**
    ```json
    {
      "message": "Quiz evaluated successfully",
      "result": {
        "quiz_id": "module_3_abc123",
        "user_id": 1,
        "score": 18,
        "total_questions": 20,
        "percentage": 90.0,
        "passed": true,
        "detailed_results": [
          {
            "question_id": "module_3_abc123_q1",
            "user_answer": "A",
            "correct_answer": "A",
            "is_correct": true
          }
        ]
      }
    }
    ```
    """
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        logging.info(f"Processing quiz submission for quiz {submission.quiz_id}")
        result = quiz_service.evaluate_quiz(submission)
        
        return {
            "message": "Quiz evaluated successfully",
            "result": result.model_dump()
        }
    except ValueError as ve:
        logging.error(f"Validation error in quiz submission: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"Error evaluating quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/quiz/{quiz_id}",
    tags=["Quiz"],
    summary="Get quiz for display (without answers)",
    description="""Retrieve a specific quiz with all questions but WITHOUT correct answers for student display.
    
**How It Works:**
1. Provide quiz_id in URL
2. System fetches quiz from database
3. Returns quiz with questions and options
4. Correct answers are EXCLUDED for security
5. Student can view and take the quiz

**Features:**
- 🔒 **Secure**: Correct answers never exposed to frontend
- 📝 **Complete Questions**: All questions with options included
- 💾 **Database Source**: Fetched from `quizzes` and `quiz_questions` tables
- ⚡ **Fast**: Single query with joins

**Use Cases:**
- Display quiz to students for taking
- Preview quiz structure
- Load quiz into frontend application
- Show quiz metadata

**Required:**
- `quiz_id`: Quiz identifier (string)
  - Example: `module_3_abc123` or `course_xyz789`

**Security Note:**
Correct answers are stored separately and only accessed during evaluation.
    """,
    responses={
        200: {
            "description": "Quiz retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "quiz": {
                            "quiz_id": "module_3_abc123",
                            "title": "Module 3 Quiz",
                            "total_questions": 20,
                            "quiz_type": "module"
                        }
                    }
                }
            }
        },
        404: {"description": "Quiz not found", "model": ErrorResponse},
        503: {"description": "Quiz service not available", "model": ErrorResponse}
    }
)
async def get_quiz(quiz_id: str):
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        quiz = quiz_service.get_quiz_without_answers(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
        
        return {"quiz": quiz.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving quiz {quiz_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== CHAT & COMMUNICATION ENDPOINTS =====

@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Text chat with AI assistant",
    description="""Send a text message to the AI assistant and get a response with conversation context.
    
**How It Works:**
1. Provide `user_id` and `message`
2. Backend automatically manages session (creates if doesn't exist)
3. Retrieves last 10 conversation turns from database
4. Sends query + history to AI with semantic routing
5. Saves both user message and AI response to database
6. Returns AI response with session_id

**Features:**
- 🧠 **Intelligent Routing**: Automatically detects intent (greeting, general question, course-related)
- 📚 **RAG Integration**: Retrieves relevant course content for accurate answers
- 💾 **Persistent Memory**: Full conversation history stored in database
- ⚡ **Redis Cache**: Fast access to recent messages

**Required:**
- `user_id`: User ID (must be valid user in database)
- `message`: User's question or message

**Optional:**
- `course_id`: Filter RAG retrieval to specific course (e.g., 1, 2, 3)
- `language`: Language code for response (default: en-IN)
- `ip_address`: Client IP for analytics
- `user_agent`: Browser info for session tracking

**Example with course filtering:**
```json
{
    "user_id": 16,
    "message": "What is machine learning?",
    "course_id": 3
}
```
    """,
    responses={
        200: {"description": "AI response generated successfully"},
        400: {"description": "Missing required fields", "model": ErrorResponse},
        503: {"description": "Chat service not available", "model": ErrorResponse}
    }
)
async def chat_endpoint(request: ChatRequest):
    """Text-only chat endpoint with database-backed conversation history."""
    if not SERVICES_AVAILABLE or not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        loop = asyncio.get_event_loop()
        
        # Get or create session for user (sync DB call → executor)
        session = await loop.run_in_executor(None, lambda: session_manager.get_or_create_session(
            user_id=request.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent
        ))
        session_id = session['session_id']
        
        logging.info(f"Chat query: {request.message[:50]}... (user: {request.user_id}, session: {session_id})")
        
        # Get conversation history from database (sync → executor)
        conversation_history = await loop.run_in_executor(
            None, lambda: session_manager.get_conversation_history(session_id, limit=5)
        )
        
        # Get response from chat service (with optional course_id filtering)
        response_data = await chat_service.ask_question(
            request.message, 
            request.language, 
            session_id, 
            conversation_history,
            course_id=request.course_id
        )
        
        # Save user message and assistant response to database (sync → executor)
        _uid, _sid, _msg = request.user_id, session_id, request.message
        _answer = response_data.get('answer', '')
        _meta = {
            'route': response_data.get('route'),
            'confidence': response_data.get('confidence'),
            'sources': response_data.get('sources')
        }
        await loop.run_in_executor(None, lambda: session_manager.add_message(
            user_id=_uid, session_id=_sid, role='user',
            content=_msg, message_type='text'
        ))
        await loop.run_in_executor(None, lambda: session_manager.add_message(
            user_id=_uid, session_id=_sid, role='assistant',
            content=_answer, message_type='text', metadata=_meta
        ))
        
        # Add session_id to response
        response_data['session_id'] = session_id
        response_data['user_id'] = request.user_id
        
        return response_data
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/chat-with-audio",
    response_model=ChatWithAudioResponse,
    tags=["Chat"],
    summary="Chat with AI assistant + audio response",
    description="""Send a message and receive both text and audio response.
    
**How It Works:**
1. Same as /api/chat but also generates audio
2. Uses Text-to-Speech (TTS) to convert AI response to audio
3. Returns base64-encoded audio along with text

**Features:**
- All features from /api/chat endpoint
- 🔊 **Multi-language TTS**: Supports multiple languages (en-IN, hi-IN, etc.)
- 🎵 **High-quality audio**: Uses ElevenLabs or Deepgram for natural voices
- 📦 **Base64 encoded**: Ready for direct playback in browser

**Use Cases:**
- Mobile apps with voice interaction
- Accessibility features for visually impaired users
- Language learning with pronunciation

**Required:**
- `user_id`: User ID
- `message`: User's question or message

**Optional:**
- `course_id`: Filter RAG retrieval to specific course (e.g., 1, 2, 3)
- `language`: Language code for both text and audio (default: en-IN)

**Example with course filtering:**
```json
{
    "user_id": 16,
    "message": "Explain neural networks",
    "course_id": 3,
    "language": "en-IN"
}
```
    """,
    responses={
        200: {"description": "AI response with audio generated successfully"},
        400: {"description": "Missing required fields", "model": ErrorResponse},
        503: {"description": "Service not available", "model": ErrorResponse}
    }
)
async def chat_with_audio_endpoint(request: ChatWithAudioRequest):
    """Chat endpoint with audio generation and database-backed conversation history."""
    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
        raise HTTPException(status_code=503, detail="Chat or audio service not available")
    
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        loop = asyncio.get_event_loop()
        
        # Get or create session for user (sync DB call → executor)
        session = await loop.run_in_executor(None, lambda: session_manager.get_or_create_session(
            user_id=request.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent
        ))
        session_id = session['session_id']
        
        logging.info(f"Chat with audio query: {request.message[:50]}... (user: {request.user_id}, session: {session_id})")
        
        # Get conversation history from database (sync → executor)
        conversation_history = await loop.run_in_executor(
            None, lambda: session_manager.get_conversation_history(session_id, limit=5)
        )
        
        # Get text response with conversation context (with optional course_id filtering)
        response_data = await chat_service.ask_question(
            request.message, 
            request.language, 
            session_id, 
            conversation_history,
            course_id=request.course_id
        )
        answer_text = response_data.get('answer', '')
        
        # Generate audio
        audio_buffer = await audio_service.generate_audio_from_text(answer_text, request.language)
        audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
        
        # Save user message and assistant response to database (sync → executor)
        _uid, _sid, _msg = request.user_id, session_id, request.message
        _meta = {
            'route': response_data.get('route'),
            'confidence': response_data.get('confidence'),
            'has_audio': True
        }
        await loop.run_in_executor(None, lambda: session_manager.add_message(
            user_id=_uid, session_id=_sid, role='user',
            content=_msg, message_type='voice'
        ))
        await loop.run_in_executor(None, lambda: session_manager.add_message(
            user_id=_uid, session_id=_sid, role='assistant',
            content=answer_text, message_type='voice', metadata=_meta
        ))
        
        response = {
            "answer": answer_text,
            "audio_data": audio_base64,
            "session_id": session_id,
            "user_id": request.user_id,
            "metadata": response_data
        }
        
        return response
    except Exception as e:
        logging.error(f"Error in chat with audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/chat-with-audio-stream",
    tags=["Chat"],
    summary="Chat with streaming audio response (optimized)",
    description="""Send a message and receive text + streaming audio response.
    
**Performance Benefits:**
- ⚡ **No base64 overhead**: Streams raw audio bytes (-33% size)
- 🚀 **Instant playback**: Audio starts playing immediately as chunks arrive
- 📦 **Smaller payload**: Raw binary instead of base64-encoded JSON

**How It Works:**
1. Get chat response (text)
2. Return text immediately in JSON
3. Generate audio and stream chunks as they're created
4. Frontend plays audio chunks progressively

**Use Cases:**
- Low-latency voice responses
- Mobile apps with limited bandwidth
- Real-time conversation

**Required:**
- `user_id`: User ID
- `message`: User's question or message

**Optional:**
- `course_id`: Filter RAG retrieval to specific course (e.g., 1, 2, 3)
- `language`: Language code for both text and audio (default: en-IN)

**Example with course filtering:**
```json
{
    "user_id": 16,
    "message": "What are the main concepts in this module?",
    "course_id": 5,
    "language": "en-IN"
}
```
    """,
    responses={
        200: {
            "description": "Streaming audio response",
            "content": {"audio/mpeg": {}}
        }
    }
)
async def chat_with_audio_stream_endpoint(request: ChatWithAudioRequest):
    """Chat endpoint with streaming audio - no base64, direct binary stream."""
    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
        raise HTTPException(status_code=503, detail="Chat or audio service not available")
    
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        loop = asyncio.get_event_loop()
        
        # Get or create session (sync DB call → executor)
        session = await loop.run_in_executor(None, lambda: session_manager.get_or_create_session(
            user_id=request.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent
        ))
        session_id = session['session_id']
        
        logging.info(f"Chat stream query: {request.message[:50]}... (user: {request.user_id})")
        
        # Get conversation history (sync → executor)
        conversation_history = await loop.run_in_executor(
            None, lambda: session_manager.get_conversation_history(session_id, limit=5)
        )
        
        # Get text response (with optional course_id filtering)
        response_data = await chat_service.ask_question(
            request.message, 
            request.language, 
            session_id, 
            conversation_history,
            course_id=request.course_id
        )
        answer_text = response_data.get('answer', '')
        
        # Save messages to DB (sync → executor)
        _uid, _sid, _msg = request.user_id, session_id, request.message
        _meta = {
            'route': response_data.get('route'),
            'confidence': response_data.get('confidence'),
            'has_audio': True,
            'streaming': True
        }
        await loop.run_in_executor(None, lambda: session_manager.add_message(
            user_id=_uid, session_id=_sid, role='user',
            content=_msg, message_type='voice'
        ))
        await loop.run_in_executor(None, lambda: session_manager.add_message(
            user_id=_uid, session_id=_sid, role='assistant',
            content=answer_text, message_type='voice', metadata=_meta
        ))
        
        # Stream audio chunks directly
        async def audio_generator():
            # First, send metadata as JSON header (small)
            metadata = {
                "answer": answer_text,
                "session_id": session_id,
                "user_id": request.user_id,
                "metadata": response_data
            }
            # Send JSON metadata followed by newline separator
            yield (json.dumps(metadata) + "\n---AUDIO_START---\n").encode('utf-8')
            
            # Then stream raw audio chunks
            async for chunk in audio_service.stream_audio_from_text(answer_text, request.language):
                yield chunk
        
        return StreamingResponse(
            audio_generator(),
            media_type="application/octet-stream",
            headers={
                "X-Session-ID": session_id,
                "X-Answer-Length": str(len(answer_text)),
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logging.error(f"Error in streaming chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/transcribe",
    tags=["Audio"],
    summary="Transcribe audio to text",
    description="""Convert audio file to text using speech-to-text AI.
    
**How It Works:**
1. Upload audio file (WAV, MP3, WebM, etc.)
2. Specify language code (e.g., en-IN, hi-IN)
3. AI transcribes audio to text
4. Returns transcript immediately

**Features:**
- 🎤 **Multi-format**: Supports WAV, MP3, WebM, OGG, etc.
- 🌍 **Multi-language**: Supports multiple language codes
- ⚡ **Fast**: Near real-time transcription
- 🎯 **Accurate**: High-quality speech recognition

**Supported Languages:**
- `en-IN`: English (India)
- `hi-IN`: Hindi
- `en-US`: English (US)
- And more...

**Use Cases:**
- Voice input for chat
- Audio note transcription
- Accessibility features
- Voice commands

**Required:**
- `audio_file`: Audio file (multipart/form-data)

**Optional:**
- `language`: Language code (default: "en-IN")
    """,
    responses={
        200: {
            "description": "Audio transcribed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "transcript": "Hello, how can I help you today?",
                        "language": "en-IN"
                    }
                }
            }
        },
        503: {"description": "Audio service not available", "model": ErrorResponse}
    }
)
async def transcribe_endpoint(language: str = Form("en-IN"), audio_file: UploadFile = File(...)):
    """Audio transcription for voice input."""
    if not SERVICES_AVAILABLE or not audio_service:
        raise HTTPException(status_code=503, detail="Audio service not available")
    
    try:
        logging.info(f"Transcribing audio file: {audio_file.filename}")
        audio_data = await audio_file.read()
        
        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name
        
        try:
            text = await audio_service.transcribe_audio(temp_path, language)
            return {"transcription": text}
        finally:
            os.unlink(temp_path)
            
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== CLASS TEACHING ENDPOINTS =====

@app.post(
    "/api/start-class",
    tags=["Teaching"],
    summary="Start interactive class session with audio",
    description="""Start a class teaching session with content delivery and audio narration.
    
**How It Works:**
1. Provide course_id, module_index, and sub_topic_index
2. System fetches topic content from database
3. Generates audio narration for content
4. Returns content preview, full content, and audio URL
5. Provides next topic information for navigation

**Features:**
- 🎓 **Interactive Teaching**: Step-by-step content delivery
- 🔊 **Audio Narration**: AI-generated voice for each topic
- 📚 **Content Preview**: Summary before full content
- ➡️ **Smart Navigation**: Automatic next topic suggestion
- 🌍 **Multi-language**: Supports multiple languages

**Audio Generation:**
- Uses text-to-speech AI
- Saved as MP3 files
- Accessible via static URL
- Cached for performance

**Use Cases:**
- Virtual classroom teaching
- Self-paced learning
- Audio learning mode
- Accessibility features

**Required:**
- `course_id`: Course identifier (integer or UUID)
- `module_index`: Module index (integer, 0-indexed)
- `sub_topic_index`: Topic index within module (integer, 0-indexed)

**Optional:**
- `language`: Language code for audio (default: "en-IN")
- `content_only`: Skip audio generation (default: false)
    """,
    responses={
        200: {
            "description": "Class session started successfully",
            "content": {
                "application/json": {
                    "example": {
                        "module_title": "Python Basics",
                        "topic_title": "Variables and Data Types",
                        "content_preview": "In this topic, we'll learn about...",
                        "audio_url": "/static/audio/class_session_abc123.mp3",
                        "full_content": "Complete topic content here..."
                    }
                }
            }
        },
        404: {"description": "Course or topic not found", "model": ErrorResponse},
        503: {"description": "Required services not available", "model": ErrorResponse}
    }
)
async def start_class_endpoint(request: dict):
    if not SERVICES_AVAILABLE or not teaching_service or not audio_service:
        raise HTTPException(status_code=503, detail="Required services not available")
    
    try:
        course_id = request.get("course_id")
        module_index = request.get("module_index", 0)
        sub_topic_index = request.get("sub_topic_index", 0)
        language = request.get("language", "en-IN")
        content_only = request.get("content_only", False)
        
        logging.info(f"Starting class for course: {course_id}, module: {module_index}, topic: {sub_topic_index}")
        
        # Try database first
        course_data = None
        if database_service:
            try:
                course_num = int(course_id)
                logging.info(f"Fetching course by course_number {course_num} from database...")
                course_data = database_service.get_course_by_number(course_num)
            except ValueError:
                logging.info(f"Fetching course by UUID {course_id} from database...")
                course_data = database_service.get_course(course_id)
        
        # Fallback to JSON file
        if not course_data:
            if not os.path.exists(config.OUTPUT_JSON_PATH):
                raise HTTPException(status_code=404, detail="Course content not found")
            
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                course_data = data
            elif isinstance(data, list):
                for course in data:
                    if str(course.get("course_id", "")) == str(course_id):
                        course_data = course
                        break
                if not course_data:
                    course_data = data[0] if data else None
        
        if not course_data:
            raise HTTPException(status_code=404, detail="Course content not found")
        
        # Validate indices
        if module_index >= len(course_data.get("modules", [])):
            raise HTTPException(status_code=400, detail="Module not found")
            
        module = course_data["modules"][module_index]
        
        if sub_topic_index >= len(module.get("sub_topics", [])):
            raise HTTPException(status_code=400, detail="Sub-topic not found")
            
        sub_topic = module["sub_topics"][sub_topic_index]
        
        # Generate teaching content
        raw_content = sub_topic.get('content', '')
        if not raw_content:
            raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
        
        try:
            teaching_content = await teaching_service.generate_teaching_content(
                module_title=module['title'],
                sub_topic_title=sub_topic['title'],
                raw_content=raw_content,
                language=language
            )
            
            if not teaching_content or len(teaching_content.strip()) == 0:
                raise Exception("Empty teaching content generated")
                
        except Exception as e:
            logging.error(f"Error generating teaching content: {e}")
            teaching_content = f"Welcome to the lesson on {sub_topic['title']}. {raw_content[:500]}..."
        
        logging.info(f"Generated teaching content: {len(teaching_content)} characters")
        
        # If only content preview is requested, return it
        if content_only:
            return {
                "content_preview": teaching_content[:400] + "..." if len(teaching_content) > 400 else teaching_content,
                "full_content_length": len(teaching_content),
                "module_title": module['title'],
                "sub_topic_title": sub_topic['title']
            }
        
        # Generate audio
        logging.info("Generating audio for teaching content...")
        audio_buffer = await audio_service.generate_audio_from_text(teaching_content, language)
        
        if not audio_buffer.getbuffer().nbytes:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        logging.info(f"Audio generated: {audio_buffer.getbuffer().nbytes} bytes")
        return StreamingResponse(audio_buffer, media_type="audio/mpeg")
        
    except Exception as e:
        logging.error(f"Error starting class: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== SESSION MANAGEMENT APIS =====

@app.get(
    "/api/session/check",
    response_model=SessionCheckResponse,
    tags=["Session Management"],
    summary="Check if user has active session",
    description="""Check if a specific user has an active session.
    
**Use Case:** Before starting a new conversation, check if the user already has an active session to resume.

**Returns:**
- `has_session`: True if user has active session, False otherwise
- `session_id`: UUID of the active session (if exists)
- `message_count`: Number of messages in the session
- `last_activity`: Timestamp of last activity
- `started_at`: When the session was created
    """,
    responses={
        200: {"description": "Session status retrieved successfully"},
        503: {"description": "Session manager not available", "model": ErrorResponse}
    }
)
async def check_session(user_id: int):
    """Check if a user has an active session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        session = session_manager.get_session(user_id)
        
        if session:
            return {
                "has_session": True,
                "session_id": session['session_id'],
                "message_count": session.get('message_count', 0),
                "last_activity": session.get('last_activity_at'),
                "started_at": session.get('started_at')
            }
        else:
            return {
                "has_session": False,
                "message": "No active session found for this user"
            }
    except Exception as e:
        logging.error(f"Error checking session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/session/create",
    response_model=SessionCreateResponse,
    tags=["Session Management"],
    summary="Create new user session",
    description="""Create a new session for a user or return existing active session.
    
**Use Case:** Explicitly create a session before starting conversation (optional, as chat endpoints auto-create).

**Note:** If user already has an active session, that session will be returned instead of creating a new one.

**Parameters:**
- `user_id` (required): User ID to create session for
- `ip_address` (optional): Client IP for analytics
- `user_agent` (optional): Browser/device info
- `device_type` (optional): mobile, desktop, tablet
    """,
    responses={
        200: {"description": "Session created or existing session returned"},
        400: {"description": "Missing required user_id", "model": ErrorResponse},
        503: {"description": "Session manager not available", "model": ErrorResponse}
    }
)
async def create_session(request: SessionCreateRequest):
    """Create a new session for a user."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        session = session_manager.get_or_create_session(
            user_id=request.user_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            device_type=request.device_type
        )
        
        return {
            "session_id": session['session_id'],
            "user_id": request.user_id,
            "started_at": session.get('started_at'),
            "message": "Session created successfully"
        }
    except Exception as e:
        logging.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/session/end",
    response_model=SessionEndResponse,
    tags=["Session Management"],
    summary="End user session",
    description="""End an active session and clear cached conversation history.
    
**Use Case:** When user logs out or explicitly wants to end the conversation.

**Effect:**
- Session marked as inactive in database
- Conversation history cleared from Redis cache
- Session can no longer be resumed

**Note:** Messages are still preserved in database for analytics.
    """,
    responses={
        200: {"description": "Session ended successfully"},
        400: {"description": "Missing required session_id", "model": ErrorResponse},
        503: {"description": "Session manager not available", "model": ErrorResponse}
    }
)
async def end_session(request: SessionEndRequest):
    """End a user's session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        session_manager.end_session(request.session_id)
        
        return {
            "session_id": request.session_id,
            "message": "Session ended successfully"
        }
    except Exception as e:
        logging.error(f"Error ending session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/session/history",
    response_model=SessionHistoryResponse,
    tags=["Session Management"],
    summary="Get conversation history",
    description="""Retrieve conversation history for a specific session.
    
**Use Case:** Display past conversation when user returns or for analytics.

**Storage:**
- First checks Redis cache (fast, last 50 messages, 24h TTL)
- Falls back to PostgreSQL if not in cache
- Returns messages in chronological order (oldest first)

**Parameters:**
- `session_id` (required): Session UUID to retrieve history for
- `limit` (optional, default=20): Maximum number of messages to return

**Returns:** List of messages with role (user/assistant), content, timestamps, and metadata.
    """,
    responses={
        200: {"description": "Conversation history retrieved successfully"},
        503: {"description": "Session manager not available", "model": ErrorResponse}
    }
)
async def get_session_history(session_id: str, limit: int = 20):
    """Get conversation history for a session."""
    if not session_manager:
        raise HTTPException(status_code=503, detail="Session manager not available")
    
    try:
        messages = session_manager.get_messages(session_id, limit=limit)
        
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "messages": messages
        }
    except Exception as e:
        logging.error(f"Error fetching session history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== ADMIN DASHBOARD API =====

@app.get(
    "/api/admin/user/{user_id}/quiz-stats",
    tags=["Admin"],
    summary="Get user quiz statistics (Admin)",
    description="""Retrieve comprehensive quiz statistics and history for a specific user.
    
**How It Works:**
1. Provide user_id in URL
2. System queries `quiz_responses` table
3. Aggregates statistics: attempts, average score, best score, pass count
4. Returns last 5 quiz attempts with details

**Features:**
- 📊 **Aggregate Stats**: Total attempts, averages, best scores
- 📈 **Progress Tracking**: Pass/fail counts
- 🕐 **Recent History**: Last 5 attempts with full details
- 🎯 **Performance Metrics**: Average score calculation

**Statistics Included:**
- `total_attempts`: Total number of quizzes taken
- `avg_score`: Average score across all attempts
- `best_score`: Highest score achieved
- `passed_count`: Number of quizzes passed (≥60%)

**Use Cases:**
- Admin dashboard user analytics
- Student progress monitoring
- Performance evaluation
- Identify struggling students

**Required:**
- `user_id`: Student user ID (integer)

**⚠️ Admin Only:**
This endpoint should be protected with admin authentication in production.
    """,
    responses={
        200: {
            "description": "User quiz statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": 1,
                        "quiz_statistics": {
                            "total_attempts": 15,
                            "avg_score": 17.5,
                            "best_score": 20,
                            "passed_count": 12
                        },
                        "recent_attempts": [
                            {
                                "id": 45,
                                "quiz_id": "module_3_abc123",
                                "score": 18,
                                "total_questions": 20,
                                "submitted_at": "2026-01-08T10:30:00Z"
                            }
                        ]
                    }
                }
            }
        },
        503: {"description": "Database service unavailable", "model": ErrorResponse}
    }
)
async def get_user_quiz_statistics(user_id: int):
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service unavailable")
    
    try:
        stats = database_service.get_user_quiz_stats(user_id)
        
        # Also get recent quiz attempts
        recent_attempts = database_service.get_user_quiz_responses(user_id)[:5]  # Last 5 attempts
        
        return {
            "user_id": user_id,
            "quiz_statistics": stats,
            "recent_attempts": recent_attempts
        }
    except Exception as e:
        logging.error(f"Error fetching quiz stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/admin/users",
    tags=["Admin"],
    summary="Get all users with detailed information",
    description="""Retrieve list of all users with complete profile information and filtering options.
    
**How It Works:**
1. Optional filters: role, is_active
2. Pagination support: limit and offset
3. Returns detailed user profiles
4. Sorted by creation date (newest first)

**Features:**
- 👥 **Complete Profiles**: All user fields including education, institution, experience
- 🔍 **Filtering**: Filter by role (student/teacher/admin) or active status
- 📄 **Pagination**: Control result size with limit/offset
- 📊 **Rich Data**: Student type, college, degree, school info, institution details

**User Fields Returned:**
- Basic: id, username, email, role
- Student Info: student_type, college_name, degree, school_class, school_affiliation
- Teacher Info: institution, subject, experience
- Status: terms_accepted, email_verified, is_active
- Timestamps: last_login_at, created_at, updated_at

**Use Cases:**
- Admin user management interface
- Export user data
- User analytics and reporting
- Filter users by role or status

**Query Parameters:**
- `role` (optional): Filter by role (student, teacher, admin)
- `is_active` (optional): Filter by active status (true/false)
- `limit` (optional, default=100): Max results to return
- `offset` (optional, default=0): Pagination offset

**⚠️ Admin Only:** This endpoint should be protected with admin authentication.
    """,
    responses={
        200: {
            "description": "Users retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_count": 78,
                        "users": [
                            {
                                "id": 79,
                                "username": "John Doe",
                                "email": "john@example.com",
                                "role": "teacher",
                                "institution": "ABC School",
                                "subject": "Mathematics",
                                "experience": "5 years",
                                "created_at": "2026-01-06T09:49:16.511237+00:00"
                            }
                        ]
                    }
                }
            }
        },
        503: {"description": "Database service unavailable", "model": ErrorResponse}
    }
)
async def get_all_users(
    role: Optional[str] = None, 
    is_active: Optional[bool] = None, 
    limit: int = 100, 
    offset: int = 0
):
    """Get all users with optional filtering"""
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service unavailable")
    
    try:
        users = database_service.get_all_users(
            role=role, 
            is_active=is_active, 
            limit=limit, 
            offset=offset
        )
        
        # Get total count for pagination using safe execute_query
        count_query = "SELECT COUNT(*) as count FROM users WHERE 1=1"
        count_params = []
        
        if role:
            count_query += " AND role = %s"
            count_params.append(role)
        
        if is_active is not None:
            count_query += " AND is_active = %s"
            count_params.append(is_active)
        
        count_result = database_service.execute_query(
            count_query, tuple(count_params) if count_params else None, fetch='one'
        )
        total_count = count_result['count'] if count_result else 0
        
        return {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "users": users
        }
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/admin/users/{user_id}",
    tags=["Admin"],
    summary="Get detailed user information by ID",
    description="""Retrieve complete profile information for a specific user.
    
**Returns all user fields:**
- Personal: username, email
- Role and permissions: role, is_active, email_verified
- Education (students): student_type, college_name, degree, school_class, school_affiliation
- Professional (teachers): institution, subject, experience
- Activity: last_login_at, created_at, updated_at
- Terms: terms_accepted

**Use Cases:**
- User profile view in admin panel
- User verification and moderation
- Support ticket investigation
- User data export

**⚠️ Admin Only:** This endpoint should be protected with admin authentication.
    """,
    responses={
        200: {
            "description": "User details retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 79,
                        "username": "John Doe",
                        "email": "john@example.com",
                        "role": "teacher",
                        "institution": "ABC School",
                        "subject": "Mathematics",
                        "experience": "5 years",
                        "is_active": True,
                        "email_verified": True,
                        "created_at": "2026-01-06T09:49:16.511237+00:00"
                    }
                }
            }
        },
        404: {"description": "User not found", "model": ErrorResponse},
        503: {"description": "Database service unavailable", "model": ErrorResponse}
    }
)
async def get_user_details(user_id: int):
    """Get detailed user information by ID"""
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service unavailable")
    
    try:
        user = database_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/admin/dashboard",
    response_model=AdminDashboardResponse,
    tags=["Admin"],
    summary="Get admin dashboard statistics",
    description="""Retrieve comprehensive statistics for the admin dashboard.
    
**⚠️ Authentication Required:** This endpoint should be protected with admin authentication in production.

**Statistics Included:**

**User Metrics:**
- Total users count
- Users breakdown by role (student, teacher, admin)
- Recently registered users (last 10)

**Course Metrics:**
- Total courses count
- Course list with enrollment statistics
- Paid vs free enrollments per course

**Session Metrics:**
- Active sessions in last 24 hours
- Session activity over last 7 days
- Unique users per day

**Financial Metrics:**
- Total purchases count
- Total revenue
- Paid enrollments vs free

**Engagement Metrics:**
- Total messages sent across all sessions
- Total enrollments

**Use Cases:**
- Admin dashboard display
- Business intelligence reporting
- User engagement analysis
- Revenue tracking

**Performance:** This endpoint aggregates data from multiple tables. Response time may vary with data volume.
    """,
    responses={
        200: {"description": "Dashboard statistics retrieved successfully"},
        503: {"description": "Database service not available", "model": ErrorResponse}
    }
)
async def admin_dashboard():
    """Get comprehensive statistics for admin dashboard."""
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        stats = database_service.get_dashboard_stats()
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "data": stats
        }
    except Exception as e:
        logging.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/",
    tags=["Health"],
    summary="Root health check",
    description="""Simple health check endpoint to verify API is running.
    
**Returns:**
- Service status (running/degraded/down)
- API version
- Brief status message
    """,
    responses={
        200: {"description": "Service is healthy and running"}
    }
)
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "version": "2.0.0-production",
        "message": "ProfAI Production API with Celery Workers"
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Detailed health check",
    description="""Comprehensive health check showing status of all components.
    
**Checks:**
- API status
- Services availability
- Celery workers
- Database connection
- Course count

**Use Cases:**
- Monitoring and alerting
- Deployment verification
- Troubleshooting
    """,
    responses={
        200: {"description": "Health status retrieved"}
    }
)
async def health_check():
    """Detailed health check"""
    health = {
        "api": "healthy",
        "services": SERVICES_AVAILABLE,
        "celery": "unknown",
        "database": "unknown",
        "database_courses": 0
    }
    
    try:
        # Check Celery connection
        inspector = celery_app.control.inspect()
        stats = inspector.stats()
        health["celery"] = "healthy" if stats else "no_workers"
    except Exception as e:
        health["celery"] = f"error: {str(e)}"
    
    # Check database connection
    try:
        if database_service:
            courses = database_service.get_all_courses()
            health["database"] = "connected"
            health["database_courses"] = len(courses)
        else:
            health["database"] = "not_initialized"
            health["database_reason"] = "database_service is None"
    except Exception as e:
        health["database"] = "error"
        health["database_error"] = str(e)
    
    return health


@app.post(
    "/api/assessment/upload-and-generate",
    tags=["Assessment"],
    summary="Upload notes and generate assessment",
    description="""Upload up to 3 documents (PDF, DOCX, TXT) and generate an MCQ assessment.
    
**How It Works:**
1. User uploads 1-3 documents containing their study notes
2. System extracts text content using LangChain document loaders
3. Content is stored in uploaded_notes table
4. AI generates MCQ questions based on the content
5. Assessment and questions are stored in database
6. Returns assessment with questions (without correct answers)

**Features:**
- 📄 **Multiple Formats**: PDF, DOCX, TXT supported
- 🤖 **AI Generation**: Uses LLM to create relevant questions
- 📊 **Customizable**: Choose difficulty and number of questions
- 💾 **Persistent**: All data stored in PostgreSQL

**Required:**
- `user_id`: User ID
- `session_id`: Session ID
- `files`: 1-3 document files (max 10MB each)

**Optional:**
- `difficulty_level`: easy, medium, hard (default: medium)
- `num_questions`: Number of questions (default: 20, max: 50)

**Response:**
Returns assessment_id and questions without correct answers for the user to attempt.
    """,
    responses={
        200: {
            "description": "Assessment generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "assessment_id": 1,
                        "total_questions": 20,
                        "questions": [
                            {
                                "question_number": 1,
                                "question_text": "What is the main concept?",
                                "options": {
                                    "A": "Option 1",
                                    "B": "Option 2",
                                    "C": "Option 3",
                                    "D": "Option 4"
                                }
                            }
                        ]
                    }
                }
            }
        },
        400: {"description": "Invalid input or file type"},
        503: {"description": "Service unavailable"}
    }
)
async def upload_and_generate_assessment(
    user_id: int = Form(...),
    session_id: int = Form(...),
    files: List[UploadFile] = File(...),
    difficulty_level: str = Form('medium'),
    num_questions: int = Form(20)
):
    """Upload documents and generate assessment"""
    if not SERVICES_AVAILABLE or not assessment_service:
        raise HTTPException(status_code=503, detail="Assessment service not available")
    
    try:
        # Validate inputs
        if len(files) > 3:
            raise HTTPException(status_code=400, detail="Maximum 3 files allowed")
        
        if len(files) == 0:
            raise HTTPException(status_code=400, detail="At least 1 file required")
        
        if difficulty_level not in ['easy', 'medium', 'hard']:
            raise HTTPException(status_code=400, detail="Invalid difficulty level")
        
        if num_questions < 1 or num_questions > 50:
            raise HTTPException(status_code=400, detail="Number of questions must be between 1 and 50")
        
        # Process files
        file_data = []
        for file in files:
            # Get file extension
            file_ext = file.filename.split('.')[-1].lower()
            
            # Validate file type
            if file_ext not in ['pdf', 'docx', 'doc', 'txt']:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported file type: {file_ext}. Supported types: PDF, DOCX, TXT"
                )
            
            # Read file content
            file_bytes = await file.read()
            
            # Check file size (max 10MB)
            if len(file_bytes) > 10 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"File {file.filename} exceeds 10MB limit")
            
            file_data.append((file_bytes, file.filename, file_ext))
            logging.info(f"Received file: {file.filename} ({len(file_bytes)} bytes)")
        
        # Generate assessment
        result = await assessment_service.process_and_generate_assessment(
            user_id=user_id,
            session_id=session_id,
            file_bytes_list=file_data,
            difficulty_level=difficulty_level,
            num_questions=num_questions
        )
        
        return {
            "status": "success",
            "message": "Assessment generated successfully",
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/assessment/{assessment_id}",
    tags=["Assessment"],
    summary="Get assessment for display",
    description="""Retrieve an assessment without correct answers for the user to attempt.
    
**Use Cases:**
- User wants to retake an assessment
- Display assessment on frontend
- Review assessment questions

**Note:** Does not include correct answers or explanations.
    """,
    responses={
        200: {"description": "Assessment retrieved successfully"},
        404: {"description": "Assessment not found"},
        503: {"description": "Service unavailable"}
    }
)
async def get_assessment(assessment_id: int):
    """Get assessment without answers"""
    if not SERVICES_AVAILABLE or not assessment_service:
        raise HTTPException(status_code=503, detail="Assessment service not available")
    
    try:
        assessment = assessment_service.get_assessment_for_display(assessment_id)
        
        if not assessment:
            raise HTTPException(status_code=404, detail=f"Assessment {assessment_id} not found")
        
        return {
            "status": "success",
            **assessment
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/assessment/submit",
    tags=["Assessment"],
    summary="Submit assessment answers and get results",
    description="""Submit user's answers for an assessment and receive evaluation results.
    
**How It Works:**
1. User submits their selected answers
2. System compares with correct answers stored in database
3. Calculates score, percentage, correct/incorrect counts
4. Saves response to user_assessment_responses table
5. Returns detailed results with explanations

**Features:**
- ✅ **Instant Grading**: Immediate results with score
- 📊 **Detailed Feedback**: Per-question breakdown
- 📝 **Explanations**: Why each answer is correct/incorrect
- 🔄 **Multiple Attempts**: Track all attempts per user
- ⏱️ **Time Tracking**: Optional time_taken field

**Request Body:**
```json
{
    "user_id": 1,
    "session_id": 123,
    "assessment_id": 5,
    "answers": {
        "1": "A",
        "2": "B",
        "3": "C"
    },
    "time_taken": 300
}
```

**Response:**
Returns score, percentage, detailed results with correct answers and explanations.
    """,
    responses={
        200: {
            "description": "Assessment evaluated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "response_id": 1,
                        "assessment_id": 5,
                        "score": 15,
                        "total_questions": 20,
                        "correct_answers": 15,
                        "incorrect_answers": 5,
                        "percentage": 75.0,
                        "passed": True,
                        "detailed_results": [
                            {
                                "question_number": 1,
                                "question_text": "What is...",
                                "user_answer": "A",
                                "correct_answer": "A",
                                "is_correct": True,
                                "explanation": "This is correct because..."
                            }
                        ]
                    }
                }
            }
        },
        400: {"description": "Invalid input"},
        404: {"description": "Assessment not found"},
        503: {"description": "Service unavailable"}
    }
)
async def submit_assessment(request: dict):
    """Submit assessment and get evaluation"""
    if not SERVICES_AVAILABLE or not assessment_service:
        raise HTTPException(status_code=503, detail="Assessment service not available")
    
    try:
        # Validate required fields
        required_fields = ['user_id', 'session_id', 'assessment_id', 'answers']
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        result = await assessment_service.submit_assessment(
            user_id=request['user_id'],
            session_id=request['session_id'],
            assessment_id=request['assessment_id'],
            answers=request['answers'],
            time_taken=request.get('time_taken')
        )
        
        return {
            "status": "success",
            "message": "Assessment submitted and evaluated",
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error submitting assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/assessment/user/{user_id}",
    tags=["Assessment"],
    summary="Get user's assessments",
    description="""Get all assessments created by a user with attempt statistics.
    
**Returns:**
- List of all assessments
- File names of uploaded notes
- Number of attempts per assessment
- Best score achieved
    """,
    responses={
        200: {"description": "User assessments retrieved successfully"},
        503: {"description": "Service unavailable"}
    }
)
async def get_user_assessments(user_id: int):
    """Get all assessments for a user"""
    if not SERVICES_AVAILABLE or not assessment_service:
        raise HTTPException(status_code=503, detail="Assessment service not available")
    
    try:
        assessments = assessment_service.get_user_assessments(user_id)
        
        return {
            "status": "success",
            "user_id": user_id,
            "total_assessments": len(assessments),
            "assessments": assessments
        }
        
    except Exception as e:
        logging.error(f"Error getting user assessments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/assessment/{assessment_id}/attempts/{user_id}",
    tags=["Assessment"],
    summary="Get user's attempts for an assessment",
    description="""Get all attempts by a user for a specific assessment.
    
**Returns:**
- All attempts with scores
- Attempt numbers
- Timestamps
- Detailed results for each attempt
    """,
    responses={
        200: {"description": "Assessment attempts retrieved successfully"},
        503: {"description": "Service unavailable"}
    }
)
async def get_assessment_attempts(assessment_id: int, user_id: int):
    """Get user's attempts for an assessment"""
    if not SERVICES_AVAILABLE or not assessment_service:
        raise HTTPException(status_code=503, detail="Assessment service not available")
    
    try:
        attempts = assessment_service.get_assessment_attempts(user_id, assessment_id)
        
        return {
            "status": "success",
            "user_id": user_id,
            "assessment_id": assessment_id,
            "total_attempts": len(attempts),
            "attempts": attempts
        }
        
    except Exception as e:
        logging.error(f"Error getting assessment attempts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/progress/mark-complete",
    tags=["Progress"],
    summary="Mark topic as completed",
    description="""Mark a specific topic as completed for a user.
    
**How It Works:**
1. User clicks "Mark Complete" on UI
2. Frontend sends course_id, module_id, topic_id
3. System updates user_progress table
4. Sets status to 'completed' and progress_percentage to 100
5. Records completion timestamp

**Features:**
- ✅ **Track Progress**: Know what user has completed
- 📊 **Analytics**: Calculate course completion percentage
- 🔄 **Idempotent**: Safe to call multiple times
- ⏰ **Timestamps**: Track when each topic was completed

**Request Body:**
```json
{
    "user_id": 1,
    "course_id": 5,
    "module_id": 12,
    "topic_id": 45
}
```

**Response:**
Confirmation and updated completion statistics.
    """,
    responses={
        200: {
            "description": "Topic marked as completed",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Topic marked as completed",
                        "completion_stats": {
                            "total_topics": 50,
                            "completed_topics": 25,
                            "completion_percentage": 50.0
                        }
                    }
                }
            }
        },
        400: {"description": "Missing required fields"},
        503: {"description": "Database service unavailable"}
    }
)
async def mark_topic_complete(request: dict):
    """Mark a topic as completed"""
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service unavailable")
    
    try:
        # Validate required fields
        required_fields = ['user_id', 'course_id', 'module_id', 'topic_id']
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Mark topic complete
        success = database_service.mark_topic_complete(
            user_id=request['user_id'],
            course_id=request['course_id'],
            module_id=request['module_id'],
            topic_id=request['topic_id']
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to mark topic complete")
        
        # Get updated completion stats
        stats = database_service.get_course_completion_stats(
            user_id=request['user_id'],
            course_id=request['course_id']
        )
        
        return {
            "status": "success",
            "message": "Topic marked as completed",
            "completion_stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error marking topic complete: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/progress/user/{user_id}/course/{course_id}",
    tags=["Progress"],
    summary="Get user's progress for a course",
    description="""Retrieve detailed progress information for a user in a specific course.
    
**Returns:**
- List of completed topics with timestamps
- Module and topic titles
- Completion status
- Overall completion statistics

**Use Cases:**
- Display progress on user dashboard
- Show which topics are completed
- Calculate course completion percentage
- Track learning journey
    """,
    responses={
        200: {
            "description": "Progress retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "user_id": 1,
                        "course_id": 5,
                        "completion_stats": {
                            "total_topics": 50,
                            "completed_topics": 25,
                            "completion_percentage": 50.0
                        },
                        "progress": [
                            {
                                "module_title": "Introduction",
                                "topic_title": "Getting Started",
                                "status": "completed",
                                "completion_date": "2026-01-08T10:30:00"
                            }
                        ]
                    }
                }
            }
        },
        503: {"description": "Database service unavailable"}
    }
)
async def get_user_progress(user_id: int, course_id: int):
    """Get user's progress for a course"""
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service unavailable")
    
    try:
        # Get progress
        progress = database_service.get_user_progress(user_id, course_id)
        
        # Get completion stats
        stats = database_service.get_course_completion_stats(user_id, course_id)
        
        return {
            "status": "success",
            "user_id": user_id,
            "course_id": course_id,
            "completion_stats": stats,
            "progress": progress
        }
        
    except Exception as e:
        logging.error(f"Error getting user progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== SELF-IMPROVEMENT / RECOMMENDATION ENDPOINT =====

@app.get(
    "/api/recommendations/{user_id}",
    tags=["Progress"],
    summary="Get personalized learning recommendations",
    description="""Self-improvement agent that analyzes student progress, quiz scores,
and learning patterns to provide actionable recommendations.

**Returns:**
- **weak_modules**: Modules where quiz score < 60% — need revision
- **recommended_quizzes**: Quizzes to take or retake
- **next_topics**: Incomplete topics to study next
- **next_courses**: Courses the student hasn't started
- **summary**: Natural-language summary of recommendations

**Use Cases:**
- Student dashboard "What should I study next?"
- Adaptive learning path
- Self-improvement feedback loop
    """,
    responses={
        200: {"description": "Recommendations generated successfully"},
        503: {"description": "Service unavailable", "model": ErrorResponse}
    }
)
async def get_recommendations(user_id: int):
    """Get personalized learning recommendations for a student."""
    try:
        from services.recommendation_service import RecommendationService
        # Use cached instance to avoid creating new DB connections per request
        if not hasattr(get_recommendations, '_rec_service'):
            get_recommendations._rec_service = RecommendationService()
        rec_service = get_recommendations._rec_service
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, rec_service.get_recommendations, user_id)
        
        if "error" in result:
            raise HTTPException(status_code=503, detail=result["error"])
        
        return {
            "status": "success",
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating recommendations for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Start server
if __name__ == "__main__":
    import uvicorn
    
    # Start WebSocket server in background
    websocket_thread = run_websocket_server_in_thread()
    
    # Start FastAPI server
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info"
    )
