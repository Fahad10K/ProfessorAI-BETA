"""
ElevenLabs TTS Service
Provides high-quality text-to-speech with streaming support
"""

import asyncio
import json
import base64
import logging
from typing import Optional, AsyncGenerator
import websockets
from websockets.exceptions import ConnectionClosed
import config
import requests
import io

logger = logging.getLogger(__name__)


class ElevenLabsService:
    """
    ElevenLabs TTS service with streaming support.
    Provides ultra-fast, high-quality text-to-speech.
    """
    
    def __init__(self):
        self.api_key = getattr(config, "ELEVENLABS_API_KEY", None)
        self.voice_id = getattr(config, "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.model = getattr(config, "ELEVENLABS_MODEL", "eleven_flash_v2_5")
        self.websocket = None
        
        if self.api_key:
            logger.info("✅ ElevenLabs TTS Service initialized")
        else:
            logger.warning("⚠️ ElevenLabs API key not found - service disabled")
    
    @property
    def enabled(self) -> bool:
        """Check if ElevenLabs is enabled (API key present)."""
        return bool(self.api_key)
    
    async def text_to_speech_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech and stream audio chunks using a fresh ElevenLabs
        stream-input WebSocket per request. Falls back to REST TTS on error.
        
        Args:
            text: Text to convert to speech
            
        Yields:
            Audio chunks as bytes (MP3 format)
        """
        if not self.enabled:
            logger.warning("⚠️ ElevenLabs disabled - no API key")
            return
        
        # Use the Multi-Context WebSocket endpoint with explicit output format
        url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/multi-stream-input"
            f"?model_id={self.model}&output_format=mp3_22050_32&optimize_streaming_latency=4&auto_mode=true"
        )

        try:
            async with websockets.connect(
                url,
                additional_headers={"xi-api-key": self.api_key},
                max_size=16 * 1024 * 1024,
                ping_interval=25,
                ping_timeout=15,
            ) as ws:
                # Initial context configuration
                context_id = "conv_1"
                init_msg = {
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                    "context_id": context_id,
                }
                await ws.send(json.dumps(init_msg))

                # Send the text and then flush to finalize generation for this context
                await ws.send(json.dumps({"text": text, "context_id": context_id}))
                await ws.send(json.dumps({"flush": True, "context_id": context_id}))

                # Receive audio frames until final
                total_received = 0
                message_count = 0
                async for message in ws:
                    message_count += 1
                    try:
                        data = json.loads(message)
                        logger.debug(f"📨 ElevenLabs message #{message_count}: {data}")
                        if data.get("audio"):
                            audio_bytes = base64.b64decode(data["audio"])
                            if audio_bytes:
                                total_received += len(audio_bytes)
                                logger.debug(f"🎵 Audio chunk: {len(audio_bytes)} bytes")
                                yield audio_bytes
                        # Handle either is_final or isFinal markers from API variants
                        if data.get("is_final") or data.get("isFinal"):
                            logger.info("🏁 ElevenLabs marked final")
                            break
                    except json.JSONDecodeError:
                        # Binary audio payload
                        if isinstance(message, bytes) and len(message) > 0:
                            total_received += len(message)
                            logger.debug(f"🎵 Binary audio: {len(message)} bytes")
                            yield message
                
                # If no audio was received, force fallback
                if total_received == 0:
                    logger.warning("⚠️ ElevenLabs streaming returned 0 bytes, forcing fallback")
                    raise Exception("No audio data received from streaming")
                else:
                    logger.info(f"✅ ElevenLabs streaming completed: {total_received} bytes")

        except Exception as e:
            logger.error(f"❌ TTS streaming error: {e}")
            # REST fallback to avoid silent failures
            try:
                logger.info("🔄 Falling back to REST TTS...")
                audio = await self.text_to_speech(text)
                if audio:
                    logger.info(f"✅ REST TTS fallback: {len(audio)} bytes")
                    yield audio
                else:
                    logger.error("❌ REST TTS fallback also failed")
            except Exception as e2:
                logger.error(f"❌ TTS fallback error: {e2}")
    
    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech (non-streaming).
        
        Args:
            text: Text to convert
            
        Returns:
            Complete audio as bytes (MP3 format)
        """
        if not self.enabled:
            logger.warning("⚠️ ElevenLabs disabled - no API key")
            return b""
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, headers=headers, json=data, timeout=(10, 60))
            )
            response.raise_for_status()
            
            logger.info(f"✅ Generated audio: {len(response.content)} bytes")
            return response.content
            
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return b""
    
    async def generate_audio_from_text(self, text: str, language: Optional[str] = None) -> io.BytesIO:
        """
        Generate audio from text (compatibility method for AudioService).
        
        Args:
            text: Text to convert
            language: Language code (ignored for ElevenLabs)
            
        Returns:
            Audio data as BytesIO
        """
        audio_bytes = await self.text_to_speech(text)
        audio_buffer = io.BytesIO(audio_bytes)
        audio_buffer.seek(0)
        return audio_buffer
    
    async def disconnect(self):
        """Disconnect from WebSocket (if persistent connection used)."""
        # Persistent WS is no longer used; nothing to do.
        self.websocket = None
        logger.debug("🔌 ElevenLabs disconnected")
