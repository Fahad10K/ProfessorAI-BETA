"""
ElevenLabs TTS Service
Provides high-quality text-to-speech with streaming support.
Uses official ElevenLabs SDK when available, falls back to raw WebSocket.
"""

import asyncio
import json
import base64
import logging
import time
from typing import Optional, AsyncGenerator
import websockets
from websockets.exceptions import ConnectionClosed
import config
import requests
import io

# Free TTS fallback when ElevenLabs is unavailable
_HAS_EDGE_TTS = False
try:
    import edge_tts
    _HAS_EDGE_TTS = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Try to import official ElevenLabs SDK
_HAS_SDK = False
try:
    from elevenlabs.client import AsyncElevenLabs as _AsyncElevenLabs
    _HAS_SDK = True
    logger.info(" ElevenLabs official SDK available")
except ImportError:
    logger.warning(" elevenlabs SDK not installed, using raw WebSocket fallback")


class ElevenLabsService:
    """
    ElevenLabs TTS service with streaming support.
    Uses official SDK for lowest latency, falls back to raw WebSocket.
    """
    
    def __init__(self):
        self.api_key = getattr(config, "ELEVENLABS_API_KEY", None)
        self.voice_id = getattr(config, "ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.model = getattr(config, "ELEVENLABS_MODEL", "eleven_flash_v2_5")
        self.websocket = None
        self._sdk_client = None
        
        if self.api_key:
            # Initialize SDK client if available
            if _HAS_SDK:
                self._sdk_client = _AsyncElevenLabs(api_key=self.api_key)
                logger.info(" ElevenLabs TTS (SDK mode, lowest latency)")
            else:
                logger.info(" ElevenLabs TTS (WebSocket fallback mode)")
        else:
            logger.warning(" ElevenLabs API key not found - service disabled")
    
    @property
    def enabled(self) -> bool:
        """Check if ElevenLabs is enabled (API key present)."""
        return bool(self.api_key)
    
    async def text_to_speech_stream(self, text: str, voice_id: str = None) -> AsyncGenerator[bytes, None]:
        """
        Convert text to speech and stream audio chunks.
        Uses SDK streaming if available (fastest), else raw WebSocket, else REST fallback.
        
        Args:
            text: Text to convert to speech
            
        Yields:
            Audio chunks as bytes (MP3 format)
        """
        if not self.enabled:
            logger.warning("⚠️ ElevenLabs disabled - no API key")
            return
        
        t0 = time.time()
        
        # Strategy 1: Official SDK streaming (fastest, ~200-500ms first byte)
        effective_voice = voice_id or self.voice_id
        if self._sdk_client:
            try:
                async for chunk in self._stream_with_sdk(text, effective_voice):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"⚠️ SDK streaming failed: {e}, trying WebSocket fallback")
        
        # Strategy 2: Raw WebSocket streaming (fallback)
        try:
            async for chunk in self._stream_with_websocket(text, effective_voice):
                yield chunk
            return
        except Exception as e2:
            logger.warning(f"⚠️ WebSocket streaming failed: {e2}, trying REST fallback")
        
        # Strategy 3: REST fallback (slowest but most reliable)
        try:
            logger.info("🔄 Falling back to REST TTS...")
            audio = await self.text_to_speech(text, voice_id)
            if audio:
                logger.info(f"✅ REST TTS fallback: {len(audio)} bytes in {(time.time()-t0)*1000:.0f}ms")
                yield audio
                return
            else:
                logger.warning("⚠️ REST TTS returned empty")
        except Exception as e2:
            logger.warning(f"⚠️ REST TTS failed: {e2}")
        
        # Strategy 4: Free Edge TTS fallback (no API key needed)
        if _HAS_EDGE_TTS:
            try:
                logger.info("🔄 Falling back to free Edge TTS...")
                async for chunk in self._stream_with_edge_tts(text):
                    yield chunk
                return
            except Exception as e3:
                logger.error(f"❌ Edge TTS fallback failed: {e3}")
        
        logger.error("❌ All TTS methods failed")

    async def _stream_with_sdk(self, text: str, voice_id: str = None) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS using official ElevenLabs SDK.
        Lowest latency: ~200-500ms first byte.
        """
        t0 = time.time()
        total_bytes = 0
        chunk_count = 0
        
        # Try SDK streaming - the async client exposes convert() as async iterator
        effective_voice = voice_id or self.voice_id
        try:
            audio_stream = await self._sdk_client.text_to_speech.convert(
                text=text,
                voice_id=effective_voice,
                model_id=self.model,
                output_format="mp3_22050_32",
                optimize_streaming_latency=4,
            )
        except TypeError:
            # Some SDK versions don't need await on convert
            audio_stream = self._sdk_client.text_to_speech.convert(
                text=text,
                voice_id=effective_voice,
                model_id=self.model,
                output_format="mp3_22050_32",
                optimize_streaming_latency=4,
            )
        
        # Handle both sync and async iterators
        if hasattr(audio_stream, '__aiter__'):
            async for chunk in audio_stream:
                if isinstance(chunk, bytes) and len(chunk) > 0:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    if chunk_count == 1:
                        logger.info(f"⚡ SDK first byte: {(time.time()-t0)*1000:.0f}ms")
                    yield chunk
        elif hasattr(audio_stream, '__iter__'):
            for chunk in audio_stream:
                if isinstance(chunk, bytes) and len(chunk) > 0:
                    chunk_count += 1
                    total_bytes += len(chunk)
                    if chunk_count == 1:
                        logger.info(f"⚡ SDK first byte: {(time.time()-t0)*1000:.0f}ms")
                    yield chunk
        elif isinstance(audio_stream, bytes):
            # Single response (non-streaming)
            if len(audio_stream) > 0:
                chunk_count = 1
                total_bytes = len(audio_stream)
                logger.info(f"⚡ SDK single response: {(time.time()-t0)*1000:.0f}ms")
                yield audio_stream
        
        logger.info(f"✅ SDK streaming: {chunk_count} chunks, {total_bytes} bytes in {(time.time()-t0)*1000:.0f}ms")

    async def _stream_with_websocket(self, text: str, voice_id: str = None) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS using raw WebSocket (fallback if SDK not installed).
        """
        t0 = time.time()
        effective_voice = voice_id or self.voice_id
        url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{effective_voice}/multi-stream-input"
            f"?model_id={self.model}&output_format=mp3_22050_32&optimize_streaming_latency=4&auto_mode=true"
        )

        async with websockets.connect(
            url,
            additional_headers={"xi-api-key": self.api_key},
            max_size=16 * 1024 * 1024,
            ping_interval=25,
            ping_timeout=15,
        ) as ws:
            context_id = "conv_1"
            await ws.send(json.dumps({
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                "context_id": context_id,
            }))
            await ws.send(json.dumps({"text": text, "context_id": context_id}))
            await ws.send(json.dumps({"flush": True, "context_id": context_id}))

            total_received = 0
            chunk_count = 0
            async for message in ws:
                try:
                    data = json.loads(message)
                    if data.get("audio"):
                        audio_bytes = base64.b64decode(data["audio"])
                        if audio_bytes:
                            chunk_count += 1
                            total_received += len(audio_bytes)
                            if chunk_count == 1:
                                logger.info(f"⚡ WS first byte: {(time.time()-t0)*1000:.0f}ms")
                            yield audio_bytes
                    if data.get("is_final") or data.get("isFinal"):
                        break
                except json.JSONDecodeError:
                    if isinstance(message, bytes) and len(message) > 0:
                        chunk_count += 1
                        total_received += len(message)
                        yield message
            
            if total_received == 0:
                raise Exception("No audio data received from WebSocket streaming")
            logger.info(f"✅ WS streaming: {chunk_count} chunks, {total_received} bytes in {(time.time()-t0)*1000:.0f}ms")
    
    async def _stream_with_edge_tts(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Free TTS fallback using Microsoft Edge TTS.
        No API key needed, good quality, ~500-1000ms first byte.
        """
        t0 = time.time()
        total_bytes = 0
        chunk_count = 0
        
        voice = "en-US-AriaNeural"  # Natural female voice
        communicate = edge_tts.Communicate(text, voice)
        
        async for chunk_data in communicate.stream():
            if chunk_data["type"] == "audio":
                audio_bytes = chunk_data["data"]
                if audio_bytes and len(audio_bytes) > 0:
                    chunk_count += 1
                    total_bytes += len(audio_bytes)
                    if chunk_count == 1:
                        logger.info(f"⚡ Edge TTS first byte: {(time.time()-t0)*1000:.0f}ms")
                    yield audio_bytes
        
        logger.info(f"✅ Edge TTS: {chunk_count} chunks, {total_bytes} bytes in {(time.time()-t0)*1000:.0f}ms")

    async def text_to_speech(self, text: str, voice_id: str = None) -> bytes:
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
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id or self.voice_id}"
        
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
