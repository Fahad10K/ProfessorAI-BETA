# websocket_server.py
# High-performance WebSocket server for ProfAI with sub-300ms latency
# Based on Contelligence architecture with optimizations for educational content

import asyncio
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

# LangGraph Supervisor Multi-Agent System (Production)
from services.langgraph_supervisor_agent import (
    create_supervisor_teaching_system,
    initialize_supervisor_session,
    process_with_supervisor,
    SupervisorState
)
from langchain_core.messages import HumanMessage, AIMessage

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
        
        # LangGraph Supervisor Multi-Agent System (LAZY ASYNC INITIALIZATION)
        # Will be initialized on first teaching session (async pattern)
        self.supervisor_graph = None
        self._supervisor_initialized = False
        
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
        
        # Interactive teaching session state (managed by supervisor)
        self.teaching_session = None
        
        log(f"ProfAI agent initialized for client {self.client_id} - Services: {self.services_available}")

    async def _ensure_supervisor_initialized(self):
        """
        Lazy initialization of supervisor graph (async pattern).
        Only runs once, then reuses the compiled graph for all sessions.
        """
        if self._supervisor_initialized and self.supervisor_graph:
            return True
        
        if not config.REDIS_URL:
            log("❌ Redis URL not configured, cannot initialize supervisor")
            return False
        
        try:
            log("🤖 Initializing Async Supervisor Multi-Agent System...")
            self.supervisor_graph = await create_supervisor_teaching_system(
                redis_url=config.REDIS_URL
            )
            self._supervisor_initialized = True
            log("✅ Async Supervisor graph compiled and ready (will reuse for all sessions)")
            return True
        except Exception as e:
            log(f"⚠️ Failed to initialize supervisor: {e}")
            self.supervisor_graph = None
            self._supervisor_initialized = False
            return False

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
                    
                    log(f"Processing message type: {message_type} for client {self.client_id}")
                    
                    # Route messages to appropriate handlers
                    if message_type == "ping":
                        await self.handle_ping(data)
                    elif message_type == "chat_with_audio":
                        await self.handle_chat_with_audio(data)
                    elif message_type == "start_class":
                        await self.handle_start_class(data)
                    elif message_type == "interactive_teaching":
                        await self.handle_interactive_teaching(data)
                    elif message_type == "stt_audio_chunk":
                        await self.handle_stt_audio_chunk(data)
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
                        course_id=course_id
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
                # OPTIMIZED streaming for sub-300ms latency (consistent with start_class)
                audio_start_time = time.time()
                chunk_count = 0
                total_audio_size = 0
                first_chunk_sent = False
                
                log(f"🚀 Starting REAL-TIME class audio streaming for: {response_text[:50]}...")
                
                async for audio_chunk in self.audio_service.stream_audio_from_text(response_text, language, self.websocket):
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
                        
                        # Log first chunk latency (CRITICAL METRIC - consistent with start_class)
                        if not first_chunk_sent:
                            first_audio_latency = (time.time() - audio_start_time) * 1000
                            log(f"🎯 FIRST CHAT AUDIO CHUNK delivered in {first_audio_latency:.0f}ms")
                            
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
                
                # Send completion message (consistent with start_class)
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
            
            # Load and validate course content with timeout
            try:
                import os
                if not os.path.exists(config.OUTPUT_JSON_PATH):
                    await self.websocket.send({
                        "type": "error",
                        "error": "Course content not found"
                    })
                    return
                
                # Load course data with timeout protection - pass course_id for proper loading
                course_data = await asyncio.wait_for(
                    self._load_course_data_async(course_id),
                    timeout=60.0  # 60 second timeout for file loading
                )
                
                # Validate indices
                if module_index >= len(course_data.get("modules", [])):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Module {module_index} not found (available: 0-{len(course_data.get('modules', []))-1})"
                    })
                    return
                    
                module = course_data["modules"][module_index]
                
                if sub_topic_index >= len(module.get("sub_topics", [])):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Sub-topic {sub_topic_index} not found (available: 0-{len(module.get('sub_topics', []))-1})"
                    })
                    return
                    
                sub_topic = module["sub_topics"][sub_topic_index]
                
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
                # OPTIMIZED streaming for sub-300ms latency (consistent with chat_with_audio)
                audio_start_time = time.time()
                chunk_count = 0
                total_audio_size = 0
                first_chunk_sent = False
                
                log(f"🚀 Starting REAL-TIME class audio streaming for: {teaching_content[:50]}...")
                
                async for audio_chunk in self.audio_service.stream_audio_from_text(teaching_content, language, self.websocket):
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
                            log(f"🎯 FIRST CLASS AUDIO CHUNK delivered in {first_audio_latency:.0f}ms")
                            
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
                
                # Send completion message (consistent completion type)
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
            
            log(f"Starting interactive teaching: course={course_id}, module={module_index}, topic={sub_topic_index}")
            
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
            
            # Ensure supervisor multi-agent system is initialized (lazy async init)
            supervisor_ready = await self._ensure_supervisor_initialized()
            if not supervisor_ready or not self.supervisor_graph:
                log("❌ Supervisor graph initialization failed, cannot start teaching")
                await self.websocket.send({
                    "type": "error",
                    "error": "Multi-agent system initialization failed"
                })
                return
            
            log("🤖 Initializing supervisor session with specialized agents...")
            
            # Initialize supervisor state (efficient - stored in Redis via checkpointing)
            thread_id = self.session_id or f"ws_{self.client_id}"
            
            self.supervisor_state = initialize_supervisor_session(
                session_id=thread_id,
                user_id=user_id,
                course_id=course_id,
                module_index=module_index,
                sub_topic_index=sub_topic_index,
                total_segments=10  # Configurable
            )
            
            # Initialize teaching session state (lightweight - for WebSocket management)
            self.teaching_session = {
                'active': True,
                'thread_id': thread_id,  # For supervisor checkpointing
                'course_id': course_id,
                'module_index': module_index,
                'sub_topic_index': sub_topic_index,
                'current_tts_task': None,
                'stt_service': None,
                'user_id': user_id,
                'language': language,
                'supervisor_state': self.supervisor_state,  # Reference to state
                'last_latency_ms': 0  # Latency tracking
            }
            
            log(f"✅ Supervisor session initialized (thread_id: {thread_id})")
            log("🎯 Specialized agents ready: Teaching, Q&A, Assessment, Navigation")
            
            # Send acknowledgment
            await self.websocket.send({
                "type": "interactive_teaching_init",
                "message": "Loading course content...",
                "course_id": course_id,
                "module_index": module_index,
                "sub_topic_index": sub_topic_index
            })
            
            # Load course content from JSON (teaching structure not in database)
            try:
                import os
                import json
                
                log(f"Loading course {course_id} teaching content from JSON...")
                
                if not os.path.exists(config.OUTPUT_JSON_PATH):
                    await self.websocket.send({
                        "type": "error",
                        "error": "Course content not found"
                    })
                    return
                
                with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle both single course and multi-course formats
                course_data = None
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
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Course {course_id} not found in teaching content"
                    })
                    return
                
                log(f"Found course: {course_data.get('course_title', 'Unknown')}")
                
                # Validate module index
                modules = course_data.get("modules", [])
                log(f"Course has {len(modules)} modules")
                
                if module_index >= len(modules):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Module {module_index} not found. Course has {len(modules)} modules (0-{len(modules)-1})"
                    })
                    return
                
                module = modules[module_index]
                
                # Validate sub-topic index
                sub_topics = module.get("sub_topics", [])
                log(f"Module '{module['title']}' has {len(sub_topics)} sub-topics")
                
                if sub_topic_index >= len(sub_topics):
                    await self.websocket.send({
                        "type": "error",
                        "error": f"Sub-topic {sub_topic_index} not found. Module has {len(sub_topics)} sub-topics (0-{len(sub_topics)-1})"
                    })
                    return
                
                sub_topic = sub_topics[sub_topic_index]
                log(f"✅ Loaded: {module['title']} → {sub_topic['title']}")
                
            except Exception as e:
                log(f"Error loading course content: {e}")
                import traceback
                traceback.print_exc()
                await self.websocket.send({
                    "type": "error",
                    "error": f"Failed to load course content: {str(e)}"
                })
                return
            
            # Generate teaching content
            try:
                raw_content = sub_topic.get('content', '')
                if not raw_content:
                    raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
                
                if len(raw_content) > 8000:
                    raw_content = raw_content[:7500] + "..."
                
                if not self.services_available.get("teaching", False):
                    teaching_content = self._create_simple_teaching_content(
                        module['title'], sub_topic['title'], raw_content
                    )
                else:
                    try:
                        teaching_content = await asyncio.wait_for(
                            self.teaching_service.generate_teaching_content(
                                module_title=module['title'],
                                sub_topic_title=sub_topic['title'],
                                raw_content=raw_content,
                                language=language
                            ),
                            timeout=60.0
                        )
                    except asyncio.TimeoutError:
                        teaching_content = self._create_simple_teaching_content(
                            module['title'], sub_topic['title'], raw_content
                        )
                
                if not teaching_content or len(teaching_content.strip()) == 0:
                    teaching_content = self._create_simple_teaching_content(
                        module['title'], sub_topic['title'], raw_content
                    )
                
                self.teaching_session['teaching_content'] = teaching_content
                
                # Content loaded and ready for supervisor to deliver
                log(f"✅ Teaching content loaded, ready for supervisor delivery")
                
            except Exception as e:
                log(f"Error generating teaching content: {e}")
                teaching_content = self._create_simple_teaching_content(
                    module['title'], sub_topic['title'], raw_content
                )
                self.teaching_session['teaching_content'] = teaching_content
                
                # Fallback content loaded and ready for supervisor
            
            # Initialize Deepgram STT service for voice input
            try:
                from services.deepgram_stt_service import DeepgramSTTService
                stt_service = DeepgramSTTService(sample_rate=16000)
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
        """Listen for STT events and handle user interruptions during teaching."""
        log("🎤 _handle_teaching_interruptions() task STARTED")
        
        if not self.teaching_session:
            log("❌ No teaching_session available in interruption handler")
            return
        
        stt_service = self.teaching_session.get('stt_service')
        if not stt_service:
            log("❌ No STT service available for interruptions")
            return
        
        log(f"✅ STT service found: {type(stt_service).__name__}")
        
        try:
            log("👂 Starting to listen for teaching interruptions...")
            
            event_count = 0
            async for event in stt_service.recv():
                event_count += 1
                event_type = event.get('type')
                # Only log critical events at INFO level, partials at DEBUG
                if event_type in ['speech_started', 'final', 'utterance_end']:
                    log(f"📨 Deepgram: {event_type}")
                else:
                    logging.debug(f"📨 Deepgram event #{event_count}: {event_type}")
                
                if event_type == 'speech_started':
                    # USER STARTED SPEAKING - BARGE-IN!
                    barge_in_start = time.time()
                    log(f"🗣️ User interruption detected for client {self.client_id}")
                    
                    # Set speaking state flag to prevent new TTS generation
                    self.teaching_session['user_is_speaking'] = True
                    
                    # Cancel current teaching/answer audio IMMEDIATELY (minimize latency)
                    if self.teaching_session.get('current_tts_task'):
                        log("⏹️ Cancelling TTS task...")
                        self.teaching_session['current_tts_task'].cancel()
                        log("✅ TTS cancelled")
                    
                    # Notify client FAST (no supervisor call needed for barge-in detection)
                    try:
                        await self.websocket.send({
                            "type": "user_interrupt_detected",
                            "message": "Listening..."
                        })
                        barge_in_latency = (time.time() - barge_in_start) * 1000
                        log(f"✅ Barge-in handled in {barge_in_latency:.0f}ms")
                    except Exception as e:
                        log(f"❌ Failed to send interrupt notification: {e}")
                
                elif event_type == 'partial':
                    # Interim transcript - DEBUG ONLY (not sent to UI to reduce spam)
                    partial_text = event.get('text', '')
                    if partial_text:
                        # Only log at DEBUG level to avoid console spam
                        logging.debug(f"📝 Partial: {partial_text[:50]}")
                        # DO NOT send partials to UI - causes network/visual spam
                
                elif event_type == 'final':
                    # User finished speaking - USE SUPERVISOR MULTI-AGENT for intelligent routing
                    supervisor_start = time.time()
                    
                    # Reset speaking state flag
                    self.teaching_session['user_is_speaking'] = False
                    
                    user_input = event.get('text', '').strip()
                    if not user_input:
                        log("⚠️ Empty final transcript, skipping")
                        continue
                    
                    log(f"📝 User utterance: {user_input}")
                    
                    # Echo to client FAST (don't wait for supervisor)
                    try:
                        await self.websocket.send({
                            "type": "user_question",
                            "text": user_input
                        })
                    except Exception as e:
                        log(f"❌ Failed to send user_question: {e}")
                    
                    # Save to database (async, non-blocking)
                    if self.session_manager and self.session_id:
                        try:
                            self.session_manager.add_message(
                                user_id=self.teaching_session['user_id'],
                                session_id=self.session_id,
                                role='user',
                                content=user_input,
                                message_type='voice',
                                course_id=self.teaching_session['course_id']
                            )
                        except Exception as e:
                            log(f"❌ Failed to save user message: {e}")
                    
                    # PROCESS WITH SUPERVISOR MULTI-AGENT SYSTEM (async, efficient)
                    if self.supervisor_graph:
                        try:
                            log("🤖 Routing to supervisor for intelligent agent selection...")
                            
                            # Process through supervisor (async, uses Redis checkpointing)
                            thread_id = self.teaching_session.get('thread_id')
                            result = await process_with_supervisor(
                                graph=self.supervisor_graph,
                                user_input=user_input,
                                thread_id=thread_id
                            )
                            
                            supervisor_latency = (time.time() - supervisor_start) * 1000
                            self.teaching_session['last_latency_ms'] = supervisor_latency
                            
                            # Extract agent response from messages
                            messages = result.get('messages', [])
                            if messages:
                                # Get last AI message (agent response)
                                ai_messages = [m for m in messages if isinstance(m, AIMessage)]
                                if ai_messages:
                                    agent_response = ai_messages[-1].content
                                    last_agent = result.get('last_agent', 'unknown')
                                    
                                    log(f"🎯 SUPERVISOR ROUTED TO: {last_agent}")
                                    log(f"⚡ Total latency: {supervisor_latency:.0f}ms")
                                    
                                    # Stream agent response via TTS
                                    await self._stream_supervisor_response(
                                        response_text=agent_response,
                                        agent_name=last_agent
                                    )
                                    
                        except Exception as e:
                            log(f"❌ Supervisor error: {e}")
                            await self.websocket.send({
                                "type": "error",
                                "error": f"Agent processing failed: {str(e)}"
                            })
                    else:
                        log("⚠️ Supervisor not available, cannot process input")
                
                elif event_type == 'utterance_end':
                    log("🔇 User stopped speaking (utterance_end)")
                
                elif event_type == 'closed':
                    log("🔌 STT service closed event received")
                    break
                
                else:
                    log(f"❓ Unknown event type: {event_type}")
        
        except asyncio.CancelledError:
            log("🛑 Interruption handler task cancelled")
        except Exception as e:
            log(f"❌❌❌ CRITICAL ERROR in teaching interruption handler: {e}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
        finally:
            log("🏁 _handle_teaching_interruptions() task ENDED")
    
    async def _stream_teaching_content(self, content: str, language: str):
        """Stream teaching audio with cancellation support for barge-in."""
        try:
            self.teaching_session['is_teaching'] = True
            
            async def send_teaching_audio():
                chunk_count = 0
                total_audio_size = 0
                audio_start_time = time.time()
                
                log(f"🎙️ Starting teaching audio stream ({len(content)} chars)")
                
                # Stream audio chunks
                async for audio_chunk in self.audio_service.stream_audio_from_text(
                    content, language, self.websocket
                ):
                    # CHECK IF INTERRUPTED
                    if not self.teaching_session.get('is_teaching', False):
                        log("🛑 Teaching interrupted by user - stopping audio")
                        await self.websocket.send({"type": "teaching_interrupted"})
                        return
                    
                    if audio_chunk and len(audio_chunk) > 0:
                        chunk_count += 1
                        total_audio_size += len(audio_chunk)
                        
                        # Send audio chunk
                        import base64
                        audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                        await self.websocket.send({
                            "type": "teaching_audio_chunk",
                            "chunk_id": chunk_count,
                            "audio_data": audio_base64,
                            "size": len(audio_chunk)
                        })
                
                # Teaching segment complete
                await self.websocket.send({
                    "type": "teaching_segment_complete",
                    "total_chunks": chunk_count,
                    "total_size": total_audio_size,
                    "duration_ms": (time.time() - audio_start_time) * 1000,
                    "message": "Section complete. Ask questions or say 'continue' to proceed."
                })
                
                self.teaching_session['is_teaching'] = False
                log(f"✅ Teaching audio complete: {chunk_count} chunks, {total_audio_size} bytes")
            
            # Create cancellable task
            self.teaching_session['current_tts_task'] = asyncio.create_task(send_teaching_audio())
            
            # Wait for completion or cancellation
            try:
                await self.teaching_session['current_tts_task']
            except asyncio.CancelledError:
                log("Teaching TTS task cancelled")
                self.teaching_session['is_teaching'] = False
            finally:
                self.teaching_session['current_tts_task'] = None
        
        except asyncio.CancelledError:
            log("Teaching audio streaming cancelled by user")
            await self.websocket.send({"type": "teaching_cancelled"})
        except Exception as e:
            log(f"Error streaming teaching content: {e}")
            self.teaching_session['is_teaching'] = False
    
    async def _stream_supervisor_response(self, response_text: str, agent_name: str):
        """
        Stream supervisor agent response via TTS with low latency.
        Optimized for continuous listening and minimal delay.
        """
        stream_start = time.time()
        
        try:
            log(f"🎤 Streaming {agent_name} response ({len(response_text)} chars)")
            
            # Send text response FIRST (user sees immediately - no waiting for audio)
            await self.websocket.send({
                "type": "agent_response",
                "text": response_text,
                "agent": agent_name,
                "timestamp": time.time()
            })
            
            text_latency = (time.time() - stream_start) * 1000
            log(f"⚡ Text sent in {text_latency:.0f}ms")
            
            # Save agent message to database (async, non-blocking)
            if self.session_manager and self.session_id:
                try:
                    self.session_manager.add_message(
                        user_id=self.teaching_session['user_id'],
                        session_id=self.session_id,
                        role='assistant',
                        content=response_text,
                        message_type='voice',
                        course_id=self.teaching_session['course_id'],
                        metadata={
                            'agent': agent_name,
                            'supervisor_routed': True
                        }
                    )
                except Exception as e:
                    log(f"⚠️ Failed to save agent message: {e}")
            
            # Stream audio chunks (async, can be interrupted)
            async def send_audio_chunks():
                # Check if user is speaking BEFORE generating TTS
                if self.teaching_session.get('user_is_speaking', False):
                    log("🛑 Skipping TTS: user is speaking")
                    return
                
                chunk_count = 0
                audio_start = time.time()
                
                try:
                    async for audio_chunk in self.audio_service.stream_audio_from_text(
                        text=response_text,
                        language_code=self.teaching_session['language']
                    ):
                        # Check if user started speaking during generation
                        if self.teaching_session.get('user_is_speaking', False):
                            log("🛑 TTS interrupted: user started speaking")
                            break
                        
                        # Check for task cancellation (barge-in)
                        if self.teaching_session.get('current_tts_task'):
                            if self.teaching_session['current_tts_task'].cancelled():
                                log("🛑 Agent TTS cancelled (barge-in)")
                                break
                        
                        # Send audio chunk
                        await self.websocket.send({
                            "type": "audio_chunk",
                            "audio": audio_chunk,
                            "chunk_index": chunk_count,
                            "agent": agent_name
                        })
                        
                        chunk_count += 1
                    
                    audio_duration = (time.time() - audio_start) * 1000
                    log(f"✅ Audio streamed: {chunk_count} chunks in {audio_duration:.0f}ms")
                    
                    # Send completion
                    await self.websocket.send({
                        "type": "audio_complete",
                        "agent": agent_name,
                        "chunk_count": chunk_count,
                        "duration_ms": audio_duration
                    })
                    
                except asyncio.CancelledError:
                    log(f"🛑 Audio streaming cancelled for {agent_name}")
                    raise
                except Exception as e:
                    log(f"❌ Audio streaming error: {e}")
            
            # Create TTS task (can be cancelled for barge-in)
            tts_task = asyncio.create_task(send_audio_chunks())
            self.teaching_session['current_tts_task'] = tts_task
            
            # Wait for completion or cancellation
            try:
                await tts_task
            except asyncio.CancelledError:
                log("Agent TTS task cancelled")
            finally:
                self.teaching_session['current_tts_task'] = None
            
            total_latency = (time.time() - stream_start) * 1000
            log(f"⚡ Total supervisor response latency: {total_latency:.0f}ms")
            
        except asyncio.CancelledError:
            log(f"🛑 Supervisor response streaming cancelled")
        except Exception as e:
            log(f"❌ Supervisor streaming error: {e}")
            await self.websocket.send({
                "type": "error",
                "error": f"Response streaming failed: {str(e)}"
            })
    
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
        # Create a simple structured teaching content
        content = f"Let's learn about {topic_title} in the {module_title} module.\n\n"
        
        # Add raw content with basic formatting
        if raw_content and len(raw_content.strip()) > 0:
            # Split into paragraphs for better readability
            paragraphs = raw_content.strip().split('\n\n')
            for para in paragraphs[:3]:  # Limit to first 3 paragraphs
                if para.strip():
                    content += para.strip() + "\n\n"
        else:
            content += "This topic covers important concepts that we'll explore together.\n\n"
        
        content += "Feel free to ask questions or say 'continue' when you're ready to proceed."
        
        return content

    async def _answer_teaching_question(self, question: str):
        """Answer user's question in the context of current teaching."""
        try:
            log(f"🤔 Processing teaching question: {question[:50]}...")
            
            # Get conversation history from database (last 5 turns)
            conversation_history = []
            if self.session_id and self.session_manager:
                try:
                    conversation_history = self.session_manager.get_conversation_history(
                        self.session_id, limit=5
                    )
                    log(f"Retrieved {len(conversation_history)} previous messages")
                except Exception as e:
                    log(f"Failed to get conversation history: {e}")
            
            # Call chat service with course context
            if not self.services_available.get("chat", False):
                # Fallback if chat service unavailable
                answer_text = "I apologize, but I'm having trouble processing your question right now. Please try again."
            else:
                try:
                    response_data = await asyncio.wait_for(
                        self.chat_service.ask_question(
                            question,
                            query_language_code=self.teaching_session['language'],
                            session_id=self.session_id,
                            conversation_history=conversation_history,
                            course_id=self.teaching_session['course_id']
                        ),
                        timeout=60.0
                    )
                    
                    answer_text = response_data.get('answer', '')
                    
                    # Send text response with metadata
                    await self.websocket.send({
                        "type": "teaching_question_answer",
                        "text": answer_text,
                        "route": response_data.get('route'),
                        "confidence": response_data.get('confidence'),
                        "sources": response_data.get('sources', [])
                    })
                    
                    log(f"💬 Answer generated: {answer_text[:80]}...")
                    
                except asyncio.TimeoutError:
                    log("Chat service timeout")
                    answer_text = "I'm taking a bit longer than usual to process your question. Could you please rephrase it?"
                    await self.websocket.send({
                        "type": "teaching_question_answer",
                        "text": answer_text
                    })
            
            # Save assistant message to database
            if self.session_manager and self.session_id:
                try:
                    self.session_manager.add_message(
                        user_id=self.teaching_session['user_id'],
                        session_id=self.session_id,
                        role='assistant',
                        content=answer_text,
                        message_type='voice',
                        course_id=self.teaching_session['course_id'],
                        metadata={
                            'route': response_data.get('route') if 'response_data' in locals() else None,
                            'context': 'teaching_qa'
                        }
                    )
                    log("💾 Answer saved to database")
                except Exception as e:
                    log(f"Failed to save answer: {e}")
            
            # Stream answer audio (use separate flag from teaching)
            self.teaching_session['is_answering'] = True
            chunk_count = 0
            total_audio_size = 0
            audio_start_time = time.time()
            
            log(f"🎙️ Generating answer audio...")
            
            try:
                async for audio_chunk in self.audio_service.stream_audio_from_text(
                    answer_text, self.teaching_session['language'], self.websocket
                ):
                    # Check if interrupted again
                    if not self.teaching_session.get('is_answering', False):
                        log("🛑 Answer interrupted by user")
                        return
                    
                    if audio_chunk and len(audio_chunk) > 0:
                        chunk_count += 1
                        total_audio_size += len(audio_chunk)
                        
                        import base64
                        audio_base64 = base64.b64encode(audio_chunk).decode('utf-8')
                        await self.websocket.send({
                            "type": "answer_audio_chunk",
                            "chunk_id": chunk_count,
                            "audio_data": audio_base64,
                            "size": len(audio_chunk)
                        })
                
                # Answer complete
                await self.websocket.send({
                    "type": "answer_complete",
                    "total_chunks": chunk_count,
                    "total_size": total_audio_size,
                    "duration_ms": (time.time() - audio_start_time) * 1000,
                    "message": "Would you like to continue the lesson or ask another question?"
                })
                
                self.teaching_session['is_answering'] = False
                log(f"✅ Answer audio complete: {chunk_count} chunks")
                
            except Exception as e:
                log(f"Error streaming answer audio: {e}")
                self.teaching_session['is_answering'] = False
        
        except Exception as e:
            log(f"Error answering teaching question: {e}")
            await self.websocket.send({
                "type": "error",
                "error": "Failed to answer question. Please try again."
            })
            self.teaching_session['is_teaching'] = False
    
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
            
            # Forward to Deepgram
            await self.teaching_session['stt_service'].send_audio_chunk(pcm_bytes)
            
        except Exception as e:
            log(f"Error forwarding audio to STT: {e}")
    
    async def handle_continue_teaching(self, data: dict):
        """Resume teaching after user Q&A."""
        if not self.teaching_session or not self.teaching_session.get('active'):
            await self.websocket.send({
                "type": "error",
                "error": "No active teaching session"
            })
            return
        
        teaching_content = self.teaching_session.get('teaching_content')
        language = self.teaching_session.get('language', self.current_language)
        
        if not teaching_content:
            await self.websocket.send({
                "type": "error",
                "error": "No teaching content available"
            })
            return
        
        log("📖 Resuming teaching...")
        
        await self.websocket.send({
            "type": "teaching_resumed",
            "message": "Continuing the lesson..."
        })
        
        # Resume teaching audio
        await self._stream_teaching_content(teaching_content, language)
    
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
        
        # Mark session as inactive
        self.teaching_session['active'] = False
        self.teaching_session = None
        
        await self.websocket.send({
            "type": "teaching_ended",
            "message": "Teaching session completed successfully"
        })
        
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
                
                async for audio_chunk in self.audio_service.stream_audio_from_text(text, language, self.websocket):
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
