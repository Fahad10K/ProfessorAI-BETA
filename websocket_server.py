# websocket_server.py
# High-performance WebSocket server for ProfAI with sub-300ms latency
# Based on Contelligence architecture with optimizations for educational content

import asyncio
import base64
import threading
import time
import json
import logging
from datetime import datetime
from typing import Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError

# Import ProfAI services
from services.chat_service import ChatService
from services.audio_service import AudioService
from services.teaching_service import TeachingService
from services.session_manager import get_session_manager
from services.database_service_v2 import get_database_service

# Real-time Teaching Orchestrator (replaces broken LangGraph supervisor)
from services.realtime_orchestrator import (
    RealtimeOrchestrator,
    TeachingPhase,
    UserIntent,
    classify_intent,
    needs_rag,
)

import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def ts():
    """Timestamp helper for logging"""
    return datetime.utcnow().isoformat(sep=' ', timespec='milliseconds') + 'Z'

def log(*args):
    """Enhanced logging with timestamp"""
    print(f"[{ts()}][WebSocket]", *args, flush=True)

def is_normal_closure(exception) -> bool:
    """Check if a WebSocket exception represents a normal closure (codes 1000, 1001)."""
    if isinstance(exception, ConnectionClosedOK):
        return True
    if isinstance(exception, ConnectionClosed):
        # Check for normal closure codes: 1000 (OK) and 1001 (going away)
        return exception.code in (1000, 1001)
    return False

def get_disconnection_emoji(exception) -> str:
    """Get appropriate emoji for disconnection type."""
    if is_normal_closure(exception):
        return "🔌"  # Normal disconnection
    else:
        return "❌"  # Error disconnection

def log_disconnection(client_id: str, exception, context: str = ""):
    """Log disconnection with appropriate emoji and message."""
    emoji = get_disconnection_emoji(exception)
    if is_normal_closure(exception):
        if hasattr(exception, 'code'):
            log(f"{emoji} Client {client_id} disconnected normally (code {exception.code}) {context}")
        else:
            log(f"{emoji} Client {client_id} disconnected normally {context}")
    else:
        if hasattr(exception, 'code'):
            log(f"{emoji} Client {client_id} disconnected with error (code {exception.code}) {context}")
        else:
            log(f"{emoji} Client {client_id} disconnected with error: {exception} {context}")

def is_client_connected(websocket) -> bool:
    """Check if WebSocket client is still connected."""
    if not websocket:
        return False
    
    # Check if WebSocket is closed or closing
    if hasattr(websocket, 'closed') and websocket.closed:
        return False
    
    if hasattr(websocket, 'state'):
        # WebSocket states: CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3
        return websocket.state == 1  # Only OPEN state is considered connected
    
    return True

class ProfAIWebSocketWrapper:
    """
    Enhanced WebSocket wrapper for ProfAI with performance tracking and error handling.
    """
    def __init__(self, websocket, client_id: str):
        self.websocket = websocket
        self.client_id = client_id
        self.message_count = 0
        self.last_activity = time.time()
        self.connection_start_time = time.time()
        self.session_data = {}
        self.active_requests = {}
        
    async def send(self, message):
        """Enhanced send with metrics tracking and error handling."""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message
                message = json.dumps(message)
            
            # Add client_id and timestamp to all messages
            if isinstance(data, dict):
                data["client_id"] = self.client_id
                data["timestamp"] = time.time()
                message = json.dumps(data)
            
            # Track message metrics
            self.message_count += 1
            self.last_activity = time.time()
            
            await self.websocket.send(message)
            
        except ConnectionClosed as e:
            log_disconnection(self.client_id, e, "while sending message")
            raise
        except Exception as e:
            log(f"Error sending message to {self.client_id}: {e}")
            raise
    
    async def recv(self):
        """Enhanced receive with activity tracking."""
        try:
            message = await self.websocket.recv()
            self.last_activity = time.time()
            return message
            
        except ConnectionClosed as e:
            log_disconnection(self.client_id, e, "while receiving message")
            raise
        except Exception as e:
            log(f"Error receiving message from {self.client_id}: {e}")
            raise
    
    async def close(self):
        """Enhanced close with cleanup."""
        try:
            # Send final metrics before closing
            session_duration = time.time() - self.connection_start_time
            await self.send({
                "type": "connection_closing",
                "session_metrics": {
                    "total_messages": self.message_count,
                    "session_duration": session_duration,
                    "last_activity": self.last_activity
                }
            })
            await self.websocket.close()
        except:
            pass  # Ignore errors during cleanup

