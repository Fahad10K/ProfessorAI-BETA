"""
Optimized streaming utilities for Supervisor Multi-Agent responses
Handles efficient TTS streaming with minimal latency
"""

import asyncio
import time
import logging
from typing import Optional

log = logging.getLogger(__name__)


async def stream_supervisor_response_to_websocket(
    websocket,
    response_text: str,
    agent_name: str,
    audio_service,
    language: str = "en-IN",
    teaching_session: Optional[dict] = None
) -> None:
    """
    Stream supervisor agent response via TTS with low latency.
    
    Optimizations:
    - Immediate start (no waiting)
    - Chunk-based streaming
    - Cancellation support for barge-in
    - Latency tracking
    
    Args:
        websocket: WebSocket wrapper for sending
        response_text: Agent's text response
        agent_name: Which agent generated response (teaching, qa, assessment, navigation)
        audio_service: Audio service for TTS
        language: TTS language
        teaching_session: Session dict for cancellation tracking
    """
    stream_start = time.time()
    
    try:
        log.info(f"🎙️ Streaming {agent_name} response ({len(response_text)} chars)")
        
        # Send text response FIRST (user sees it immediately)
        await websocket.send({
            "type": "agent_response",
            "text": response_text,
            "agent": agent_name,
            "timestamp": time.time()
        })
        
        text_latency = (time.time() - stream_start) * 1000
        log.info(f"⚡ Text sent in {text_latency:.0f}ms")
        
        # Stream audio chunks (async, can be interrupted)
        async def send_audio_chunks():
            chunk_count = 0
            audio_start = time.time()
            
            try:
                async for audio_chunk in audio_service.text_to_speech_stream(
                    text=response_text,
                    language=language
                ):
                    # Check for cancellation (barge-in)
                    if teaching_session and teaching_session.get('current_tts_task'):
                        if teaching_session['current_tts_task'].cancelled():
                            log.info("🛑 TTS cancelled (barge-in)")
                            break
                    
                    # Send audio chunk
                    await websocket.send({
                        "type": "audio_chunk",
                        "audio": audio_chunk,
                        "chunk_index": chunk_count,
                        "agent": agent_name
                    })
                    
                    chunk_count += 1
                
                audio_duration = (time.time() - audio_start) * 1000
                log.info(f"✅ Audio streamed: {chunk_count} chunks in {audio_duration:.0f}ms")
                
                # Send completion
                await websocket.send({
                    "type": "audio_complete",
                    "agent": agent_name,
                    "chunk_count": chunk_count,
                    "duration_ms": audio_duration
                })
                
            except asyncio.CancelledError:
                log.info(f"🛑 Audio streaming cancelled for {agent_name}")
                raise
            except Exception as e:
                log.error(f"❌ Audio streaming error: {e}")
                await websocket.send({
                    "type": "error",
                    "error": f"Audio streaming failed: {str(e)}"
                })
        
        # Create TTS task (can be cancelled)
        tts_task = asyncio.create_task(send_audio_chunks())
        
        # Store task for potential cancellation
        if teaching_session:
            teaching_session['current_tts_task'] = tts_task
        
        # Wait for completion or cancellation
        await tts_task
        
        total_latency = (time.time() - stream_start) * 1000
        log.info(f"⚡ Total supervisor response latency: {total_latency:.0f}ms")
        
    except asyncio.CancelledError:
        log.info(f"🛑 Supervisor response streaming cancelled")
        raise
    except Exception as e:
        log.error(f"❌ Supervisor streaming error: {e}")
        await websocket.send({
            "type": "error",
            "error": f"Response streaming failed: {str(e)}"
        })


async def stream_agent_response_optimized(
    websocket,
    agent_response: str,
    agent_name: str,
    audio_service,
    language: str = "en-IN"
) -> None:
    """
    Optimized streaming for agent responses (no teaching session tracking needed).
    Minimal latency version for quick Q&A responses.
    
    Args:
        websocket: WebSocket wrapper
        agent_response: Agent's text response
        agent_name: Agent identifier
        audio_service: TTS service
        language: Language code
    """
    try:
        # Text first (fastest)
        await websocket.send({
            "type": "agent_response",
            "text": agent_response,
            "agent": agent_name
        })
        
        # Audio streaming (parallel if possible)
        chunk_count = 0
        async for audio_chunk in audio_service.text_to_speech_stream(
            text=agent_response,
            language=language
        ):
            await websocket.send({
                "type": "audio_chunk",
                "audio": audio_chunk,
                "agent": agent_name
            })
            chunk_count += 1
        
        # Completion
        await websocket.send({
            "type": "audio_complete",
            "agent": agent_name,
            "chunks": chunk_count
        })
        
    except Exception as e:
        log.error(f"❌ Optimized streaming error: {e}")
        raise
