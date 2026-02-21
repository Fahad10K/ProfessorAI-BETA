"""
ProfAI - Clean API Server
Streamlined version with only essential endpoints
"""

import logging
import asyncio
import sys
import os
import json
import time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
import io
import json
import base64

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from models.schemas import CourseLMS, TTSRequest, QuizRequest, QuizSubmission, QuizDisplay
from models.job_status import job_tracker, JobStatus, JobInfo

# Import WebSocket server
from websocket_server import run_websocket_server_in_thread

# Import services
try:
    from services.chat_service import ChatService
    from services.document_service import DocumentService
    from services.async_document_service import async_document_service
    from services.audio_service import AudioService
    from services.teaching_service import TeachingService
    from services.quiz_service import QuizService
    from services.database_service_actual import get_database_service
    SERVICES_AVAILABLE = True
    print("✅ All services loaded successfully")
except ImportError as e:
    print(f"⚠️ Some services not available: {e}")
    SERVICES_AVAILABLE = False

# Initialize FastAPI app
app = FastAPI(
    title="ProfAI API",
    description="AI-powered multilingual educational assistant with course generation and chat capabilities.",
    version="2.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),  # In production, set CORS_ALLOWED_ORIGINS to your frontend's domain
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
document_service = None
audio_service = None
teaching_service = None
quiz_service = None

if SERVICES_AVAILABLE:
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Attempting to initialize services (Attempt {attempt + 1}/{MAX_RETRIES})...")
            chat_service = ChatService()
            document_service = DocumentService()
            audio_service = AudioService()
            teaching_service = TeachingService()
            quiz_service = QuizService()
            logging.info("✅ All services initialized successfully")
            break  # Exit loop on success
        except Exception as e:
            logging.warning(f"⚠️ Failed to initialize services on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("❌ All retries failed. Some services will be unavailable.")
                SERVICES_AVAILABLE = False

# ===== COURSE MANAGEMENT ENDPOINTS =====

@app.post("/api/upload-pdfs")
async def upload_and_process_pdfs(
    files: List[UploadFile] = File(...),
    course_title: str = Form(None)
):
    """
    Upload PDF files and generate course content asynchronously.
    Returns immediately with a job_id. Poll /api/jobs/{job_id} for status.
    """
    if not SERVICES_AVAILABLE or not document_service:
        raise HTTPException(status_code=503, detail="Document processing service not available")

    try:
        logging.info(f"Received {len(files)} PDF files for course: {course_title}")
        
        # Create job
        job_id = job_tracker.create_job()
        
        # Start background processing
        asyncio.create_task(
            async_document_service.process_pdfs_async(job_id, files, course_title)
        )
        
        logging.info(f"Created job {job_id} for PDF processing")
        return {
            "message": "PDF processing started",
            "job_id": job_id,
            "status": "pending",
            "status_url": f"/api/jobs/{job_id}"
        }
        
    except Exception as e:
        logging.error(f"Error starting PDF processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Get status of a background job.
    
    Status values:
    - pending: Job created but not started
    - processing: Job is currently running
    - completed: Job finished successfully
    - failed: Job encountered an error
    """
    job = job_tracker.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job.dict()

@app.post("/api/upload-pdfs-sync")
async def upload_and_process_pdfs_sync(
    files: List[UploadFile] = File(...),
    course_title: str = Form(None)
):
    """
    LEGACY ENDPOINT: Upload PDF files and wait for completion (BLOCKING).
    
    ⚠️ WARNING: This endpoint blocks until processing completes (2-10 minutes).
    Use /api/upload-pdfs instead for non-blocking operation.
    
    This endpoint is kept for backward compatibility.
    """
    if not SERVICES_AVAILABLE or not document_service:
        raise HTTPException(status_code=503, detail="Document processing service not available")

    try:
        logging.info(f"[SYNC] Processing {len(files)} PDF files for course: {course_title}")
        
        # Process PDFs and generate course (BLOCKING)
        course_data = await document_service.process_pdfs_and_generate_course(files, course_title)
        
        if not course_data:
            raise HTTPException(status_code=500, detail="Failed to generate course content")
        
        logging.info(f"Course generated successfully: {course_data.get('course_title', 'Unknown')}")
        return {"message": "Course generated successfully", "course": course_data}
        
    except Exception as e:
        logging.error(f"Error processing PDFs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses")
async def get_courses():
    """Get list of available courses."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                # Single course format
                return [{
                    "course_id": data.get("course_id", 1),
                    "course_title": data.get("course_title", "Generated Course"),
                    "modules": len(data.get("modules", []))
                }]
            elif isinstance(data, list):
                # Multi-course format
                return [{
                    "course_id": course.get("course_id", i+1),
                    "course_title": course.get("course_title", f"Course {i+1}"),
                    "modules": len(course.get("modules", []))
                } for i, course in enumerate(data)]
                
        return []
    except Exception as e:
        logging.error(f"Error loading courses: {e}")

@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    """Get specific course content."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                # Single course format
                if str(data.get("course_id", 1)) == str(course_id):
                    return data
                else:
                    raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
            elif isinstance(data, list):
                # Multi-course format - find the specific course
                for course in data:
                    if str(course.get("course_id", "")) == str(course_id):
                        return course
                raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
            else:
                raise HTTPException(status_code=500, detail="Invalid course data format")
                
        raise HTTPException(status_code=404, detail="No courses found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error loading course {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== QUIZ ENDPOINTS =====

@app.post("/api/quiz/generate-module")
async def generate_module_quiz(request: QuizRequest):
    """Generate a 20-question MCQ quiz for a specific module."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        # Load course content
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        course_content = None
        if isinstance(data, dict) and 'course_title' in data:
            # Single course format - check if course_id matches
            if str(data.get("course_id", 1)) == str(request.course_id):
                course_content = data
        elif isinstance(data, list):
            # Multi-course format - find the specific course by ID
            for course in data:
                if str(course.get("course_id", "")) == str(request.course_id):
                    course_content = course
                    break
        
        if not course_content:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
        # Validate module week exists
        module_weeks = [mod.get("week") for mod in course_content.get("modules", [])]
        if request.module_week not in module_weeks:
            raise HTTPException(
                status_code=400, 
                detail=f"Module week {request.module_week} not found. Available weeks: {module_weeks}"
            )
        
        logging.info(f"Generating module quiz for week {request.module_week}")
        quiz = await quiz_service.generate_module_quiz(request.module_week, course_content)
        
        # Return quiz without answers for security
        quiz_display = quiz_service.get_quiz_without_answers(quiz.quiz_id)
        if not quiz_display:
            raise HTTPException(status_code=500, detail="Failed to prepare quiz for display")
        
        return {
            "message": "Module quiz generated successfully",
            "quiz": quiz_display.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating module quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quiz/generate-course")
async def generate_course_quiz(request: QuizRequest):
    """Generate a 40-question MCQ quiz covering the entire course."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        # Load course content
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
           data = json.load(f)
        
        # Handle both single course and multi-course formats
        course_content = None
        if isinstance(data, dict) and 'course_title' in data:
            # Single course format - check if course_id matches
            if str(data.get("course_id", 1)) == str(request.course_id):
                course_content = data
        elif isinstance(data, list):
            # Multi-course format - find the specific course by ID
            for course in data:
                if str(course.get("course_id", "")) == str(request.course_id):
                    course_content = course
                    break
        
        if not course_content:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
        
        logging.info(f"Generating comprehensive course quiz for course: {course_content.get('course_title')}")
        quiz = await quiz_service.generate_course_quiz(course_content)
        
        # Return quiz without answers for security
        quiz_display = quiz_service.get_quiz_without_answers(quiz.quiz_id)
        if not quiz_display:
            raise HTTPException(status_code=500, detail="Failed to prepare quiz for display")
        
        return {
            "message": "Course quiz generated successfully",
            "quiz": quiz_display.dict()
        }
        
    except Exception as e:
        logging.error(f"Error generating course quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/quiz/submit")
async def submit_quiz(submission: QuizSubmission):
    """Submit quiz answers and get evaluation results."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        logging.info(f"Processing quiz submission for quiz {submission.quiz_id} by user {submission.user_id}")
        
        # Evaluate the quiz submission
        result = quiz_service.evaluate_quiz(submission)
        
        return {
            "message": "Quiz evaluated successfully",
            "result": result.dict()
        }
        
    except ValueError as ve:
        logging.error(f"Validation error in quiz submission: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"Error evaluating quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/quiz/{quiz_id}")
async def get_quiz(quiz_id: str):
    """Get a specific quiz (without answers) for display."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        quiz = quiz_service.get_quiz_without_answers(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
        
        return {"quiz": quiz.dict()}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving quiz {quiz_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== CHAT & COMMUNICATION ENDPOINTS =====

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    """Text-only chat endpoint for dedicated chat page."""
    if not SERVICES_AVAILABLE or not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    
    try:
        query = request.get('message') or request.get('query')
        language = request.get('language', 'en-IN')
        
        if not query:
            raise HTTPException(status_code=400, detail="Message/query is required")
        
        logging.info(f"Chat query: {query[:50]}...")
        response_data = await chat_service.ask_question(query, language)
        return response_data
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat-with-audio")
async def chat_with_audio_endpoint(request: dict):
    """Chat endpoint with automatic audio generation for home page chat box."""
    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
        raise HTTPException(status_code=503, detail="Chat or audio service not available")
    
    try:
        query = request.get('message') or request.get('query')
        language = request.get('language', 'en-IN')
        
        if not query:
            raise HTTPException(status_code=400, detail="Message/query is required")
        
        logging.info(f"Chat with audio query: {query[:50]}...")
        
        # Get text response
        response_data = await chat_service.ask_question(query, language)
        response_text = response_data.get('answer') or response_data.get('response', '')
        
        if not response_text:
            raise HTTPException(status_code=500, detail="No response generated")
        
        # Generate audio for the response
        logging.info(f"Generating audio for response: {response_text[:50]}...")
        audio_buffer = await audio_service.generate_audio_from_text(response_text, language)
        
        # Return both text and audio
        if audio_buffer.getbuffer().nbytes > 0:
            # Convert audio to base64 for JSON response
            import base64
            audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
            response_data['audio'] = audio_base64
            response_data['has_audio'] = True
        else:
            response_data['has_audio'] = False
            logging.warning("Audio generation failed, returning text only")
        
        return response_data
        
    except Exception as e:
        logging.error(f"Error in chat with audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/transcribe")
async def transcribe_endpoint(language: str = Form("en-IN"), audio_file: UploadFile = File(...)):
    """Audio transcription for voice input."""
    if not SERVICES_AVAILABLE or not audio_service:
        raise HTTPException(status_code=503, detail="Audio service not available")
    
    try:
        logging.info(f"Transcribing audio in language: {language}")
        
        audio_content = await audio_file.read()
        audio_buffer = io.BytesIO(audio_content)
        
        transcribed_text = await audio_service.transcribe_audio(audio_buffer, language)
        
        if not transcribed_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio")
        
        logging.info(f"Transcribed: {transcribed_text[:50]}...")
        return {"transcribed_text": transcribed_text}
        
    except Exception as e:
        logging.error(f"Error in transcription: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== CLASS TEACHING ENDPOINTS =====

@app.post("/api/start-class")
async def start_class_endpoint(request: dict):
    """Start a class session with content preview and audio generation."""
    if not SERVICES_AVAILABLE or not teaching_service or not audio_service:
        raise HTTPException(status_code=503, detail="Required services not available")
    
    try:
        course_id = request.get("course_id")
        module_index = request.get("module_index", 0)
        sub_topic_index = request.get("sub_topic_index", 0)
        language = request.get("language", "en-IN")
        content_only = request.get("content_only", False)  # If true, return only content preview
        
        logging.info(f"Starting class for course: {course_id}, module: {module_index}, topic: {sub_topic_index}")
        
        # Load course content
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        if isinstance(data, dict) and 'course_title' in data:
            # Single course format
            course_data = data
        elif isinstance(data, list):
            # Multi-course format - find the specific course by ID
            course_data = None
            for course in data:
                if str(course.get("course_id", "")) == str(course_id):
                    course_data = course
                    break
            if not course_data:
                # If no specific course found, use the first one
                course_data = data[0] if data else None
        else:
            course_data = None
            
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
            # Fallback content
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

# ===== WEBSOCKET STREAMING ENDPOINTS =====

@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Simple WebSocket test endpoint."""
    try:
        await websocket.accept()
        logging.info("Test WebSocket connection accepted")
        
        await websocket.send_json({
            "type": "connection_ready",
            "message": "Test WebSocket connected successfully"
        })
        
        while True:
            try:
                data = await websocket.receive_json()
                message_type = data.get("type")
                
                if message_type == "ping":
                    await websocket.send_json({"type": "pong", "message": "Test connection alive"})
                elif message_type == "echo":
                    await websocket.send_json({"type": "echo", "data": data})
                else:
                    await websocket.send_json({"type": "error", "error": f"Unknown type: {message_type}"})
                    
            except WebSocketDisconnect:
                logging.info("Test WebSocket client disconnected")
                break
            except Exception as e:
                logging.error(f"Test WebSocket error: {e}")
                break
                
    except Exception as e:
        logging.error(f"Test WebSocket connection error: {e}")

@app.websocket("/ws/audio-stream")
async def websocket_audio_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming with sub-900ms latency."""
    try:
        await websocket.accept()
        logging.info("WebSocket connection accepted")
        
        # Send connection confirmation immediately
        await websocket.send_json({
            "type": "connection_ready",
            "message": "WebSocket connected and ready",
            "services_available": SERVICES_AVAILABLE,
            "chat_service": chat_service is not None,
            "audio_service": audio_service is not None
        })
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                message_type = data.get("type")
                
                logging.info(f"Received WebSocket message: {message_type}")
                
                if message_type == "ping":
                    await websocket.send_json({"type": "pong", "message": "Connection alive"})
                
                elif message_type == "chat_with_audio":
                    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
                        await websocket.send_json({"type": "error", "error": "Required services not available"})
                        continue
                    await handle_chat_with_audio(websocket, data, chat_service, audio_service)
                
                elif message_type == "start_class":
                    if not SERVICES_AVAILABLE or not teaching_service or not audio_service:
                        await websocket.send_json({"type": "error", "error": "Teaching services not available"})
                        continue
                    await handle_start_class(websocket, data, teaching_service, audio_service)
                
                elif message_type == "audio_only":
                    if not SERVICES_AVAILABLE or not audio_service:
                        await websocket.send_json({"type": "error", "error": "Audio service not available"})
                        continue
                    await handle_audio_only(websocket, data, audio_service)
                
                else:
                    await websocket.send_json({
                        "type": "error", 
                        "error": f"Unknown message type: {message_type}"
                    })
                    
            except WebSocketDisconnect:
                logging.info("WebSocket client disconnected")
                break
            except Exception as e:
                logging.error(f"Error processing WebSocket message: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Message processing error: {str(e)}"
                    })
                except:
                    break
                
    except Exception as e:
        logging.error(f"WebSocket connection error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await websocket.close()
        except:
            pass

async def handle_chat_with_audio(websocket: WebSocket, data: dict, chat_service, audio_service):
    """Handle chat with audio streaming."""
    try:
        query = data.get("message")
        language = data.get("language", "en-IN")
        
        if not query:
            await websocket.send_json({"type": "error", "error": "Message is required"})
            return
        
        logging.info(f"Processing chat query: {query[:50]}...")
        
        # Send immediate acknowledgment
        await websocket.send_json({
            "type": "processing_started",
            "message": "Generating response..."
        })
        
        try:
            # Get text response
            response_data = await chat_service.ask_question(query, language)
            response_text = response_data.get('answer') or response_data.get('response', '')
            
            if not response_text:
                await websocket.send_json({"type": "error", "error": "No response generated"})
                return
            
            logging.info(f"Generated response: {len(response_text)} chars")
            
            # Send text response immediately
            await websocket.send_json({
                "type": "text_response",
                "text": response_text,
                "metadata": response_data
            })
            
        except Exception as e:
            logging.error(f"Chat service error: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Chat service failed: {str(e)}"
            })
            return
        
        # Generate audio with streaming - SAME PATTERN AS start_class
        await websocket.send_json({
            "type": "audio_generation_started",
            "message": "Generating audio..."
        })
        
        try:
            # OPTIMIZED streaming for sub-300ms latency (consistent with start_class)
            audio_start_time = time.time()
            chunk_count = 0
            total_audio_size = 0
            first_chunk_sent = False
            
            logging.info(f"🚀 Starting REAL-TIME chat audio streaming for: {response_text[:50]}...")
            
            async for audio_chunk in audio_service.stream_audio_from_text(response_text, language, websocket):
                if audio_chunk and len(audio_chunk) > 0:
                    chunk_count += 1
                    total_audio_size += len(audio_chunk)
                    
                    # Convert to base64 for JSON transmission
                    audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                    
                    # Send chunk immediately
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "chunk_id": chunk_count,
                        "audio_data": audio_base64,
                        "size": len(audio_chunk),
                        "is_first_chunk": not first_chunk_sent
                    })
                    
                    # Log first chunk latency (CRITICAL METRIC)
                    if not first_chunk_sent:
                        first_audio_latency = (time.time() - audio_start_time) * 1000
                        logging.info(f"🎯 FIRST CHAT AUDIO CHUNK delivered in {first_audio_latency:.0f}ms")
                        
                        if first_audio_latency <= 300:
                            logging.info(f"🎉 TARGET ACHIEVED! Sub-300ms latency: {first_audio_latency:.0f}ms")
                        elif first_audio_latency <= 900:
                            logging.info(f"✅ GOOD latency: {first_audio_latency:.0f}ms (under 900ms target)")
                        else:
                            logging.info(f"⚠️ HIGH latency: {first_audio_latency:.0f}ms (needs optimization)")
                        
                        first_chunk_sent = True
                    else:
                        # Log subsequent chunks
                        chunk_time = (time.time() - audio_start_time) * 1000
                        logging.info(f"   Chunk {chunk_count}: {len(audio_chunk)} bytes at {chunk_time:.0f}ms")
            
            # Send completion message (consistent with start_class)
            await websocket.send_json({
                "type": "audio_generation_complete",
                "total_chunks": chunk_count,
                "total_size": total_audio_size,
                "first_chunk_latency": (time.time() - audio_start_time) * 1000 if first_chunk_sent else 0,
                "message": "Chat audio ready to play!"
            })
            
            audio_total_time = (time.time() - audio_start_time) * 1000
            logging.info(f"🏁 Chat audio streaming complete: {chunk_count} chunks, {total_audio_size} bytes in {audio_total_time:.0f}ms")
                
        except Exception as e:
            logging.error(f"❌ Chat audio generation error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Chat audio generation failed: {str(e)}"
            })
            
    except Exception as e:
        logging.error(f"Chat with audio error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "error": f"Chat processing failed: {str(e)}"
        })

async def handle_start_class(websocket: WebSocket, data: dict, teaching_service, audio_service):
    """Handle start class with real-time audio streaming."""
    try:
        course_id = data.get("course_id")
        module_index = data.get("module_index", 0)
        sub_topic_index = data.get("sub_topic_index", 0)
        language = data.get("language", "en-IN")
        
        logging.info(f"WebSocket start class: course={course_id}, module={module_index}, topic={sub_topic_index}")
        
        # Send immediate acknowledgment
        await websocket.send_json({
            "type": "class_starting",
            "message": "Loading course content...",
            "course_id": course_id,
            "module_index": module_index,
            "sub_topic_index": sub_topic_index
        })
        
        try:
            # Load course content
            if not os.path.exists(config.OUTPUT_JSON_PATH):
                await websocket.send_json({"type": "error", "error": "Course content not found"})
                return
            
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                 data = json.load(f)
            
            # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                # Single course format
                course_data = data
            elif isinstance(data, list):
                # Multi-course format - find the specific course by ID
                course_data = None
                for course in data:
                    if str(course.get("course_id", "")) == str(course_id):
                        course_data = course
                        break
                if not course_data:
                    # If no specific course found, use the first one
                    course_data = data[0] if data else None
            else:
                course_data = None
                
            if not course_data:
                await websocket.send_json({"type": "error", "error": "Course content not found"})
                return
            
            # Validate indices
            if module_index >= len(course_data.get("modules", [])):
                await websocket.send_json({"type": "error", "error": "Module not found"})
                return
                
            module = course_data["modules"][module_index]
            
            if sub_topic_index >= len(module.get("sub_topics", [])):
                await websocket.send_json({"type": "error", "error": "Sub-topic not found"})
                return
                
            sub_topic = module["sub_topics"][sub_topic_index]
            
            # Send course info
            await websocket.send_json({
                "type": "course_info",
                "module_title": module['title'],
                "sub_topic_title": sub_topic['title'],
                "message": "Generating teaching content..."
            })
            
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
                # Fallback content
                teaching_content = f"Welcome to the lesson on {sub_topic['title']}. {raw_content[:500]}..."
            
            logging.info(f"Generated teaching content: {len(teaching_content)} characters")
            
            # Send teaching content
            await websocket.send_json({
                "type": "teaching_content",
                "content": teaching_content,
                "content_length": len(teaching_content),
                "message": "Content generated, starting audio..."
            })
            
        except Exception as e:
            logging.error(f"Course loading error: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Failed to load course content: {str(e)}"
            })
            return
        
        # Generate audio with streaming
        await websocket.send_json({
            "type": "audio_stream_start",
            "message": "Generating class audio..."
        })
        
        try:
            logging.info("Starting class audio generation...")
            # Use ultra-fast generation for better reliability
            audio_buffer = await audio_service.generate_audio_from_text(teaching_content, language, ultra_fast=True)
            
            if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                logging.info(f"Class audio generated: {audio_buffer.getbuffer().nbytes} bytes")
                audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
                await websocket.send_json({
                    "type": "audio_chunk",
                    "chunk_id": 1,
                    "audio_data": audio_base64,
                    "size": audio_buffer.getbuffer().nbytes
                })
                
                await websocket.send_json({
                    "type": "class_complete",
                    "total_chunks": 1,
                    "message": "Class audio ready to play!"
                })
            else:
                logging.warning("No class audio generated")
                await websocket.send_json({
                    "type": "error",
                    "error": "Failed to generate class audio"
                })
                
        except Exception as e:
            logging.error(f"Class audio generation error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Class audio generation failed: {str(e)}"
            })
            
    except Exception as e:
        logging.error(f"Start class error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "error": f"Class processing failed: {str(e)}"
        })

async def handle_audio_only(websocket: WebSocket, data: dict, audio_service):
    """Handle audio-only generation."""
    try:
        text = data.get("text")
        language = data.get("language", "en-IN")
        
        if not text:
            await websocket.send_json({"type": "error", "error": "Text is required"})
            return
        
        logging.info(f"Processing audio-only request: {len(text)} chars")
        
        await websocket.send_json({
            "type": "audio_stream_start",
            "message": "Generating audio..."
        })
        
        try:
            logging.info("Starting audio generation...")
            # Use ultra-fast generation for better reliability
            audio_buffer = await audio_service.generate_audio_from_text(text, language, ultra_fast=True)
            
            if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                logging.info(f"Audio generated: {audio_buffer.getbuffer().nbytes} bytes")
                audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
                await websocket.send_json({
                    "type": "audio_chunk",
                    "chunk_id": 1,
                    "audio_data": audio_base64,
                    "size": audio_buffer.getbuffer().nbytes
                })
                
                await websocket.send_json({
                    "type": "audio_stream_complete",
                    "total_chunks": 1
                })
            else:
                logging.warning("No audio generated")
                await websocket.send_json({
                    "type": "error",
                    "error": "Failed to generate audio - empty result"
                })
                
        except Exception as e:
            logging.error(f"Audio generation error: {e}")
            import traceback
            traceback.print_exc()
            await websocket.send_json({
                "type": "error",
                "error": f"Audio generation failed: {str(e)}"
            })
            
    except Exception as e:
        logging.error(f"Audio only error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            "type": "error",
            "error": f"Audio processing failed: {str(e)}"
        })

# ===== SYSTEM ENDPOINTS =====

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services_available": SERVICES_AVAILABLE,
        "services": {
            "chat_service": chat_service is not None,
            "document_service": document_service is not None,
            "audio_service": audio_service is not None,
            "teaching_service": teaching_service is not None
        }
    }

@app.get("/test-services")
async def test_services():
    """Test endpoint to verify services are working."""
    results = {}
    
    # Test chat service
    if chat_service:
        try:
            response = await chat_service.ask_question("Hello", "en-IN")
            results["chat_service"] = {"status": "working", "response_length": len(str(response))}
        except Exception as e:
            results["chat_service"] = {"status": "error", "error": str(e)}
    else:
        results["chat_service"] = {"status": "not_available"}
    
    # Test audio service
    if audio_service:
        try:
            audio_buffer = await audio_service.generate_audio_from_text("Hello test", "en-IN", ultra_fast=True)
            results["audio_service"] = {"status": "working", "audio_size": audio_buffer.getbuffer().nbytes}
        except Exception as e:
            results["audio_service"] = {"status": "error", "error": str(e)}
    else:
        results["audio_service"] = {"status": "not_available"}
    
    return {
        "overall_status": "tested",
        "services_available": SERVICES_AVAILABLE,
        "test_results": results
    }

@app.get("/websocket-info")
async def websocket_info():
    """Information about available WebSocket endpoints."""
    base_url = "ws://localhost:5001"  # Adjust based on your config
    
    return {
        "websocket_endpoints": {
            "/ws/test": {
                "url": f"{base_url}/ws/test",
                "description": "Simple WebSocket test endpoint for connection testing",
                "supported_messages": ["ping", "echo"],
                "example_usage": {
                    "ping": {"type": "ping"},
                    "echo": {"type": "echo", "message": "test"}
                }
            },
            "/ws/audio-stream": {
                "url": f"{base_url}/ws/audio-stream",
                "description": "Real-time audio streaming with sub-900ms latency",
                "supported_messages": ["ping", "chat_with_audio", "start_class", "audio_only"],
                "example_usage": {
                    "ping": {"type": "ping"},
                    "chat_with_audio": {
                        "type": "chat_with_audio",
                        "message": "Hello, how are you?",
                        "language": "en-IN"
                    },
                    "start_class": {
                        "type": "start_class",
                        "course_id": "1",
                        "module_index": 0,
                        "sub_topic_index": 0,
                        "language": "en-IN"
                    },
                    "audio_only": {
                        "type": "audio_only",
                        "text": "Convert this text to audio",
                        "language": "en-IN"
                    }
                }
            }
        },
        "note": "WebSocket endpoints don't appear in Swagger/OpenAPI docs. Use WebSocket clients to test.",
        "test_page": "/stream-test",
        "python_test_script": "test_websocket.py"
    }

# ===== WEB INTERFACE ENDPOINTS =====

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(web_dir, 'index.html'))

@app.get("/upload")
async def serve_upload():
    return FileResponse(os.path.join(web_dir, 'upload.html'))

@app.get("/courses")
async def serve_courses():
    return FileResponse(os.path.join(web_dir, 'courses.html'))

@app.get("/course")
async def serve_course():
    return FileResponse(os.path.join(web_dir, 'course.html'))

@app.get("/chat")
async def serve_chat():
    return FileResponse(os.path.join(web_dir, 'chat.html'))

@app.get("/stream-test")
async def serve_stream_test():
    return FileResponse(os.path.join(web_dir, 'stream-test.html'))

@app.get("/websocket-status")
async def serve_websocket_status():
    return FileResponse(os.path.join(web_dir, 'websocket-status.html'))

@app.get("/profai-websocket-test")
async def serve_profai_websocket_test():
    return FileResponse(os.path.join(web_dir, 'profai-websocket-test.html'))

@app.get("/test-web-websocket")
async def serve_test_web_websocket():
    return FileResponse(os.path.join(web_dir, 'test_web_websocket.html'))

if __name__ == "__main__":
    # Start WebSocket server in background thread
    websocket_thread = run_websocket_server_in_thread("0.0.0.0", 8765)
    print("🌐 WebSocket server started on ws://localhost:8765")
    
    # Start FastAPI server
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")