class ProfAIAgent:
    """
    ProfAI WebSocket agent that handles educational content delivery with low latency.
    """
    def __init__(self, websocket_wrapper: ProfAIWebSocketWrapper):
        self.websocket = websocket_wrapper
        self.client_id = websocket_wrapper.client_id
        
        # Get shared database service singleton
        try:
            self.database_service = get_database_service()
            log(f"Database service connected for client {self.client_id}")
        except Exception as e:
            log(f"Failed to get database service for {self.client_id}: {e}")
            self.database_service = None
        
        # Get shared session manager singleton
        try:
            self.session_manager = get_session_manager(redis_url=config.REDIS_URL)
            log(f"Session manager connected for client {self.client_id}")
        except Exception as e:
            log(f"Failed to get session manager for {self.client_id}: {e}")
            self.session_manager = None
        
        # Initialize services with error handling
        self.services_available = {}
        try:
            self.chat_service = ChatService()
            self.services_available["chat"] = True
            log(f"Chat service initialized for client {self.client_id}")
        except Exception as e:
            log(f"Failed to initialize chat service for {self.client_id}: {e}")
            self.chat_service = None
            self.services_available["chat"] = False
        
        try:
            self.audio_service = AudioService()
            self.services_available["audio"] = True
            log(f"Audio service initialized for client {self.client_id}")
        except Exception as e:
            log(f"Failed to initialize audio service for {self.client_id}: {e}")
            self.audio_service = None
            self.services_available["audio"] = False
        
        try:
            self.teaching_service = TeachingService()
            self.services_available["teaching"] = True
            log(f"Teaching service initialized for client {self.client_id}")
        except Exception as e:
            log(f"Failed to initialize teaching service for {self.client_id}: {e}")
            self.teaching_service = None
            self.services_available["teaching"] = False
        
        # Real-time Teaching Orchestrator (replaces broken LangGraph supervisor)
        self.orchestrator = RealtimeOrchestrator()
        
        # Performance tracking
        self.conversation_metrics = {
            "total_requests": 0,
            "avg_response_time": 0.0,
            "total_response_time": 0.0,
            "chat_requests": 0,
            "audio_requests": 0,
            "teaching_requests": 0,
            "errors": 0
        }
        
        # Session state
        self.session_start_time = time.time()
        self.current_language = "en-IN"
        self.current_course_context = None
        
        # Session identifiers
        self.user_id = None
        self.session_id = None
        self.ip_address = None
        self.user_agent = "WebSocket"
        
        # Interactive teaching session state (managed by orchestrator)
        self.teaching_session = None
        
        # Chat audio barge-in: generation counter incremented on each new
        # chat_with_audio request so the previous audio loop stops.
        self._chat_audio_gen = 0
        
        log(f"ProfAI agent initialized for client {self.client_id} - Services: {self.services_available}")

    def _ensure_orchestrator_ready(self):
        """Orchestrator is always ready (no async init needed)."""
        return self.orchestrator is not None

    async def process_messages(self):
        """
        Main message processing loop with optimized handling for different request types.
        """
        try:
            log(f"Starting message processing for client {self.client_id}")
            
            # Send connection ready message
            await self.websocket.send({
                "type": "connection_ready",
                "message": "ProfAI WebSocket connected successfully",
                "client_id": self.client_id,
                "services": self.services_available
            })
            
            while True:
                try:
                    message = await self.websocket.recv()
                    data = json.loads(message)
                    
                    message_type = data.get("type")
                    if not message_type:
                        await self.websocket.send({
                            "type": "error",
                            "error": "Message type is required"
                        })
                        continue
                    
                    # Don't log high-frequency audio chunks (fires ~15/sec)
                    if message_type != "stt_audio_chunk":
                        log(f"Processing message type: {message_type} for client {self.client_id}")
                    
                    # Route messages to appropriate handlers
                    if message_type == "ping":
                        await self.handle_ping(data)
                    elif message_type == "chat_with_audio":
                        await self.handle_chat_with_audio(data)
                    elif message_type == "start_class":
                        await self.handle_start_class(data)
                    elif message_type == "start_class_interactive":
                        await self.handle_interactive_teaching(data)
                    elif message_type == "interactive_teaching":
                        await self.handle_interactive_teaching(data)
                    elif message_type == "stt_audio_chunk":
                        await self.handle_stt_audio_chunk(data)
                    elif message_type == "teaching_user_input":
                        await self.handle_teaching_user_input(data)
                    elif message_type == "continue_teaching":
                        await self.handle_continue_teaching(data)
                    elif message_type == "end_teaching":
                        await self.handle_end_teaching(data)
                    elif message_type == "audio_only":
                        await self.handle_audio_only(data)
                    elif message_type == "transcribe_audio":
                        await self.handle_transcribe_audio(data)
                    elif message_type == "set_language":
                        await self.handle_set_language(data)
                    elif message_type == "get_metrics":
                        await self.handle_get_metrics(data)
                    else:
                        await self.websocket.send({
                            "type": "error",
                            "error": f"Unknown message type: {message_type}"
                        })
                    
                except ConnectionClosed as e:
                    log_disconnection(self.client_id, e, "during message processing")
                    # Don't count normal disconnections as errors
                    if not is_normal_closure(e):
                        self.conversation_metrics["errors"] += 1
                    break
                except json.JSONDecodeError:
                    await self.websocket.send({
                        "type": "error",
                        "error": "Invalid JSON message"
                    })
                except Exception as e:
                    log(f"❌ Error processing message for {self.client_id}: {e}")
                    try:
                        await self.websocket.send({
                            "type": "error",
                            "error": f"Message processing error: {str(e)}"
                        })
                    except ConnectionClosed as conn_e:
                        log_disconnection(self.client_id, conn_e, "while sending error message")
                        break
                    
        except Exception as e:
            log(f"Fatal error in message processing for {self.client_id}: {e}")
        finally:
            await self.cleanup()

    async def handle_ping(self, data: dict):
        """Handle ping messages for connection testing."""
        await self.websocket.send({
            "type": "pong",
            "message": "Connection alive",
            "server_time": time.time()
        })

    async def handle_chat_with_audio(self, data: dict):
        """Handle chat requests with automatic audio generation - optimized for low latency."""
        request_start_time = time.time()
        
        # Barge-in: cancel any previous chat audio stream
        self._chat_audio_gen += 1
        my_gen = self._chat_audio_gen
        
        try:
            # Enhanced service availability check
            if not self.services_available.get("chat", False):
                await self.websocket.send({
                    "type": "error", 
                    "error": "Chat service not available - please refresh connection"
                })
                return
                
            if not self.services_available.get("audio", False):
                await self.websocket.send({
                    "type": "error",
                    "error": "Audio service not available - please refresh connection"  
                })
                return
                
            
            query = data.get("message")
            language = data.get("language", self.current_language)
            user_id = data.get("user_id") or self.user_id or f"ws_{self.client_id}"
            course_id = data.get("course_id")
            ip_address = data.get("ip_address") or self.ip_address or "127.0.0.1"  # Valid IP for database inet type
            user_agent = data.get("user_agent") or self.user_agent
            
            # Resolve persona / voice for TTS
            persona_id = data.get("persona_id") or getattr(config, "DEFAULT_PERSONA", "prof_sarah")
            personas = getattr(config, "PROFESSOR_PERSONAS", {})
            persona = personas.get(persona_id, {})
            chat_voice_id = persona.get("voice_id")  # None → default
            log(f"🎤 Persona: {persona_id} → voice={chat_voice_id[:8] + '...' if chat_voice_id else 'default'}")
            
            if not query:
                await self.websocket.send({
                    "type": "error",
                    "error": "Message is required"
                })
                return
            
            # Store user_id for session
            self.user_id = user_id
            self.ip_address = ip_address
            self.user_agent = user_agent
            
            log(f"Processing chat with audio: {query[:50]}... (language: {language}, user: {user_id})")
            
            # Send immediate acknowledgment
            await self.websocket.send({
                "type": "processing_started",
                "message": "Generating response...",
                "request_id": data.get("request_id", ""),
                "timestamp": time.time()
            })
            
            # Get or create session for user
            if self.session_manager:
                try:
                    session = self.session_manager.get_or_create_session(
                        user_id=user_id,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    self.session_id = session['session_id']
                    log(f"Session retrieved: {self.session_id}")
                except Exception as e:
                    log(f"Failed to get session: {e}")
                    self.session_id = None
            
            # Get conversation history from database (last 5 interactions = 10 messages)
            conversation_history = []
            if self.session_manager and self.session_id:
                try:
                    conversation_history = self.session_manager.get_conversation_history(self.session_id, limit=5)
                    log(f"Retrieved {len(conversation_history)} messages from conversation history")
                except Exception as e:
                    log(f"Failed to get conversation history: {e}")
            
            # Get text response with enhanced error handling
            response_text = ""
            try:
                
                response_data = await asyncio.wait_for(
                    self.chat_service.ask_question(
                        query, 
                        language, 
                        self.session_id,
                        conversation_history,
                        course_id=course_id,
                        pedagogical=True,
                    ),
                    timeout=90.0  # Increased to 90s for RAG + reranking + LLM processing
                )
                response_text = response_data.get('answer') or response_data.get('response', '')
                
                if not response_text:
                    await self.websocket.send({
                        "type": "error",
                        "error": "No response generated from chat service"
                    })
                    return
                
                
                # Send text response immediately
                await self.websocket.send({
                    "type": "text_response",
                    "text": response_text,
                    "metadata": response_data,
                    "request_id": data.get("request_id", ""),
                    "timestamp": time.time()
                })
                
                log(f"Text response sent: {len(response_text)} chars")
                
                # Save messages to database (matching REST API format)
                if self.session_manager and self.session_id:
                    try:
                        self.session_manager.add_message(
                            user_id=user_id,
                            session_id=self.session_id,
                            role="user",
                            content=query,
                            message_type='voice'
                        )
                        self.session_manager.add_message(
                            user_id=user_id,
                            session_id=self.session_id,
                            role="assistant",
                            content=response_text,
                            message_type='voice',
                            metadata={
                                'route': response_data.get('route'),
                                'confidence': response_data.get('confidence'),
                                'has_audio': True
                            }
                        )
                        log(f"Messages saved to database")
                    except Exception as e:
                        log(f"Failed to save messages: {e}")
                
            except asyncio.TimeoutError:
                log(f"Chat service timeout for client {self.client_id}")
                try:
                    await self.websocket.send({
                        "type": "error",
                        "error": "Response generation timeout - please try again"
                    })
                except ConnectionClosed:
                    log(f"Client {self.client_id} disconnected during timeout handling")
                return
            except Exception as e:
                log(f"Chat service error for client {self.client_id}: {e}")
                try:
                    await self.websocket.send({
                        "type": "error", 
                        "error": f"Chat service failed: {str(e)}"
                    })
                except ConnectionClosed:
                    log(f"Client {self.client_id} disconnected during error handling")
                return
            
            # Generate audio with REAL-TIME streaming - SAME AS START_CLASS
            await self.websocket.send({
                "type": "audio_generation_started",
                "message": "Generating audio..."
            })
            
            try:
                # Accumulate small TTS chunks into larger buffers for gapless
                # playback.  At 32kbps MP3, 16 KB ≈ 4 s of audio.
                _MIN_SEND = 16_384  # 16 KB — same as teaching audio
                
                audio_start_time = time.time()
                chunk_count = 0
                total_audio_size = 0
                first_chunk_sent = False
                audio_buf = b''
                
                log(f"🚀 Starting REAL-TIME chat audio streaming for: {response_text[:50]}...")
                
                import base64
                barged_in = False
                async for audio_chunk in self.audio_service.stream_audio_from_text(response_text, language, self.websocket, voice_id=chat_voice_id):
                    # Barge-in check: a newer request has arrived
                    if my_gen != self._chat_audio_gen:
                        log("🛑 Chat audio interrupted by new request (barge-in)")
                        barged_in = True
                        break
                    
                    if audio_chunk and len(audio_chunk) > 0:
                        audio_buf += audio_chunk
                        total_audio_size += len(audio_chunk)
                        
                        # Flush buffer when large enough
                        if len(audio_buf) >= _MIN_SEND:
                            chunk_count += 1
                            audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                            await self.websocket.send({
                                "type": "audio_chunk",
                                "chunk_id": chunk_count,
                                "audio_data": audio_base64,
                                "size": len(audio_buf),
                                "is_first_chunk": not first_chunk_sent,
                                "request_id": data.get("request_id", "")
                            })
                            audio_buf = b''
                            
                            if not first_chunk_sent:
                                first_audio_latency = (time.time() - audio_start_time) * 1000
                                log(f"🎯 FIRST CHAT AUDIO CHUNK delivered in {first_audio_latency:.0f}ms ({chunk_count} accumulated)")
                                first_chunk_sent = True
                
                # Flush remaining buffer (skip if barged in)
                if audio_buf and not barged_in:
                    chunk_count += 1
                    audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                    await self.websocket.send({
                        "type": "audio_chunk",
                        "chunk_id": chunk_count,
                        "audio_data": audio_base64,
                        "size": len(audio_buf),
                        "is_first_chunk": not first_chunk_sent,
                        "request_id": data.get("request_id", "")
                    })
                    if not first_chunk_sent:
                        first_audio_latency = (time.time() - audio_start_time) * 1000
                        log(f"🎯 FIRST CHAT AUDIO CHUNK delivered in {first_audio_latency:.0f}ms (final flush)")
                        first_chunk_sent = True
                
                # Send completion message
                await self.websocket.send({
                    "type": "audio_generation_complete",
                    "total_chunks": chunk_count,
                    "total_size": total_audio_size,
                    "first_chunk_latency": (time.time() - audio_start_time) * 1000 if first_chunk_sent else 0,
                    "message": "Chat audio ready to play!",
                    "request_id": data.get("request_id", "")
                })
                
                audio_total_time = (time.time() - audio_start_time) * 1000
                log(f"🏁 Chat audio streaming complete: {chunk_count} chunks, {total_audio_size} bytes in {audio_total_time:.0f}ms")
                
            except ConnectionClosed as e:
                log_disconnection(self.client_id, e, "during chat audio streaming")
                if is_normal_closure(e):
                    log(f"🔌 Client disconnected normally - chat audio streaming completed")
                else:
                    log(f"❌ Chat audio streaming interrupted by connection error")
                    self.conversation_metrics["errors"] += 1
            except Exception as e:
                log(f"❌ Chat audio generation error: {e}")
                self.conversation_metrics["errors"] += 1
                try:
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Chat audio generation failed: {str(e)}"
                    })
                except ConnectionClosed as conn_e:
                    log_disconnection(self.client_id, conn_e, "while sending error message")
                    return
            
            # Update metrics
            total_time = time.time() - request_start_time
            self.conversation_metrics["total_requests"] += 1
            self.conversation_metrics["chat_requests"] += 1
            self.conversation_metrics["total_response_time"] += total_time
            self.conversation_metrics["avg_response_time"] = (
                self.conversation_metrics["total_response_time"] / 
                self.conversation_metrics["total_requests"]
            )
            
            log(f"Chat with audio completed in {total_time:.2f}s")
            
        except ConnectionClosed as e:
            log_disconnection(self.client_id, e, "during chat with audio")
            if not is_normal_closure(e):
                self.conversation_metrics["errors"] += 1
            # Don't try to send error message if connection is closed
            return
        except Exception as e:
            log(f"❌ Error in chat with audio: {e}")
            self.conversation_metrics["errors"] += 1
            try:
                await self.websocket.send({
                    "type": "error",
                    "error": f"Chat processing failed: {str(e)}"
                })
            except ConnectionClosed as conn_e:
                log_disconnection(self.client_id, conn_e, "while sending error message")
                return

    async def handle_start_class(self, data: dict):
        """Handle class start requests with optimized content delivery and timeout handling."""
        request_start_time = time.time()
        
        try:
            course_id = data.get("course_id")
            module_index = data.get("module_index", 0)
            sub_topic_index = data.get("sub_topic_index", 0)
            language = data.get("language", self.current_language)
            
            log(f"Starting class: course={course_id}, module={module_index}, topic={sub_topic_index}")
            
            # Send immediate acknowledgment
            await self.websocket.send({
                "type": "class_starting",
                "message": "Loading course content...",
                "course_id": course_id,
                "module_index": module_index,
                "sub_topic_index": sub_topic_index,
                "request_id": data.get("request_id", "")
            })
            
            # Load and validate course content — DB primary, JSON fallback
            try:
                course_data = None
                
                # PRIMARY: Load from Neon database
                if self.database_service:
                    try:
                        log(f"Loading course {course_id} from Neon database...")
                        course_data = self.database_service.get_course_with_content(course_id)
                        if course_data:
                            log(f"✅ Found course from DB: {course_data.get('title', 'Unknown')}")
                    except Exception as db_err:
                        log(f"⚠️ DB load failed, trying JSON fallback: {db_err}")
                
                # FALLBACK: Load from JSON
                if not course_data:
                    course_data = await asyncio.wait_for(
                        self._load_course_data_async(course_id),
                        timeout=60.0
                    )
                
                if not course_data:
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Course {course_id} not found in database or JSON"
                    })
                    return
                
                # Validate indices
                modules = course_data.get("modules", [])
                if module_index >= len(modules):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Module {module_index} not found (available: 0-{len(modules)-1})"
                    })
                    return
                    
                module = modules[module_index]
                
                # DB uses 'topics', JSON uses 'sub_topics' — handle both
                sub_topics = module.get("topics", module.get("sub_topics", []))
                if sub_topic_index >= len(sub_topics):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Topic {sub_topic_index} not found (available: 0-{len(sub_topics)-1})"
                    })
                    return
                    
                sub_topic = sub_topics[sub_topic_index]
                
                # Send course info
                await self.websocket.send({
                    "type": "course_info",
                    "module_title": module['title'],
                    "sub_topic_title": sub_topic['title'],
                    "message": "Content loaded, generating teaching material...",
                    "request_id": data.get("request_id", "")
                })
                
                log(f"Course content loaded: {module['title']} -> {sub_topic['title']}")
                
            except asyncio.TimeoutError:
                log("Course content loading timeout")
                await self.websocket.send({
                    "type": "error",
                    "error": "Course content loading timeout"
                })
                return
            except Exception as e:
                log(f"Error loading course content: {e}")
                await self.websocket.send({
                    "type": "error",
                    "error": f"Failed to load course content: {str(e)}"
                })
                return
            
            # Generate teaching content with reduced timeout and better fallback
            try:
                raw_content = sub_topic.get('content', '')
                if not raw_content:
                    raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
                
                # Truncate content if too long to avoid timeout
                if len(raw_content) > 8000:
                    raw_content = raw_content[:7500] + "..."
                    log(f"Truncated content to 7500 chars for faster processing")
                
                # Check if teaching service is available
                if not self.services_available.get("teaching", False):
                    log("Teaching service not available, using direct content")
                    teaching_content = self._create_simple_teaching_content(
                        module['title'], sub_topic['title'], raw_content
                    )
                else:
                    # Try to generate with increased timeout
                    try:
                        teaching_content = await asyncio.wait_for(
                            self.teaching_service.generate_teaching_content(
                                module_title=module['title'],
                                sub_topic_title=sub_topic['title'],
                                raw_content=raw_content,
                                language=language
                            ),
                            timeout=60.0  # Increased to 60 seconds for LLM content generation
                        )
                    except asyncio.TimeoutError:
                        log("Teaching content generation timeout, using fallback")
                        teaching_content = self._create_simple_teaching_content(
                            module['title'], sub_topic['title'], raw_content
                        )
                
                if not teaching_content or len(teaching_content.strip()) == 0:
                    # Final fallback content
                    teaching_content = self._create_simple_teaching_content(
                        module['title'], sub_topic['title'], raw_content
                    )
                
                # Send teaching content
                await self.websocket.send({
                    "type": "teaching_content",
                    "content": teaching_content[:500] + "..." if len(teaching_content) > 500 else teaching_content,
                    "content_length": len(teaching_content),
                    "message": "Teaching content ready, starting audio...",
                    "request_id": data.get("request_id", "")
                })
                
                log(f"Teaching content ready: {len(teaching_content)} characters")
                
            except Exception as e:
                log(f"Error generating teaching content: {e}")
                # Use simple fallback content
                teaching_content = self._create_simple_teaching_content(
                    module['title'], sub_topic['title'], raw_content
                )
                
                await self.websocket.send({
                    "type": "teaching_content",
                    "content": teaching_content[:500] + "..." if len(teaching_content) > 500 else teaching_content,
                    "content_length": len(teaching_content),
                    "message": "Using fallback content, starting audio...",
                    "request_id": data.get("request_id", "")
                })
            
            # Generate audio with streaming
            await self.websocket.send({
                "type": "audio_generation_started",
                "message": "Generating class audio..."
            })
            
            try:
                # Accumulate small TTS chunks into larger buffers for gapless
                # playback.  At 32kbps MP3, 16 KB ≈ 4 s of audio.
                _MIN_SEND = 16_384  # 16 KB — same as teaching audio
                
                audio_start_time = time.time()
                chunk_count = 0
                total_audio_size = 0
                first_chunk_sent = False
                audio_buf = b''
                
                log(f"🚀 Starting REAL-TIME class audio streaming for: {teaching_content[:50]}...")
                
                import base64
                async for audio_chunk in self.audio_service.stream_audio_from_text(teaching_content, language, self.websocket):
                    if audio_chunk and len(audio_chunk) > 0:
                        audio_buf += audio_chunk
                        total_audio_size += len(audio_chunk)
                        
                        # Flush buffer when large enough
                        if len(audio_buf) >= _MIN_SEND:
                            chunk_count += 1
                            audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                            await self.websocket.send({
                                "type": "audio_chunk",
                                "chunk_id": chunk_count,
                                "audio_data": audio_base64,
                                "size": len(audio_buf),
                                "is_first_chunk": not first_chunk_sent,
                                "request_id": data.get("request_id", "")
                            })
                            audio_buf = b''
                            
                            if not first_chunk_sent:
                                first_audio_latency = (time.time() - audio_start_time) * 1000
                                log(f"🎯 FIRST CLASS AUDIO CHUNK delivered in {first_audio_latency:.0f}ms ({chunk_count} accumulated)")
                                first_chunk_sent = True
                
                # Flush remaining buffer
                if audio_buf:
                    chunk_count += 1
                    audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                    await self.websocket.send({
                        "type": "audio_chunk",
                        "chunk_id": chunk_count,
                        "audio_data": audio_base64,
                        "size": len(audio_buf),
                        "is_first_chunk": not first_chunk_sent,
                        "request_id": data.get("request_id", "")
                    })
                    if not first_chunk_sent:
                        first_audio_latency = (time.time() - audio_start_time) * 1000
                        log(f"🎯 FIRST CLASS AUDIO CHUNK delivered in {first_audio_latency:.0f}ms (final flush)")
                        first_chunk_sent = True
                
                # Send completion message
                await self.websocket.send({
                    "type": "audio_generation_complete",
                    "total_chunks": chunk_count,
                    "total_size": total_audio_size,
                    "first_chunk_latency": (time.time() - audio_start_time) * 1000 if first_chunk_sent else 0,
                    "message": "Class audio ready to play!",
                    "request_id": data.get("request_id", "")
                })
                
                audio_total_time = (time.time() - audio_start_time) * 1000
                log(f"🏁 Class audio streaming complete: {chunk_count} chunks, {total_audio_size} bytes in {audio_total_time:.0f}ms")
                
            except ConnectionClosed as e:
                log_disconnection(self.client_id, e, "during class audio streaming")
                if is_normal_closure(e):
                    log(f"🔌 Client disconnected normally - class audio streaming completed")
                else:
                    log(f"❌ Class audio streaming interrupted by connection error")
                    self.conversation_metrics["errors"] += 1
            except Exception as e:
                log(f"❌ Class audio generation error: {e}")
                self.conversation_metrics["errors"] += 1
                try:
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Class audio generation failed: {str(e)}"
                    })
                except ConnectionClosed as conn_e:
                    log_disconnection(self.client_id, conn_e, "while sending error message")
                    return
            
            # Update metrics
            total_time = time.time() - request_start_time
            self.conversation_metrics["total_requests"] += 1
            self.conversation_metrics["teaching_requests"] += 1
            self.conversation_metrics["total_response_time"] += total_time
            self.conversation_metrics["avg_response_time"] = (
                self.conversation_metrics["total_response_time"] / 
                self.conversation_metrics["total_requests"]
            )
            
            log(f"Class start completed in {total_time:.2f}s")
            
        except Exception as e:
            log(f"Error in start class: {e}")
            self.conversation_metrics["errors"] += 1
            await self.websocket.send({
                "type": "error",
                "error": f"Class processing failed: {str(e)}"
            })

    async def handle_interactive_teaching(self, data: dict):
        """Handle interactive teaching with two-way voice communication and barge-in support."""
        request_start_time = time.time()
        
        try:
            course_id = data.get("course_id")
            module_index = data.get("module_index", 0)
            sub_topic_index = data.get("sub_topic_index", 0)
            language = data.get("language", self.current_language)
            user_id = data.get("user_id") or self.user_id or f"ws_{self.client_id}"
            ip_address = data.get("ip_address") or self.ip_address or "127.0.0.1"
            user_agent = data.get("user_agent") or self.user_agent
            
            # Resolve professor persona for multi-voice + personality
            persona_id = data.get("persona_id") or getattr(config, "DEFAULT_PERSONA", "prof_sarah")
            personas = getattr(config, "PROFESSOR_PERSONAS", {})
            persona = personas.get(persona_id, {})
            voice_id = persona.get("voice_id")  # None → AudioService uses default
            
            log(f"Starting interactive teaching: course={course_id}, module={module_index}, topic={sub_topic_index}, persona={persona_id}, voice={voice_id[:8] + '...' if voice_id else 'default'}")
            
            # Get or create session for message persistence
            if self.session_manager:
                try:
                    session = self.session_manager.get_or_create_session(
                        user_id=user_id,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    self.session_id = session['session_id']
                    self.user_id = user_id
                    log(f"Session created/retrieved: {self.session_id}")
                except Exception as e:
                    log(f"Session creation failed: {e}")
            
            # Fetch username for personalised prompts
            user_name = ""
            if self.database_service and user_id:
                try:
                    user_info = self.database_service.get_user_by_id(int(user_id))
                    if user_info:
                        user_name = user_info.get('username', '')
                        log(f"👤 User: {user_name} (id={user_id})")
                except Exception as e:
                    log(f"⚠️ Could not fetch username: {e}")
            
            # Initialize orchestrator session (instant, no async init needed)
            thread_id = self.session_id or f"ws_{self.client_id}"
            
            orch_state = self.orchestrator.create_session(
                session_id=thread_id,
                user_id=user_id,
                course_id=course_id,
                module_index=module_index,
                sub_topic_index=sub_topic_index,
                module_title="",  # Set after loading
                sub_topic_title="",
                user_name=user_name,
                persona_id=persona_id,
            )
            
            # Initialize teaching session state (lightweight - for WebSocket management)
            self.teaching_session = {
                'active': True,
                'thread_id': thread_id,
                'course_id': course_id,
                'module_index': module_index,
                'sub_topic_index': sub_topic_index,
                'current_tts_task': None,
                'stt_service': None,
                'user_id': user_id,
                'user_name': user_name,
                'language': language,
                'last_latency_ms': 0,
                '_streaming_text': '',  # Track text currently being spoken (for barge-in resume)
                'persona_id': persona_id,
                'persona': persona,
                'voice_id': voice_id,
                # Mode: 'course_teaching' | 'query_resolution' | 'idle'
                'mode': 'course_teaching',
            }
            
            log(f"✅ Orchestrator session ready (thread_id: {thread_id})")
            
            # Send acknowledgment with persona info
            await self.websocket.send({
                "type": "interactive_teaching_init",
                "message": "Loading course content...",
                "course_id": course_id,
                "module_index": module_index,
                "sub_topic_index": sub_topic_index,
                "persona": {
                    "id": persona_id,
                    "name": persona.get("name", "Professor"),
                    "gender": persona.get("gender", ""),
                    "style": persona.get("style", ""),
                } if persona else None,
            })
            
            # Load course content from Neon PostgreSQL database (primary) with JSON fallback
            try:
                course_data = None
                
                # PRIMARY: Load from Neon database via DatabaseServiceV2
                if self.database_service:
                    try:
                        log(f"Loading course {course_id} from Neon database...")
                        course_data = self.database_service.get_course_with_content(course_id)
                        if course_data:
                            log(f"✅ Found course from DB: {course_data.get('title', 'Unknown')} (id={course_data.get('id')})")
                    except Exception as db_err:
                        log(f"⚠️ Database loading failed, will try JSON fallback: {db_err}")
                
                # FALLBACK: Load from JSON file if database unavailable
                if not course_data:
                    import os
                    import json as json_mod
                    log(f"Loading course {course_id} from JSON fallback...")
                    
                    if os.path.exists(config.OUTPUT_JSON_PATH):
                        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                            json_content = json_mod.load(f)
                        
                        if isinstance(json_content, dict) and ('course_title' in json_content or 'title' in json_content):
                            course_data = json_content
                        elif isinstance(json_content, list):
                            for c in json_content:
                                if str(c.get("course_id", c.get("id", ""))) == str(course_id):
                                    course_data = c
                                    break
                            if not course_data and json_content:
                                course_data = json_content[0]
                        
                        if course_data:
                            log(f"Found course from JSON: {course_data.get('course_title', course_data.get('title', 'Unknown'))}")
                
                if not course_data:
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Course {course_id} not found in database or JSON"
                    })
                    return
                
                # Validate module index — DB uses 'modules' same as JSON
                modules = course_data.get("modules", [])
                log(f"Course has {len(modules)} modules")
                
                if module_index >= len(modules):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Module {module_index} not found. Course has {len(modules)} modules (0-{len(modules)-1})"
                    })
                    return
                
                module = modules[module_index]
                
                # DB uses 'topics', JSON uses 'sub_topics' — handle both
                sub_topics = module.get("topics", module.get("sub_topics", []))
                log(f"Module '{module.get('title', 'Unknown')}' has {len(sub_topics)} topics")
                
                if sub_topic_index >= len(sub_topics):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Topic {sub_topic_index} not found. Module has {len(sub_topics)} topics (0-{len(sub_topics)-1})"
                    })
                    return
                
                sub_topic = sub_topics[sub_topic_index]
                module_title = module.get('title', 'Unknown Module')
                sub_topic_title = sub_topic.get('title', 'Unknown Topic')
                log(f"✅ Loaded: {module_title} → {sub_topic_title}")
                
                # Store course_data for auto-advance to next topic/module
                self.teaching_session['course_data'] = course_data
                
                # Rolling conversation context (last 6 exchanges) for LLM relevance
                self.teaching_session['conversation_context'] = []
                
                # Update orchestrator with titles + course structure counts
                orch_state = self.orchestrator.get_session(thread_id)
                if orch_state:
                    orch_state.module_title = module_title
                    orch_state.sub_topic_title = sub_topic_title
                    orch_state.total_modules = len(modules)
                    orch_state.total_sub_topics = len(sub_topics)
                
            except Exception as e:
                log(f"Error loading course content: {e}")
                import traceback
                traceback.print_exc()
                await self.websocket.send({
                    "type": "error",
                    "error": f"Failed to load course content: {str(e)}"
                })
                return
            
            # FAST content delivery: use raw content with minimal formatting
            # This eliminates the 5-10s LLM generation delay
            try:
                raw_content = sub_topic.get('content', '')
                if not raw_content:
                    raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
                
                if len(raw_content) > 8000:
                    raw_content = raw_content[:7500] + "..."
                
                # Use simple formatting for immediate delivery (<100ms)
                teaching_content = self._create_simple_teaching_content(
                    module['title'], sub_topic['title'], raw_content
                )
                
                self.teaching_session['teaching_content'] = teaching_content
                
                # Set content in orchestrator for segmented resume support
                self.orchestrator.set_content(thread_id, teaching_content, raw_content)
                
                log(f"✅ Teaching content ready ({len(teaching_content)} chars, {self.orchestrator.get_session(thread_id).total_segments} segments)")
                
                # BACKGROUND: Enhance content with LangGraph pedagogical LLM (non-blocking)
                # Raw content is delivered immediately; enhanced version replaces it when ready
                if self.orchestrator.langgraph_available:
                    async def _enhance_content_background():
                        try:
                            enhanced = await asyncio.get_event_loop().run_in_executor(
                                None,
                                self.orchestrator.generate_teaching_content_with_llm,
                                thread_id
                            )
                            if enhanced and len(enhanced) > 50:
                                self.orchestrator.set_content(thread_id, enhanced, raw_content)
                                self.teaching_session['teaching_content'] = enhanced
                                log(f"✅ LangGraph enhanced content ready ({len(enhanced)} chars)")
                        except Exception as e:
                            log(f"⚠️ Background content enhancement skipped: {e}")
                    
                    asyncio.create_task(_enhance_content_background())
                    log("🧠 LangGraph content enhancement started (background)")
                
            except Exception as e:
                log(f"Error preparing teaching content: {e}")
                teaching_content = f"Let's learn about {sub_topic.get('title', 'this topic')}."
                self.teaching_session['teaching_content'] = teaching_content
                self.orchestrator.set_content(thread_id, teaching_content)
            
            # Initialize Deepgram STT service for voice input
            try:
                from services.deepgram_stt_service import DeepgramSTTService
                stt_service = DeepgramSTTService(sample_rate=16000, language_hint=language)
                stt_started = await stt_service.start()
                
                if not stt_started:
                    log("⚠️ Deepgram STT not available, falling back to one-way teaching")
                    await self.websocket.send({
                        "type": "stt_unavailable",
                        "message": "Voice input not available. Using one-way teaching mode."
                    })
                    # Fallback to regular start_class
                    return await self.handle_start_class(data)
                
                self.teaching_session['stt_service'] = stt_service
                log("✅ Deepgram STT service initialized")
                
            except Exception as e:
                log(f"❌ Failed to initialize STT service: {e}")
                await self.websocket.send({
                    "type": "stt_unavailable",
                    "message": "Voice input initialization failed. Using one-way teaching."
                })
                return await self.handle_start_class(data)
            
            # Start STT event listener (background task)
            asyncio.create_task(self._handle_teaching_interruptions())
            log("🎤 STT interruption listener started")
            
            # Send ready message
            await self.websocket.send({
                "type": "interactive_teaching_started",
                "module_title": module['title'],
                "sub_topic_title": sub_topic['title'],
                "content_length": len(teaching_content),
                "message": "Interactive teaching ready! Speak anytime to ask questions.",
                "vad_mode": "hybrid"
            })
            
            log(f"📚 Starting interactive teaching: {module['title']} → {sub_topic['title']}")
            
            # Start teaching audio (cancellable)
            await self._stream_teaching_content(teaching_content, language)
            
        except Exception as e:
            log(f"Error in interactive teaching: {e}")
            self.conversation_metrics["errors"] += 1
            await self.websocket.send({
                "type": "error",
                "error": f"Interactive teaching failed: {str(e)}"
            })
    
    async def _handle_teaching_interruptions(self):
        """
        Listen for STT events and handle user interruptions during teaching.
        Uses RealtimeOrchestrator for fast intent classification and routing.
        """
        log("🎤 _handle_teaching_interruptions() task STARTED")
        
        if not self.teaching_session:
            log("❌ No teaching_session available in interruption handler")
            return
        
        stt_service = self.teaching_session.get('stt_service')
        if not stt_service:
            log("❌ No STT service available for interruptions")
            return
        
        thread_id = self.teaching_session.get('thread_id')
        log(f"✅ STT service found, thread_id={thread_id}")
        
        try:
            log("👂 Listening for teaching interruptions...")
            
            event_count = 0
            _last_real_activity = time.time()
            _idle_warned = False
            _IDLE_WARN_SECS = 300   # 5 min — send gentle nudge
            _IDLE_TIMEOUT_SECS = 600  # 10 min — auto-pause
            
            async for event in stt_service.recv():
                event_count += 1
                event_type = event.get('type')
                
                # Only log critical events at INFO level (not speech_started — fires on noise)
                if event_type in ['final', 'utterance_end']:
                    log(f"📨 Deepgram: {event_type}")
                elif event_type == 'partial':
                    log(f"📨 Deepgram: partial")
                else:
                    logging.debug(f"📨 Deepgram event #{event_count}: {event_type}")
                
                # --- Idle timeout check ---
                idle_secs = time.time() - _last_real_activity
                if idle_secs > _IDLE_TIMEOUT_SECS:
                    log(f"⏰ Teaching session idle for {idle_secs:.0f}s — auto-pausing")
                    try:
                        await self.websocket.send({
                            "type": "session_idle_timeout",
                            "message": "Session paused due to inactivity. Send a message to resume.",
                            "idle_seconds": int(idle_secs),
                        })
                    except Exception:
                        pass
                    break  # Exit STT loop — this effectively pauses the session
                elif idle_secs > _IDLE_WARN_SECS and not _idle_warned:
                    _idle_warned = True
                    try:
                        await self.websocket.send({
                            "type": "session_idle_warning",
                            "message": "Are you still there? The session will pause soon if there's no activity.",
                            "idle_seconds": int(idle_secs),
                        })
                    except Exception:
                        pass
                
                if event_type == 'speech_started':
                    # DON'T barge-in on speech_started alone — Deepgram VAD
                    # fires on ambient noise (fan, AC). Just note it; we'll
                    # confirm real speech when a partial/final transcript arrives.
                    self.teaching_session['_pending_barge_in'] = True
                    log("🗣️ SpeechStarted (pending barge-in confirmation)")
                
                elif event_type == 'partial':
                    partial_text = event.get('text', '')
                    if partial_text:
                        # Real text confirmed — NOW trigger barge-in if pending
                        if self.teaching_session.get('_pending_barge_in'):
                            self.teaching_session['_pending_barge_in'] = False
                            barge_in_start = time.time()
                            self.teaching_session['user_is_speaking'] = True
                            
                            # Capture text being spoken for resume
                            streaming_text = self.teaching_session.get('_streaming_text', '')
                            self.teaching_session['_streaming_text'] = ''
                            
                            # Stop teaching audio immediately (checked every iteration)
                            self.teaching_session['is_teaching'] = False
                            
                            # Cancel entire answer pipeline (LLM + TTS)
                            if self.teaching_session.get('current_answer_task'):
                                self.teaching_session['current_answer_task'].cancel()
                                self.teaching_session['current_answer_task'] = None
                            if self.teaching_session.get('current_tts_task'):
                                self.teaching_session['current_tts_task'].cancel()
                            
                            # Notify orchestrator (with text for resume)
                            self.orchestrator.on_barge_in(thread_id, streaming_text=streaming_text)
                            
                            # Switch mode: course_teaching → query_resolution
                            self.teaching_session['mode'] = 'query_resolution'
                            
                            # Notify client
                            try:
                                await self.websocket.send({
                                    "type": "user_interrupt_detected",
                                    "message": "Listening...",
                                    "mode": "query_resolution",
                                })
                                log(f"✅ Barge-in (confirmed by transcript) in {(time.time()-barge_in_start)*1000:.0f}ms")
                            except Exception as e:
                                log(f"❌ Failed to send interrupt notification: {e}")
                        
                        log(f"📝 Partial: {partial_text[:80]}")
                
                elif event_type == 'utterance_end':
                    # Reset pending barge-in — utterance ended without real text
                    self.teaching_session['_pending_barge_in'] = False
                    log("🔇 Utterance ended")
                
                elif event_type == 'final':
                    # User finished speaking - route via orchestrator (<5ms)
                    route_start = time.time()
                    self.teaching_session['user_is_speaking'] = False
                    self.teaching_session['_pending_barge_in'] = False
                    _last_real_activity = time.time()
                    _idle_warned = False
                    
                    user_input = event.get('text', '').strip()
                    if not user_input:
                        log("⚠️ Empty final transcript, skipping")
                        continue
                    
                    # Cancel any in-progress answer pipeline + TTS
                    streaming_text = self.teaching_session.get('_streaming_text', '')
                    self.teaching_session['_streaming_text'] = ''
                    self.teaching_session['is_teaching'] = False  # Stop chunk loop immediately
                    if self.teaching_session.get('current_answer_task'):
                        self.teaching_session['current_answer_task'].cancel()
                        self.teaching_session['current_answer_task'] = None
                    if self.teaching_session.get('current_tts_task'):
                        self.teaching_session['current_tts_task'].cancel()
                        self.orchestrator.on_barge_in(thread_id, streaming_text=streaming_text)
                        try:
                            await self.websocket.send({
                                "type": "user_interrupt_detected",
                                "message": "Listening..."
                            })
                        except Exception:
                            pass
                    
                    log(f"📝 User: {user_input}")
                    
                    # Echo to client immediately
                    try:
                        await self.websocket.send({
                            "type": "user_question",
                            "text": user_input
                        })
                    except Exception as e:
                        log(f"❌ Failed to send user_question: {e}")
                    
                    # ORCHESTRATOR ROUTING (<5ms, no LLM call)
                    route_t0 = time.time()
                    routing = self.orchestrator.process_user_input(thread_id, user_input)
                    action = routing.get('action', 'error')
                    intent = routing.get('intent', 'unknown')
                    route_ms = (time.time() - route_t0) * 1000
                    log(f"⚡ Orchestrator: intent={intent}, action={action} in {route_ms:.1f}ms")
                    
                    # Handle 'end' inline (needs to break the event loop)
                    if action == 'end':
                        await self.websocket.send({
                            "type": "teaching_ended",
                            "message": routing.get('message', "Session complete.")
                        })
                        break
                    
                    # Fire action as BACKGROUND TASK so the STT event loop
                    # never blocks during LLM generation (5-10s) or TTS.
                    self._schedule_action(action, routing, user_input, thread_id, save_user_msg=True)
                
                elif event_type == 'closed':
                    log("🔌 STT service closed")
                    break
        
        except asyncio.CancelledError:
            log("🛑 Interruption handler cancelled")
        except Exception as e:
            log(f"❌ CRITICAL ERROR in interruption handler: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
        finally:
            log("🏁 _handle_teaching_interruptions() task ENDED")
    
    async def _dispatch_action(self, act: str, rt: dict, ui: str, tid: str, save_user_msg: bool = False):
        """
        Shared action dispatcher for both STT and text-input paths.
        Handles all orchestrator actions with proper mode transitions.
        Runs as a background task; supports cancellation via barge-in.

        Args:
            act: Action name from orchestrator
            rt: Full routing dict from orchestrator
            ui: Original user input text
            tid: Thread/session ID
            save_user_msg: If True, persist user message to DB (STT path)
        """
        try:
            # Optionally persist user message (STT path does this here; text path does it before)
            if save_user_msg and self.session_manager and self.session_id and self.teaching_session:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.session_manager.add_message(
                            user_id=self.teaching_session['user_id'],
                            session_id=self.session_id,
                            role='user',
                            content=ui,
                            message_type='voice',
                            course_id=self.teaching_session['course_id']
                        )
                    )
                except Exception:
                    pass

            if act == 'continue_teaching':
                seg = rt.get('segment_text')
                if seg:
                    if self.teaching_session:
                        self.teaching_session['mode'] = 'course_teaching'
                    is_resume = rt.get('is_resume', False)
                    if is_resume:
                        await self.websocket.send({"type": "teaching_resumed", "message": "Resuming where we left off...", "mode": "course_teaching"})
                        seg = f"As I was saying, {seg}"
                    else:
                        await self.websocket.send({"type": "teaching_resumed", "message": "Continuing the lesson...", "mode": "course_teaching"})
                    await self._stream_teaching_content(seg, self.teaching_session['language'])
            elif act == 'pause':
                await self.websocket.send({"type": "teaching_paused", "message": rt.get('message', "Paused.")})
            elif act == 'repeat':
                seg = rt.get('segment_text')
                if seg:
                    if self.teaching_session:
                        self.teaching_session['mode'] = 'course_teaching'
                    await self.websocket.send({"type": "teaching_repeat", "message": "Let me repeat that...", "mode": "course_teaching"})
                    await self._stream_teaching_content(seg, self.teaching_session['language'])
            elif act == 'advance_next_topic':
                if self.teaching_session:
                    self.teaching_session['mode'] = 'course_teaching'
                await self._handle_advance_next_topic(tid, rt)
            elif act == 'course_complete':
                msg = rt.get('message', "You've completed the course!")
                await self.websocket.send({"type": "course_complete", "message": msg})
                await self._stream_answer_response(msg, "course_complete")
            elif act == 'ask_confirmation':
                msg = rt.get('message', "Should I mark this as complete?")
                await self.websocket.send({"type": "ask_confirmation", "message": msg})
                await self._stream_answer_response(msg, "confirmation")
            elif act == 'mark_complete':
                await self._handle_mark_complete()
                # After marking complete, offer to advance if there's a next topic/course
                if rt.get('has_next'):
                    orch_state = self.orchestrator.get_session(tid) if self.orchestrator else None
                    if orch_state:
                        import json as _json
                        name = orch_state.user_name or "there"
                        name = name.split('_')[0].capitalize() if '_' in name else name.capitalize()
                        orch_state.pending_action = "advance_next_topic"
                        orch_state.pending_action_data = _json.dumps({
                            "next_module_index": rt.get("next_module_index"),
                            "next_sub_topic_index": rt.get("next_sub_topic_index"),
                        })
                        orch_state.phase = "pending_confirmation"
                        follow_up = f"Great {name}, shall we move on to the next topic?"
                        await self.websocket.send({"type": "ask_confirmation", "message": follow_up})
                        await self._stream_answer_response(follow_up, "confirmation")
            elif act == 'mark_and_advance':
                await self._handle_mark_complete()
                await self._handle_advance_next_topic(tid, rt)
            elif act == 'mark_and_next_course':
                await self._handle_mark_complete()
                await self._handle_next_course()
            elif act == 'next_course':
                await self._handle_next_course()
            elif act == 'greeting':
                await self._stream_answer_response(rt.get('message', "Hello!"), "greeting")
            elif act in ('answer_with_rag', 'answer_general'):
                if self.teaching_session:
                    self.teaching_session['mode'] = 'query_resolution'
                await self._execute_answer_pipeline(tid, rt, ui)
            else:
                log(f"⚠️ Unknown action: {act}")
        except asyncio.CancelledError:
            log(f"🛑 Action '{act}' cancelled by barge-in")
        except Exception as e:
            log(f"❌ Error handling action '{act}': {e}")
            import traceback; traceback.print_exc()
            try:
                await self.websocket.send({"type": "error", "error": f"Failed to process: {str(e)}"})
            except Exception:
                pass
        finally:
            if self.teaching_session:
                self.teaching_session['current_answer_task'] = None

    def _schedule_action(self, act: str, rt: dict, ui: str, tid: str, save_user_msg: bool = False):
        """Schedule _dispatch_action as a cancellable background task."""
        task = asyncio.create_task(self._dispatch_action(act, rt, ui, tid, save_user_msg=save_user_msg))
        if self.teaching_session:
            self.teaching_session['current_answer_task'] = task
        return task

    async def _execute_answer_pipeline(self, thread_id: str, routing: dict, user_input: str):
        """
        Full answer pipeline with immediate audio acknowledgment:
          1. Send visual 'thinking' indicator + stream short filler TTS
          2. Generate LLM answer IN PARALLEL with filler audio
          3. When both done, stream the real answer TTS
        Runs as a background task; supports cancellation via barge-in.
        """
        log = lambda msg: logging.info(f"[WebSocket] {msg}")
        question = routing.get('question', user_input)
        use_rag = routing.get('needs_rag', False)
        
        # --- 1. Immediate feedback (visual + audio) ---
        import random, re as _re
        raw_name = (self.teaching_session.get('user_name', '') or '').strip()
        _parts = _re.split(r'[_\-.\s]+', raw_name) if raw_name else []
        first_name = _parts[0].capitalize() if _parts and _parts[0] else ""
        
        # Varied filler pool — some with name slot, some without
        _fillers_with_name = [
            f"Sure {first_name}, let me think about that.",
            f"Good question {first_name}. Give me a moment.",
            f"Hmm, interesting. One second {first_name}.",
            f"Let me look into that for you, {first_name}.",
        ]
        _fillers_no_name = [
            "Sure, let me think about that.",
            "Good question. Give me a moment.",
            "Hmm, let me think.",
            "One moment, let me put that together.",
            "Let me think about the best way to explain this.",
        ]
        # Use name ~40% of the time, if available
        if first_name and random.random() < 0.4:
            filler = random.choice(_fillers_with_name)
        else:
            filler = random.choice(_fillers_no_name)
        
        await self.websocket.send({
            "type": "thinking_acknowledgment",
            "message": filler,
        })
        
        # --- 2. Run filler TTS and LLM generation in parallel ---
        llm_task = asyncio.create_task(
            self._generate_llm_answer(thread_id, question, use_rag)
        )
        
        try:
            # Filler audio plays on client (~2-3s) while LLM generates (~5-10s)
            await self._stream_filler_tts(filler)
        except asyncio.CancelledError:
            llm_task.cancel()
            raise
        
        try:
            answer_text, answer_source, answer_ms = await llm_task
        except asyncio.CancelledError:
            raise
        
        log(f"💬 Answer [{answer_source}] in {answer_ms:.0f}ms: {answer_text[:80]}...")
        
        # --- Update rolling conversation context (max 6 exchanges) ---
        ctx = self.teaching_session.get('conversation_context', [])
        ctx.append({"role": "user", "content": question})
        ctx.append({"role": "assistant", "content": answer_text[:500]})  # truncate for prompt size
        if len(ctx) > 12:  # 6 exchanges × 2 messages
            ctx = ctx[-12:]
        self.teaching_session['conversation_context'] = ctx
        
        # --- 3. Send answer text to client ---
        await self.websocket.send(json.dumps({
            "type": "agent_response",
            "text": answer_text,
            "agent": answer_source,
            "answer_time_ms": round(answer_ms),
        }))
        
        # Notify orchestrator answer is complete
        self.orchestrator.on_answer_complete(thread_id, answer_text)
        
        # Save assistant response to DB (once)
        if self.session_manager and self.session_id:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session_manager.add_message(
                        user_id=self.teaching_session['user_id'],
                        session_id=self.session_id,
                        role='assistant',
                        content=answer_text,
                        message_type='voice',
                        course_id=self.teaching_session['course_id']
                    )
                )
            except Exception:
                pass
        
        # --- 4. Stream answer + resume prompt via TTS ---
        resume_prompt = self.orchestrator.get_resume_text(thread_id)
        full_response = f"{answer_text} {resume_prompt}"
        
        await self._stream_answer_response(
            full_response,
            "qa_rag" if use_rag else "qa_general",
            skip_text_send=True,  # Already sent above
        )
    
    async def _generate_llm_answer(self, thread_id: str, question: str, use_rag: bool):
        """
        Generate answer text through LLM tiers (LangGraph → RAG → General).
        Returns (answer_text, answer_source, duration_ms).
        """
        log = lambda msg: logging.info(f"[WebSocket] {msg}")
        answer_start = time.time()
        answer_text = ""
        answer_source = "unknown"
        
        # TIER 2: Try LangGraph pedagogical answer first
        conv_ctx = self.teaching_session.get('conversation_context', []) if self.teaching_session else []
        if self.orchestrator.langgraph_available:
            try:
                log("🧠 Tier 2: LangGraph pedagogical answer...")
                lg_answer = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self.orchestrator.answer_question_with_llm(
                            thread_id, question, conversation_context=conv_ctx
                        )
                    ),
                    timeout=10.0
                )
                if lg_answer and len(lg_answer.strip()) > 20:
                    answer_text = lg_answer
                    answer_source = "langgraph_pedagogical"
                    log(f"✅ LangGraph answer: {len(answer_text)} chars")
            except asyncio.TimeoutError:
                log("⚠️ LangGraph timeout, falling to Tier 1")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"⚠️ LangGraph error: {e}, falling to Tier 1")
        
        # TIER 1 FALLBACK: ChatService with RAG
        if not answer_text and use_rag and self.services_available.get("chat", False):
            try:
                log("📚 Tier 1: RAG fallback...")
                conversation_history = []
                if self.session_manager and self.session_id:
                    try:
                        conversation_history = self.session_manager.get_conversation_history(
                            self.session_id, limit=3
                        )
                    except Exception:
                        pass
                
                response_data = await asyncio.wait_for(
                    self.chat_service.ask_question(
                        question,
                        query_language_code=self.teaching_session['language'],
                        session_id=self.session_id,
                        conversation_history=conversation_history,
                        course_id=self.teaching_session['course_id']
                    ),
                    timeout=15.0
                )
                answer_text = response_data.get('answer', '')
                answer_source = "rag"
            except asyncio.TimeoutError:
                log("⚠️ RAG timeout, falling back to general LLM")
                use_rag = False
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"⚠️ RAG error: {e}, falling back to general LLM")
                use_rag = False
        
        # TIER 1 FALLBACK: General LLM
        if not answer_text and self.services_available.get("chat", False):
            try:
                log("🤖 Tier 1: General LLM fallback...")
                response_data = await asyncio.wait_for(
                    self.chat_service.ask_question(
                        question,
                        query_language_code=self.teaching_session['language'],
                        session_id=self.session_id,
                        conversation_history=[],
                        course_id=None
                    ),
                    timeout=15.0
                )
                answer_text = response_data.get('answer', '')
                answer_source = "general_llm"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log(f"⚠️ LLM error: {e}")
                answer_text = "I'm having trouble processing your question right now. Could you rephrase it?"
                answer_source = "fallback"
        
        if not answer_text:
            answer_text = "I apologize, but I couldn't process your question. Please try again."
            answer_source = "fallback"
        
        answer_ms = (time.time() - answer_start) * 1000
        return answer_text, answer_source, answer_ms
    
    async def _stream_filler_tts(self, filler_text: str):
        """
        Stream a short acknowledgment phrase via TTS.
        Awaits completion so the caller knows when filler audio is done.
        Sends chunks as 'answer_audio_chunk' so the client plays them
        seamlessly before the real answer audio.
        """
        try:
            if not self.audio_service or not self.teaching_session:
                return
            if self.teaching_session.get('user_is_speaking', False):
                return
            
            chunk_count = 0
            async for audio_chunk in self.audio_service.stream_audio_from_text(
                filler_text,
                self.teaching_session.get('language', self.current_language),
                self.websocket,
                voice_id=self.teaching_session.get('voice_id'),
            ):
                if self.teaching_session.get('user_is_speaking', False):
                    break
                if audio_chunk and len(audio_chunk) > 0:
                    audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                    await self.websocket.send({
                        "type": "answer_audio_chunk",
                        "chunk_id": chunk_count,
                        "audio_data": audio_base64,
                        "size": len(audio_chunk),
                        "agent": "thinking"
                    })
                    chunk_count += 1
            
            logging.info(f"[WebSocket] 💭 Filler TTS done: {chunk_count} chunks")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logging.info(f"[WebSocket] ⚠️ Filler TTS error (non-fatal): {e}")
    
    async def _handle_mark_complete(self):
        """Mark current topic/module as complete via the progress API."""
        if not self.teaching_session or not self.database_service:
            return
        try:
            user_id = self.teaching_session.get('user_id')
            course_id = self.teaching_session.get('course_id')
            module_idx = self.teaching_session.get('module_index', 0)
            topic_idx = self.teaching_session.get('sub_topic_index', 0)
            if user_id and course_id:
                # Resolve topic_id from course_data if available
                topic_title = ""
                course_data = self.teaching_session.get('course_data')
                if course_data:
                    modules = course_data.get("modules", [])
                    if module_idx < len(modules):
                        mod = modules[module_idx]
                        subs = mod.get("topics", mod.get("sub_topics", []))
                        if topic_idx < len(subs):
                            topic_title = subs[topic_idx].get("title", "")
                self.database_service.mark_topic_complete(
                    user_id=int(user_id),
                    course_id=int(course_id),
                    module_id=module_idx,
                    topic_id=topic_idx,
                )
                log(f"✅ Marked complete: course={course_id} module={module_idx} topic={topic_idx} ({topic_title})")
                await self.websocket.send({
                    "type": "progress_updated",
                    "message": f"Marked as complete: {topic_title or f'Module {module_idx+1}, Topic {topic_idx+1}'}",
                    "course_id": course_id,
                    "module_index": module_idx,
                    "topic_index": topic_idx,
                })
                # Also speak a short confirmation
                await self._stream_answer_response(
                    f"Done! I've marked that as complete.",
                    "progress"
                )
                # Fetch recommendations (non-blocking, best-effort)
                await self._send_recommendations_if_available()
        except Exception as e:
            log(f"⚠️ mark_topic_complete failed: {e}")
            await self.websocket.send({
                "type": "error",
                "error": f"Could not mark as complete: {str(e)}"
            })

    async def _send_recommendations_if_available(self):
        """Fetch and send learning recommendations to the client (best-effort)."""
        try:
            uid = self.teaching_session.get('user_id') if self.teaching_session else self.user_id
            if not uid:
                return
            # Reuse cached instance to avoid creating new DB connections per call
            if not hasattr(self, '_recommendation_service') or self._recommendation_service is None:
                from services.recommendation_service import RecommendationService
                self._recommendation_service = RecommendationService()
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._recommendation_service.get_recommendations, int(uid)
            )
            if result and 'error' not in result:
                await self.websocket.send({
                    "type": "recommendations",
                    "next_topics": result.get('next_topics', [])[:3],
                    "recommended_quizzes": result.get('recommended_quizzes', [])[:3],
                    "next_courses": result.get('next_courses', [])[:2],
                    "summary": result.get('summary', ''),
                })
                log(f"📊 Recommendations sent: {len(result.get('next_topics',[]))} topics, {len(result.get('recommended_quizzes',[]))} quizzes")
        except Exception as e:
            log(f"⚠️ Recommendations fetch failed (non-critical): {e}")

    async def _handle_next_course(self):
        """Load the next course from the database and start teaching it."""
        if not self.teaching_session or not self.database_service:
            return
        try:
            current_course_id = int(self.teaching_session.get('course_id', 0))
            all_courses = self.database_service.get_all_courses()
            if not all_courses:
                await self.websocket.send({
                    "type": "error",
                    "error": "No courses available."
                })
                return

            # Sort by id and find next
            sorted_courses = sorted(all_courses, key=lambda c: c.get('id', 0))
            next_course = None
            for c in sorted_courses:
                if c.get('id', 0) > current_course_id:
                    next_course = c
                    break

            if not next_course:
                await self.websocket.send({
                    "type": "all_courses_complete",
                    "message": "You've completed all available courses! Amazing work!"
                })
                await self._stream_answer_response(
                    "Congratulations! You've completed all available courses. That's an incredible achievement!",
                    "all_courses_complete"
                )
                return

            next_id = next_course.get('id')
            next_title = next_course.get('title', 'Unknown')
            log(f"⏭️ Switching to next course: {next_title} (id={next_id})")

            # Update course_id FIRST so any barge-in during loading uses correct course
            self.teaching_session['course_id'] = next_id

            # Load full course content
            course_data = self.database_service.get_course_with_content(next_id)
            if not course_data:
                await self.websocket.send({
                    "type": "error",
                    "error": f"Could not load course: {next_title}"
                })
                return

            # Update teaching session
            self.teaching_session['course_id'] = next_id
            self.teaching_session['course_data'] = course_data
            self.teaching_session['module_index'] = 0
            self.teaching_session['sub_topic_index'] = 0

            modules = course_data.get("modules", [])
            if not modules:
                await self.websocket.send({"type": "error", "error": "Course has no modules."})
                return

            first_mod = modules[0]
            sub_topics = first_mod.get("topics", first_mod.get("sub_topics", []))
            first_topic = sub_topics[0] if sub_topics else {}
            module_title = first_mod.get('title', 'Module 1')
            sub_topic_title = first_topic.get('title', 'Topic 1')

            # Update orchestrator
            tid = self.teaching_session['thread_id']
            self.orchestrator.advance_topic(
                session_id=tid,
                module_index=0,
                sub_topic_index=0,
                module_title=module_title,
                sub_topic_title=sub_topic_title,
                total_sub_topics=len(sub_topics),
            )
            orch_state = self.orchestrator.get_session(tid)
            if orch_state:
                orch_state.course_id = next_id
                orch_state.total_modules = len(modules)

            # Notify client
            await self.websocket.send({
                "type": "course_changed",
                "course_id": next_id,
                "course_title": next_title,
                "module_title": module_title,
                "sub_topic_title": sub_topic_title,
                "message": f"Starting new course: {next_title}"
            })

            # Prepare and stream first topic
            raw_content = first_topic.get('content', '')
            if not raw_content:
                raw_content = f"This topic covers {sub_topic_title} as part of {module_title}."
            if len(raw_content) > 8000:
                raw_content = raw_content[:7500] + "..."

            teaching_content = self._create_simple_teaching_content(
                module_title, sub_topic_title, raw_content
            )
            self.teaching_session['teaching_content'] = teaching_content
            self.orchestrator.set_content(tid, teaching_content, raw_content)

            first_segment = self.orchestrator.start_teaching(tid)
            if first_segment:
                await self._stream_teaching_content(first_segment, self.teaching_session['language'])
        except Exception as e:
            log(f"❌ _handle_next_course error: {e}")
            import traceback; traceback.print_exc()
            await self.websocket.send({
                "type": "error",
                "error": f"Failed to load next course: {str(e)}"
            })

    async def _handle_advance_next_topic(self, thread_id: str, routing: dict):
        """
        Auto-advance to the next sub-topic or module when all segments are done.
        Loads new content from the stored course_data and starts streaming.
        """
        next_mi = routing.get('next_module_index', 0)
        next_si = routing.get('next_sub_topic_index', 0)
        
        course_data = self.teaching_session.get('course_data')
        if not course_data:
            log("⚠️ No course_data stored, cannot advance")
            await self.websocket.send({
                "type": "error",
                "error": "Course data not available. Please restart the session."
            })
            return
        
        modules = course_data.get("modules", [])
        if next_mi >= len(modules):
            log(f"⚠️ Module index {next_mi} out of range ({len(modules)} modules)")
            await self.websocket.send({
                "type": "course_complete",
                "message": "You've completed all modules in this course!"
            })
            return
        
        module = modules[next_mi]
        sub_topics = module.get("topics", module.get("sub_topics", []))
        
        if next_si >= len(sub_topics):
            log(f"⚠️ Sub-topic index {next_si} out of range ({len(sub_topics)} topics)")
            await self.websocket.send({
                "type": "error",
                "error": "Topic not found. Please restart the session."
            })
            return
        
        sub_topic = sub_topics[next_si]
        module_title = module.get('title', 'Unknown Module')
        sub_topic_title = sub_topic.get('title', 'Unknown Topic')
        
        log(f"⏭️ Advancing to: {module_title} → {sub_topic_title}")
        
        # Notify client of topic change
        await self.websocket.send({
            "type": "topic_advanced",
            "module_index": next_mi,
            "sub_topic_index": next_si,
            "module_title": module_title,
            "sub_topic_title": sub_topic_title,
            "message": f"Moving on to: {sub_topic_title}"
        })
        
        # Update orchestrator state
        self.orchestrator.advance_topic(
            session_id=thread_id,
            module_index=next_mi,
            sub_topic_index=next_si,
            module_title=module_title,
            sub_topic_title=sub_topic_title,
            total_sub_topics=len(sub_topics),
        )
        
        # Update teaching_session indices
        self.teaching_session['module_index'] = next_mi
        self.teaching_session['sub_topic_index'] = next_si
        
        # Load and prepare new content
        raw_content = sub_topic.get('content', '')
        if not raw_content:
            raw_content = f"This topic covers {sub_topic_title} as part of {module_title}."
        if len(raw_content) > 8000:
            raw_content = raw_content[:7500] + "..."
        
        teaching_content = self._create_simple_teaching_content(
            module_title, sub_topic_title, raw_content
        )
        
        self.teaching_session['teaching_content'] = teaching_content
        self.orchestrator.set_content(thread_id, teaching_content, raw_content)
        
        log(f"✅ New topic content ready ({len(teaching_content)} chars, "
            f"{self.orchestrator.get_session(thread_id).total_segments} segments)")
        
        # Start streaming the first segment of the new topic
        first_segment = self.orchestrator.start_teaching(thread_id)
        if first_segment:
            await self._stream_teaching_content(first_segment, self.teaching_session['language'])
        else:
            log("⚠️ No content to stream for new topic")

    async def _stream_teaching_content(self, content: str, language: str):
        """Stream teaching audio with cancellation support for barge-in."""
        try:
            self.teaching_session['is_teaching'] = True
            self.teaching_session['_streaming_text'] = content  # Track for barge-in resume
            
            async def send_teaching_audio():
                # Accumulate small TTS chunks into larger buffers for gapless
                # playback.  At 32kbps MP3, 16 KB ≈ 4 s of audio — enough for
                # the browser to decode and queue seamlessly.
                _MIN_SEND = 16_384  # 16 KB minimum buffer before sending
                
                chunk_count = 0
                total_audio_size = 0
                audio_start_time = time.time()
                audio_buf = b''
                
                log(f"🎙️ Starting teaching audio stream ({len(content)} chars)")
                
                async for audio_chunk in self.audio_service.stream_audio_from_text(
                    content, language, self.websocket,
                    voice_id=self.teaching_session.get('voice_id'),
                ):
                    if not self.teaching_session.get('is_teaching', False):
                        log("🛑 Teaching interrupted by user - stopping audio")
                        await self.websocket.send({"type": "teaching_interrupted"})
                        return
                    
                    if audio_chunk and len(audio_chunk) > 0:
                        audio_buf += audio_chunk
                        total_audio_size += len(audio_chunk)
                        
                        # Flush buffer when large enough
                        if len(audio_buf) >= _MIN_SEND:
                            chunk_count += 1
                            audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                            await self.websocket.send({
                                "type": "teaching_audio_chunk",
                                "chunk_id": chunk_count,
                                "audio_data": audio_base64,
                                "size": len(audio_buf)
                            })
                            audio_buf = b''
                
                # Flush remaining bytes
                if audio_buf:
                    chunk_count += 1
                    audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                    await self.websocket.send({
                        "type": "teaching_audio_chunk",
                        "chunk_id": chunk_count,
                        "audio_data": audio_base64,
                        "size": len(audio_buf)
                    })
                
                await self.websocket.send({
                    "type": "teaching_segment_complete",
                    "total_chunks": chunk_count,
                    "total_size": total_audio_size,
                    "duration_ms": (time.time() - audio_start_time) * 1000,
                    "message": "Section complete. Ask questions or say 'continue' to proceed."
                })
                
                self.teaching_session['is_teaching'] = False
                self.teaching_session['_streaming_text'] = ''  # Clear — delivered successfully
                log(f"✅ Teaching audio complete: {chunk_count} chunks, {total_audio_size} bytes")
                
                # Advance segment index so next 'continue' loads the next segment
                thread_id = self.teaching_session.get('thread_id')
                if thread_id:
                    self.orchestrator.advance_segment(thread_id)
            
            # Create cancellable task — DON'T await!
            # The interruption handler must keep consuming STT events during playback.
            tts_task = asyncio.create_task(send_teaching_audio())
            self.teaching_session['current_tts_task'] = tts_task
            
            def _on_teaching_tts_done(task):
                if self.teaching_session:
                    self.teaching_session['current_tts_task'] = None
                if task.cancelled():
                    log("Teaching TTS task cancelled")
                    if self.teaching_session:
                        self.teaching_session['is_teaching'] = False
                elif task.exception():
                    log(f"❌ Teaching TTS error: {task.exception()}")
                    if self.teaching_session:
                        self.teaching_session['is_teaching'] = False
                    # Notify client of TTS failure so they know teaching didn't complete
                    try:
                        asyncio.get_event_loop().call_soon_threadsafe(
                            asyncio.ensure_future,
                            self.websocket.send({"type": "error", "error": "Audio streaming failed. Say 'continue' to retry."})
                        )
                    except Exception:
                        pass
            tts_task.add_done_callback(_on_teaching_tts_done)
        
        except asyncio.CancelledError:
            log("Teaching audio streaming cancelled by user")
            await self.websocket.send({"type": "teaching_cancelled"})
        except Exception as e:
            log(f"Error streaming teaching content: {e}")
            self.teaching_session['is_teaching'] = False
    
    async def _stream_answer_response(self, response_text: str, agent_name: str, skip_text_send: bool = False):
        """
        Stream answer response via TTS with low latency and barge-in support.
        Sends text immediately (unless skip_text_send), then streams audio asynchronously.
        """
        stream_start = time.time()
        
        try:
            log(f"🎤 Streaming {agent_name} response ({len(response_text)} chars)")
            
            # Track for barge-in resume
            if self.teaching_session:
                self.teaching_session['_streaming_text'] = response_text
            
            if not skip_text_send:
                # Send text response FIRST (user sees immediately)
                await self.websocket.send({
                    "type": "agent_response",
                    "text": response_text,
                    "agent": agent_name,
                    "timestamp": time.time()
                })
                
                log(f"⚡ Text sent in {(time.time()-stream_start)*1000:.0f}ms")
                
                # Save to database (non-blocking — runs in thread pool)
                if self.session_manager and self.session_id and self.teaching_session:
                    try:
                        _uid = self.teaching_session.get('user_id', '')
                        _cid = self.teaching_session.get('course_id')
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: self.session_manager.add_message(
                                user_id=_uid,
                                session_id=self.session_id,
                                role='assistant',
                                content=response_text,
                                message_type='voice',
                                course_id=_cid,
                                metadata={'agent': agent_name}
                            )
                        )
                    except Exception:
                        pass
            
            # Stream audio (cancellable for barge-in)
            async def send_audio_chunks():
                if not self.teaching_session:
                    return
                if self.teaching_session.get('user_is_speaking', False):
                    log("🛑 Skipping TTS: user is speaking")
                    return
                
                _MIN_SEND = 16_384  # 16 KB — same as teaching audio
                chunk_count = 0
                audio_start = time.time()
                audio_buf = b''
                
                try:
                    async for audio_chunk in self.audio_service.stream_audio_from_text(
                        response_text,
                        self.teaching_session.get('language', self.current_language),
                        self.websocket,
                        voice_id=self.teaching_session.get('voice_id'),
                    ):
                        if self.teaching_session.get('user_is_speaking', False):
                            log("🛑 TTS interrupted: user speaking")
                            break
                        
                        if audio_chunk and len(audio_chunk) > 0:
                            audio_buf += audio_chunk
                            
                            if len(audio_buf) >= _MIN_SEND:
                                chunk_count += 1
                                audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                                await self.websocket.send({
                                    "type": "answer_audio_chunk",
                                    "chunk_id": chunk_count,
                                    "audio_data": audio_base64,
                                    "size": len(audio_buf),
                                    "agent": agent_name
                                })
                                audio_buf = b''
                    
                    # Flush remaining
                    if audio_buf:
                        chunk_count += 1
                        audio_base64 = base64.b64encode(audio_buf).decode('utf-8')
                        await self.websocket.send({
                            "type": "answer_audio_chunk",
                            "chunk_id": chunk_count,
                            "audio_data": audio_base64,
                            "size": len(audio_buf),
                            "agent": agent_name
                        })
                    
                    audio_ms = (time.time() - audio_start) * 1000
                    log(f"✅ Answer audio: {chunk_count} chunks in {audio_ms:.0f}ms")
                    
                    await self.websocket.send({
                        "type": "answer_audio_complete",
                        "agent": agent_name,
                        "chunk_count": chunk_count,
                        "duration_ms": audio_ms
                    })
                    
                except asyncio.CancelledError:
                    log(f"🛑 Answer audio cancelled for {agent_name}")
                    raise
                except Exception as e:
                    log(f"❌ Answer audio error: {e}")
            
            # Create cancellable TTS task — DON'T await it!
            # The interruption handler must keep consuming STT events during playback.
            # If we await here, the handler blocks and user speech queues up unseen.
            tts_task = asyncio.create_task(send_audio_chunks())
            if self.teaching_session:
                self.teaching_session['current_tts_task'] = tts_task
            
            _start = stream_start  # capture for callback
            def _on_answer_tts_done(task):
                if self.teaching_session:
                    self.teaching_session['current_tts_task'] = None
                    self.teaching_session['_streaming_text'] = ''  # Clear after delivery/cancel
                if task.cancelled():
                    log("Answer TTS cancelled")
                elif task.exception():
                    log(f"❌ Answer TTS error: {task.exception()}")
                else:
                    log(f"⚡ Total answer latency: {(time.time()-_start)*1000:.0f}ms")
            tts_task.add_done_callback(_on_answer_tts_done)
            
        except asyncio.CancelledError:
            log("🛑 Answer streaming cancelled")
        except Exception as e:
            log(f"❌ Answer streaming error: {e}")
            try:
                await self.websocket.send({
                    "type": "error",
                    "error": f"Response streaming failed: {str(e)}"
                })
            except Exception:
                pass
    
    def _create_simple_teaching_content(self, module_title: str, topic_title: str, raw_content: str) -> str:
        """
        Create simple teaching content as fallback when teaching service is unavailable.
        
        Args:
            module_title: Module name
            topic_title: Sub-topic name
            raw_content: Raw content from JSON
        
        Returns:
            Formatted teaching content string
        """
        # Personalise greeting with username and persona
        user_name = ""
        persona_name = ""
        if self.teaching_session:
            user_name = self.teaching_session.get('user_name', '')
            persona = self.teaching_session.get('persona', {})
            persona_name = persona.get('name', '')
        intro = f"I'm {persona_name}. " if persona_name else ""
        greeting = f"{intro}Hey {user_name}, let's" if user_name else f"{intro}Let's"
        
        content = f"{greeting} learn about {topic_title} in the {module_title} module.\n\n"
        
        # Add raw content with basic formatting
        if raw_content and len(raw_content.strip()) > 0:
            # Split into paragraphs — include ALL content; the segmenter handles chunking for TTS
            paragraphs = raw_content.strip().split('\n\n')
            for para in paragraphs:
                if para.strip():
                    content += para.strip() + "\n\n"
        else:
            content += "This topic covers important concepts that we'll explore together.\n\n"
        
        content += "Feel free to ask questions or say 'continue' when you're ready to proceed."
        
        return content

    async def handle_stt_audio_chunk(self, data: dict):
        """Receive audio chunk from client and forward to Deepgram STT service."""
        # Check if teaching session active with STT service
        if not self.teaching_session or not self.teaching_session.get('stt_service'):
            return
        
        audio_base64 = data.get('audio')
        if not audio_base64:
            return
        
        try:
            # Decode base64 to PCM16 bytes
            import base64
            pcm_bytes = base64.b64decode(audio_base64)
            
            # Track audio chunk count for diagnostics
            chunk_count = self.teaching_session.get('_audio_chunk_count', 0) + 1
            self.teaching_session['_audio_chunk_count'] = chunk_count
            if chunk_count == 1:
                log(f"🎤 First audio chunk received ({len(pcm_bytes)} bytes) — forwarding to Deepgram")
            elif chunk_count % 500 == 0:
                log(f"🎤 Audio chunks forwarded: {chunk_count}")
            
            # Forward to Deepgram
            await self.teaching_session['stt_service'].send_audio_chunk(pcm_bytes)
            
        except Exception as e:
            log(f"Error forwarding audio to STT: {e}")
    
    async def handle_teaching_user_input(self, data: dict):
        """
        Handle direct text input during an interactive teaching session.
        This bypasses STT and injects user text into the orchestrator pipeline,
        enabling button-driven actions (mark complete, next course, yes/no).
        """
        if not self.teaching_session or not self.teaching_session.get('active'):
            await self.websocket.send({"type": "error", "error": "No active teaching session"})
            return

        user_input = (data.get('text') or '').strip()
        if not user_input:
            return

        thread_id = self.teaching_session.get('thread_id')
        if not thread_id:
            return

        log(f"📝 Text input: {user_input}")

        # Cancel any in-progress TTS / answer so we can process the new input
        streaming_text = self.teaching_session.get('_streaming_text', '')
        self.teaching_session['_streaming_text'] = ''
        self.teaching_session['is_teaching'] = False
        if self.teaching_session.get('current_answer_task'):
            self.teaching_session['current_answer_task'].cancel()
            self.teaching_session['current_answer_task'] = None
        if self.teaching_session.get('current_tts_task'):
            self.teaching_session['current_tts_task'].cancel()
            self.orchestrator.on_barge_in(thread_id, streaming_text=streaming_text)

        # Echo to client
        try:
            await self.websocket.send({"type": "user_question", "text": user_input})
        except Exception:
            pass

        # Orchestrator routing
        routing = self.orchestrator.process_user_input(thread_id, user_input)
        action = routing.get('action', 'error')
        intent = routing.get('intent', 'unknown')
        log(f"⚡ Text input → intent={intent}, action={action}")

        # Handle 'end' inline
        if action == 'end':
            await self.websocket.send({
                "type": "teaching_ended",
                "message": routing.get('message', "Session complete.")
            })
            return

        # Persist user message (non-blocking — runs in thread pool)
        if self.session_manager and self.session_id:
            try:
                _uid = self.teaching_session.get('user_id', self.user_id)
                _cid = self.teaching_session.get('course_id')
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.session_manager.add_message(
                        user_id=_uid,
                        session_id=self.session_id,
                        role='user',
                        content=user_input,
                        message_type='text',
                        course_id=_cid
                    )
                )
            except Exception:
                pass

        # Fire action as background task (uses shared dispatcher with mode transitions)
        self._schedule_action(action, routing, user_input, thread_id)

    async def handle_continue_teaching(self, data: dict):
        """Resume teaching after user Q&A - resumes from current segment, not beginning."""
        if not self.teaching_session or not self.teaching_session.get('active'):
            await self.websocket.send({
                "type": "error",
                "error": "No active teaching session"
            })
            return
        
        thread_id = self.teaching_session.get('thread_id')
        language = self.teaching_session.get('language', self.current_language)
        
        # Use orchestrator to get current segment (resume from where we left off)
        segment_text = None
        if thread_id and self.orchestrator:
            segment_text = self.orchestrator.start_teaching(thread_id)
        
        # Fallback to full content if orchestrator has no segments
        if not segment_text:
            segment_text = self.teaching_session.get('teaching_content')
        
        if not segment_text:
            await self.websocket.send({
                "type": "error",
                "error": "No teaching content available"
            })
            return
        
        log(f"📖 Resuming teaching from segment (orchestrator)...")
        
        if self.teaching_session:
            self.teaching_session['mode'] = 'course_teaching'
        
        await self.websocket.send({
            "type": "teaching_resumed",
            "message": "Continuing the lesson...",
            "mode": "course_teaching",
        })
        
        # Resume teaching audio from current segment
        await self._stream_teaching_content(segment_text, language)
    
    async def handle_end_teaching(self, data: dict):
        """End teaching session and cleanup resources."""
        if not self.teaching_session:
            return
        
        log("🛑 Ending teaching session...")
        
        # Stop STT service
        if self.teaching_session.get('stt_service'):
            try:
                await self.teaching_session['stt_service'].close()
                log("✅ STT service closed")
            except Exception as e:
                log(f"Error closing STT service: {e}")
        
        # Cancel any ongoing TTS
        if self.teaching_session.get('current_tts_task'):
            try:
                self.teaching_session['current_tts_task'].cancel()
                log("✅ TTS task cancelled")
            except Exception as e:
                log(f"Error cancelling TTS: {e}")
        
        # Cleanup orchestrator session
        thread_id = self.teaching_session.get('thread_id')
        if thread_id and self.orchestrator:
            self.orchestrator.cleanup(thread_id)
        
        # Mark session as inactive
        self.teaching_session['active'] = False
        self.teaching_session = None
        
        # Fetch recommendations for the student (non-blocking, best-effort)
        recommendations = None
        if self.user_id:
            try:
                from services.recommendation_service import RecommendationService
                rec_service = RecommendationService()
                recommendations = await asyncio.get_event_loop().run_in_executor(
                    None, rec_service.get_recommendations, int(self.user_id)
                )
                if recommendations and "error" in recommendations:
                    recommendations = None
            except Exception as e:
                log(f"⚠️ Recommendations fetch failed (non-fatal): {e}")
        
        end_payload = {
            "type": "teaching_ended",
            "message": "Teaching session completed successfully"
        }
        if recommendations:
            end_payload["recommendations"] = {
                "summary": recommendations.get("summary", ""),
                "next_topics": recommendations.get("next_topics", [])[:3],
                "recommended_quizzes": recommendations.get("recommended_quizzes", [])[:3],
                "weak_modules": recommendations.get("weak_modules", [])[:3],
                "next_courses": recommendations.get("next_courses", [])[:2],
            }
        
        await self.websocket.send(end_payload)
        
        log("✅ Teaching session ended")

    async def handle_audio_only(self, data: dict):
        """Handle audio-only generation requests."""
        request_start_time = time.time()
        
        try:
            text = data.get("text")
            language = data.get("language", self.current_language)
            
            if not text:
                await self.websocket.send({
                    "type": "error",
                    "error": "Text is required"
                })
                return
            
            log(f"Processing audio-only request: {len(text)} chars")
            
            await self.websocket.send({
                "type": "audio_generation_started",
                "message": "Generating audio...",
                "request_id": data.get("request_id", "")
            })
            
            try:
                # OPTIMIZED streaming for sub-300ms latency (consistent with chat_with_audio)
                audio_start_time = time.time()
                chunk_count = 0
                total_audio_size = 0
                first_chunk_sent = False
                
                log(f"🚀 Starting REAL-TIME audio-only streaming for: {text[:50]}...")
                
                # Resolve voice_id from request or teaching session
                _ao_voice_id = data.get("voice_id")
                if not _ao_voice_id and self.teaching_session:
                    _ao_voice_id = self.teaching_session.get('voice_id')
                
                async for audio_chunk in self.audio_service.stream_audio_from_text(text, language, self.websocket, voice_id=_ao_voice_id):
                    if audio_chunk and len(audio_chunk) > 0:
                        chunk_count += 1
                        total_audio_size += len(audio_chunk)
                        
                        # Convert to base64 for JSON transmission
                        import base64
                        audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                        
                        # Send chunk immediately
                        await self.websocket.send({
                            "type": "audio_chunk",
                            "chunk_id": chunk_count,
                            "audio_data": audio_base64,
                            "size": len(audio_chunk),
                            "is_first_chunk": not first_chunk_sent,
                            "request_id": data.get("request_id", "")
                        })
                        
                        # Log first chunk latency (CRITICAL METRIC - consistent with chat)
                        if not first_chunk_sent:
                            first_audio_latency = (time.time() - audio_start_time) * 1000
                            log(f"🎯 FIRST AUDIO-ONLY CHUNK delivered in {first_audio_latency:.0f}ms")
                            
                            if first_audio_latency <= 300:
                                log(f"🎉 TARGET ACHIEVED! Sub-300ms latency: {first_audio_latency:.0f}ms")
                            elif first_audio_latency <= 900:
                                log(f"✅ GOOD latency: {first_audio_latency:.0f}ms (under 900ms target)")
                            else:
                                log(f"⚠️ HIGH latency: {first_audio_latency:.0f}ms (needs optimization)")
                            
                            first_chunk_sent = True
                        else:
                            # Log subsequent chunks
                            chunk_time = (time.time() - audio_start_time) * 1000
                            log(f"   Chunk {chunk_count}: {len(audio_chunk)} bytes at {chunk_time:.0f}ms")
                
                # Send completion message
                await self.websocket.send({
                    "type": "audio_generation_complete",
                    "total_chunks": chunk_count,
                    "total_size": total_audio_size,
                    "first_chunk_latency": (time.time() - audio_start_time) * 1000 if first_chunk_sent else 0,
                    "request_id": data.get("request_id", "")
                })
                
                audio_total_time = (time.time() - audio_start_time) * 1000
                log(f"🏁 Audio-only streaming complete: {chunk_count} chunks, {total_audio_size} bytes in {audio_total_time:.0f}ms")
                
            except ConnectionClosed as e:
                log_disconnection(self.client_id, e, "during audio-only streaming")
                if is_normal_closure(e):
                    log(f"🔌 Client disconnected normally - audio-only streaming completed")
                else:
                    log(f"❌ Audio-only streaming interrupted by connection error")
                    self.conversation_metrics["errors"] += 1
            except Exception as e:
                log(f"❌ Audio-only generation error: {e}")
                self.conversation_metrics["errors"] += 1
                try:
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Audio generation failed: {str(e)}"
                    })
                except ConnectionClosed as conn_e:
                    log_disconnection(self.client_id, conn_e, "while sending error message")
                    return
            
            # Update metrics
            total_time = time.time() - request_start_time
            self.conversation_metrics["total_requests"] += 1
            self.conversation_metrics["audio_requests"] += 1
            self.conversation_metrics["total_response_time"] += total_time
            self.conversation_metrics["avg_response_time"] = (
                self.conversation_metrics["total_response_time"] / 
                self.conversation_metrics["total_requests"]
            )
            
            log(f"Audio-only completed in {total_time:.2f}s")
            
        except Exception as e:
            log(f"Error in audio-only: {e}")
            self.conversation_metrics["errors"] += 1
            await self.websocket.send({
                "type": "error",
                "error": f"Audio processing failed: {str(e)}"
            })

    def _is_websocket_connected(self):
        """Safely check if WebSocket connection is still active."""
        try:
            if not hasattr(self, 'websocket') or not self.websocket:
                return False
            
            # Try different ways to check connection status
            websocket_obj = getattr(self.websocket, 'websocket', None)
            if websocket_obj:
                # Check for closed attribute
                if hasattr(websocket_obj, 'closed'):
                    return not websocket_obj.closed
                # Check for state attribute (websockets library)
                if hasattr(websocket_obj, 'state'):
                    # State 1 = OPEN, others are closed/closing
                    return websocket_obj.state == 1
            
            # If we can't determine status, assume connected to continue processing
            return True
            
        except Exception as e:
            log(f"Error checking WebSocket status: {e}")
            # On error, assume disconnected for safety
            return False

    async def _load_course_data_async(self, course_id=None):
        """Load course data asynchronously with proper error handling."""
        try:
            import os
            import json
            import config
            
            # Load from the same path as the HTTP endpoints use
            if os.path.exists(config.OUTPUT_JSON_PATH):
                with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                
                # Handle both single course (dict) and multi-course (list) formats
                course_obj = None
                if isinstance(loaded, dict) and 'course_title' in loaded:
                    # Single course format
                    course_obj = loaded
                elif isinstance(loaded, list):
                    # Multi-course format: find by course_id if provided, else use first course
                    if course_id is not None:
                        for c in loaded:
                            if str(c.get("course_id", "")) == str(course_id):
                                course_obj = c
                                break
                    # Fallback to first course if not found
                    if course_obj is None and len(loaded) > 0:
                        course_obj = loaded[0]
                else:
                    log(f"Invalid course data format in {config.OUTPUT_JSON_PATH}; using fallback")
                    return self._create_fallback_course_data()

                # Ensure course_id is set if provided
                if course_obj is not None and course_id is not None:
                    course_obj["course_id"] = course_id

                # Log safely
                modules_len = len(course_obj.get('modules', [])) if isinstance(course_obj, dict) else 0
                log(f"Course data loaded from {config.OUTPUT_JSON_PATH}: {modules_len} modules")
                return course_obj
            
            # Try to load from the document service as secondary option
            if hasattr(self, 'document_service') and self.document_service:
                try:
                    courses_list = await self.document_service.get_all_courses()
                    if courses_list and len(courses_list) > 0:
                        course = None
                        if course_id is not None:
                            for c in courses_list:
                                if str(c.get("course_id", "")) == str(course_id):
                                    course = c
                                    break
                        if course is None:
                            course = courses_list[0]
                        if course_id is not None:
                            course["course_id"] = course_id
                        log(f"Course data loaded from document service: {len(course.get('modules', []))} modules")
                        return course
                except Exception as e:
                    log(f"Document service course loading failed: {e}")
            
            # Final fallback
            log(f"No course data found at {config.OUTPUT_JSON_PATH}, using fallback")
            return self._create_fallback_course_data()
        
        except Exception as e:
            log(f"Error loading course data: {e}")
            return self._create_fallback_course_data()
    
    def _create_fallback_course_data(self):
        """Create fallback course data when files are not available."""
        return {
            "course_id": "fallback_course",
            "course_title": "Sample Educational Course",
            "modules": [
                {
                    "title": "Introduction to Learning",
                    "sub_topics": [
                        {
                            "title": "Getting Started",
                            "content": "Welcome to this educational journey. In this introduction, we will explore the fundamentals of learning and how to make the most of your educational experience. Learning is a continuous process that involves acquiring new knowledge, skills, and understanding through study, experience, or teaching."
                        },
                        {
                            "title": "Study Methods", 
                            "content": "Effective study methods are crucial for academic success. Some proven techniques include active reading, note-taking, spaced repetition, and practice testing. These methods help improve retention and understanding of the material."
                        }
                    ]
                },
                {
                    "title": "Core Concepts",
                    "sub_topics": [
                        {
                            "title": "Fundamental Principles",
                            "content": "Understanding fundamental principles is essential for building a strong foundation in any subject. These principles serve as the building blocks for more advanced concepts and applications."
                        }
                    ]
                }
            ]
        }

    async def handle_transcribe_audio(self, data: dict):
        """Handle audio transcription requests."""
        try:
            audio_data = data.get("audio_data")  # Base64 encoded audio
            language = data.get("language", self.current_language)
            
            if not audio_data:
                await self.websocket.send({
                    "type": "error",
                    "error": "Audio data is required"
                })
                return
            
            log(f"Processing audio transcription request")
            
            await self.websocket.send({
                "type": "transcription_started",
                "message": "Transcribing audio...",
                "request_id": data.get("request_id", "")
            })
            
            try:
                # Decode base64 audio data
                import base64
                import io
                audio_bytes = base64.b64decode(audio_data)
                audio_buffer = io.BytesIO(audio_bytes)
                
                # Transcribe audio
                transcribed_text = await asyncio.wait_for(
                    self.audio_service.transcribe_audio(audio_buffer, language),
                    timeout=60.0  # 60 second timeout for audio transcription
                )
                
                if not transcribed_text:
                    await self.websocket.send({
                        "type": "error",
                        "error": "Could not transcribe audio"
                    })
                    return
                
                await self.websocket.send({
                    "type": "transcription_complete",
                    "transcribed_text": transcribed_text,
                    "request_id": data.get("request_id", "")
                })
                
                log(f"Transcription complete: {transcribed_text[:50]}...")
                
            except asyncio.TimeoutError:
                await self.websocket.send({
                    "type": "error",
                    "error": "Transcription timeout"
                })
            except Exception as e:
                log(f"Transcription error: {e}")
                await self.websocket.send({
                    "type": "error",
                    "error": f"Transcription failed: {str(e)}"
                })
            
        except Exception as e:
            log(f"Error in transcribe audio: {e}")
            await self.websocket.send({
                "type": "error",
                "error": f"Transcription processing failed: {str(e)}"
            })

    async def handle_set_language(self, data: dict):
        """Handle language setting requests."""
        try:
            language = data.get("language")
            if not language:
                await self.websocket.send({
                    "type": "error",
                    "error": "Language is required"
                })
                return
            
            self.current_language = language
            
            await self.websocket.send({
                "type": "language_set",
                "language": language,
                "message": f"Language set to {language}",
                "request_id": data.get("request_id", "")
            })
            
            log(f"Language set to {language} for client {self.client_id}")
            
        except Exception as e:
            log(f"Error setting language: {e}")
            await self.websocket.send({
                "type": "error",
                "error": f"Language setting failed: {str(e)}"
            })

    async def handle_get_metrics(self, data: dict):
        """Handle metrics requests."""
        try:
            session_duration = time.time() - self.session_start_time
            
            metrics = {
                "session_metrics": {
                    "session_duration": session_duration,
                    "client_id": self.client_id,
                    "current_language": self.current_language,
                    "message_count": self.websocket.message_count
                },
                "performance_metrics": self.conversation_metrics,
                "timestamp": time.time()
            }
            
            await self.websocket.send({
                "type": "metrics_response",
                "metrics": metrics,
                "request_id": data.get("request_id", "")
            })
            
        except Exception as e:
            log(f"Error getting metrics: {e}")
            await self.websocket.send({
                "type": "error",
                "error": f"Metrics retrieval failed: {str(e)}"
            })

    async def cleanup(self):
        """Cleanup resources when connection closes."""
        try:
            session_duration = time.time() - self.session_start_time
            log(f"Cleaning up client {self.client_id} after {session_duration:.2f}s")
            
            # --- Stop teaching session resources ---
            if self.teaching_session:
                # Cancel in-flight answer/TTS tasks
                for task_key in ('current_answer_task', 'current_tts_task'):
                    task = self.teaching_session.get(task_key)
                    if task and not task.done():
                        task.cancel()
                        log(f"  Cancelled {task_key}")
                
                # Close Deepgram STT WebSocket
                stt = self.teaching_session.get('stt_service')
                if stt:
                    try:
                        await stt.close()
                        log("  STT service closed")
                    except Exception as e:
                        log(f"  STT close error (ignored): {e}")
                
                # Cleanup orchestrator session
                thread_id = self.teaching_session.get('thread_id')
                if thread_id and self.orchestrator:
                    self.orchestrator.cleanup(thread_id)
                
                self.teaching_session['active'] = False
                self.teaching_session = None
            
            # Log final metrics
            log(f"Final metrics for {self.client_id}: {self.conversation_metrics}")
            
        except Exception as e:
            log(f"Error during cleanup for {self.client_id}: {e}")

async def websocket_handler(websocket, path=None):
    """
    Main WebSocket handler for ProfAI connections with improved error handling.
    """
    connection_start_time = time.time()
    client_id = f"profai_client_{int(connection_start_time)}"
    try:
        remote_address = getattr(websocket, 'remote_address', 'unknown')
        if hasattr(remote_address, '__iter__') and not isinstance(remote_address, str):
            remote_address = f"{remote_address[0]}:{remote_address[1]}"
    except Exception:
        remote_address = "unknown"
    log(f"New client connected: {client_id} from {remote_address}")
    
    try:
        # Create enhanced websocket wrapper
        websocket_wrapper = ProfAIWebSocketWrapper(websocket, client_id)
        
        # Try to create ProfAI agent
        try:
            agent = ProfAIAgent(websocket_wrapper)
            # Process messages
            await agent.process_messages()
        except Exception as agent_error:
            log(f"Error creating ProfAI agent for {client_id}: {agent_error}")
            # Fallback to basic WebSocket handling
            await basic_websocket_handler(websocket_wrapper, client_id)
        
    except ConnectionClosed as e:
        connection_duration = time.time() - connection_start_time
        log_disconnection(client_id, e, f"after {connection_duration:.2f}s")
    except Exception as e:
        connection_duration = time.time() - connection_start_time
        log(f"Error handling client {client_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connection_duration = time.time() - connection_start_time
        log(f"Connection handler finished for {client_id}. Total duration: {connection_duration:.2f}s")

async def basic_websocket_handler(websocket_wrapper: ProfAIWebSocketWrapper, client_id: str):
    """
    Basic WebSocket handler for when services are not available.
    """
    log(f"Using basic WebSocket handler for {client_id}")
    
    # Send connection ready message
    await websocket_wrapper.send({
        "type": "connection_ready",
        "message": "ProfAI WebSocket connected (basic mode - services unavailable)",
        "client_id": client_id,
        "services": {
            "chat": False,
            "audio": False,
            "teaching": False
        }
    })
    
    while True:
        try:
            message = await websocket_wrapper.recv()
            data = json.loads(message)
            
            message_type = data.get("type")
            if not message_type:
                await websocket_wrapper.send({
                    "type": "error",
                    "error": "Message type is required"
                })
                continue
            
            log(f"Basic handler processing: {message_type} for client {client_id}")
            
            if message_type == "ping":
                await websocket_wrapper.send({
                    "type": "pong",
                    "message": "Connection alive (basic mode)",
                    "server_time": time.time()
                })
            else:
                await websocket_wrapper.send({
                    "type": "error",
                    "error": f"Service not available in basic mode: {message_type}"
                })
            
        except ConnectionClosed as e:
            log_disconnection(client_id, e, "in basic handler")
            break
        except json.JSONDecodeError:
            await websocket_wrapper.send({
                "type": "error",
                "error": "Invalid JSON message"
            })
        except Exception as e:
            log(f"❌ Basic handler error for {client_id}: {e}")
            try:
                await websocket_wrapper.send({
                    "type": "error",
                    "error": f"Basic handler error: {str(e)}"
                })
            except ConnectionClosed as conn_e:
                log_disconnection(client_id, conn_e, "while sending error message in basic handler")
                break

async def start_websocket_server(host: str, port: int):
    """
    Start the ProfAI WebSocket server with optimized configuration.
    """
    # Enhanced WebSocket server configuration for stability
    server_config = {
        "ping_interval": 30,  # Send ping every 30 seconds
        "ping_timeout": 20,   # Wait 20 seconds for pong
        "close_timeout": 5,   # Wait 5 seconds for close
        "max_size": 2**20,    # 1MB max message size
        "max_queue": 16,      # Reduced queue size for stability
        "compression": None,  # Disable compression to reduce complexity
    }
    
    log(f"Starting ProfAI WebSocket server on {host}:{port}")
    log("Features enabled: low-latency audio streaming, educational content delivery, performance optimization")
    
    try:
        async with websockets.serve(
            websocket_handler,
            host,
            port,
            **server_config
        ):
            log(f"✅ ProfAI WebSocket server started successfully!")
            log(f"🌐 WebSocket URL: ws://{host}:{port}")
            log(f"🧪 Test page: http://{host}:5001/profai-websocket-test")
            log(f"📊 Quick test: python quick_test_websocket.py")
            await asyncio.Future()  # Run forever
    except OSError as e:
        if e.errno == 10048:  # Windows: Address already in use
            log(f"❌ Port {port} is already in use!")
            log(f"💡 Try a different port or stop the existing server")
        elif e.errno == 98:  # Linux: Address already in use
            log(f"❌ Port {port} is already in use!")
            log(f"💡 Try: sudo lsof -i :{port} to find what's using the port")
        else:
            log(f"❌ Failed to start WebSocket server: {e}")
        raise
    except Exception as e:
        log(f"❌ Unexpected error starting WebSocket server: {e}")
        raise

def main():
    """
    Main entry point for the ProfAI WebSocket server.
    """
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description='ProfAI WebSocket Server')
    parser.add_argument('--host', type=str, default=config.WEBSOCKET_HOST, help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=config.WEBSOCKET_PORT, help='Port to bind the server to')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    
    try:
        # Run the WebSocket server
        asyncio.run(start_websocket_server(args.host, args.port))
    except KeyboardInterrupt:
        log("Server stopped by user")
    except Exception as e:
        log(f"Server error: {e}")
        import traceback
        traceback.print_exc()

def run_websocket_server_in_thread(host: str = "0.0.0.0", port: int = 8765):
    """Run WebSocket server in a separate thread for integration with Flask."""
    def run_server():
        asyncio.run(start_websocket_server(host, port))
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    log(f"WebSocket server thread started on {host}:{port}")
    return thread

if __name__ == "__main__":
    main()
