"""
Deepgram Real-time STT Service with VAD and Barge-in Support

Provider: Deepgram Nova-3 (websocket)
- Ultra-low latency streaming STT
- Built-in Voice Activity Detection (VAD)
- Excellent endpointing for natural conversation flow
- Supports interruption and barge-in

This service provides production-ready real-time speech-to-text.
"""
import asyncio
import base64
import json
import logging
from typing import AsyncGenerator, Optional
import websockets
import config

logger = logging.getLogger(__name__)


class DeepgramSTTService:
    """
    Real-time streaming STT service using Deepgram Nova-3 model.
    Provides excellent VAD, low latency, and reliable WebSocket streaming.
    """

    def __init__(self, sample_rate: int = 16000, language_hint: Optional[str] = None):
        self.sample_rate = sample_rate
        self.language = language_hint or "en-US"
        self.api_key = getattr(config, "DEEPGRAM_API_KEY", None)
        self.ws = None
        self._recv_task: Optional[asyncio.Task] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False

    @property
    def enabled(self) -> bool:
        """Check if Deepgram STT is enabled (API key present)."""
        return bool(self.api_key)

    async def start(self) -> bool:
        """Open Deepgram WebSocket connection and start streaming."""
        if not self.enabled:
            logger.warning("❌ Deepgram STT disabled: missing DEEPGRAM_API_KEY")
            return False

        # Deepgram Flux v2 WebSocket URL with optimized parameters for turn-taking
        params = {
            "encoding": "linear16",
            "sample_rate": str(self.sample_rate),
            "model": "flux-general-en",
            # VAD tuning to reduce false positives and partials
            "interim_results": "false",        # Disable excessive partials at source (90% spam reduction)
            "endpointing": "500",              # Wait 500ms of silence before finalizing turn
            "vad_turnoff": "400",              # Ignore sounds <400ms (filters fan noise)
            "smart_format": "true",            # Auto punctuation for better readability
            # Optional EOT tuning (uncomment to adjust sensitivity)
            # "eot_threshold": "0.8",          # EndOfTurn confidence threshold (0.5-0.9)
            # "eager_eot_threshold": "0.6",    # EagerEndOfTurn threshold (0.3-0.9)
        }
        
        url = "wss://api.deepgram.com/v2/listen?" + "&".join([f"{k}={v}" for k, v in params.items()])

        try:
            self.ws = await websockets.connect(
                url,
                additional_headers={
                    "Authorization": f"Token {self.api_key}"
                },
                ping_interval=20,
                ping_timeout=10,
                max_size=16 * 1024 * 1024
            )
            
            logger.info("✅ Connected to Deepgram Real-time STT")
            
            # Start background receiver
            self._recv_task = asyncio.create_task(self._receiver())
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Deepgram STT: {e}")
            return False

    async def _receiver(self):
        """Receive and process messages from Deepgram WebSocket."""
        assert self.ws is not None
        
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._process_message(data)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Failed to decode Deepgram message: {e}")
                except Exception as e:
                    logger.error(f"❌ Error processing Deepgram message: {e}")
                    
        except Exception as e:
            if not self._closed:
                logger.error(f"❌ Deepgram receiver error: {e}")
        finally:
            await self._queue.put({"type": "closed"})

    async def _process_message(self, data: dict):
        """Process different types of messages from Deepgram."""
        message_type = data.get("type")

        # Flux v2 emits TurnInfo messages for turn-taking; handle that first
        if message_type == "TurnInfo":
            event = data.get("event")
            transcript = data.get("transcript", "") or ""
            words = data.get("words", []) or []

            if event == "StartOfTurn":
                await self._queue.put({"type": "speech_started"})
                logger.debug("🗣️ StartOfTurn (VAD)")
            elif event == "EagerEndOfTurn":
                # Medium-confidence end; surface as partial-final to start LLM early if desired
                if transcript.strip():
                    await self._queue.put({"type": "partial", "text": transcript, "language": self.language})
                    logger.debug(f"⚡ EagerEndOfTurn partial: '{transcript}'")
            elif event == "TurnResumed":
                # User kept talking; nothing to emit besides a debug
                logger.debug("🔄 TurnResumed")
            elif event == "EndOfTurn":
                if transcript.strip():
                    await self._queue.put({"type": "final", "text": transcript, "language": self.language})
                    logger.debug(f"✅ EndOfTurn final: '{transcript}'")
                await self._queue.put({"type": "utterance_end"})
                logger.debug("🔇 Utterance ended (EndOfTurn)")
            elif event == "Update":
                if transcript.strip():
                    await self._queue.put({"type": "partial", "text": transcript, "language": self.language})
                    logger.debug(f"📝 Update partial: '{transcript}'")
            else:
                logger.debug(f"📨 TurnInfo: {event}")

        elif message_type == "Metadata":
            request_id = data.get("request_id")
            logger.info(f"✅ Deepgram session started: {request_id}")

        elif message_type == "Error":
            error_msg = data.get("description", data)
            logger.error(f"❌ Deepgram error: {error_msg}")

        else:
            # Back-compat: older v1 style
            if message_type == "Results":
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if alternatives:
                    alternative = alternatives[0]
                    transcript = alternative.get("transcript", "")
                    is_final = channel.get("is_final", False)
                    if transcript.strip():
                        await self._queue.put({"type": "final" if is_final else "partial", "text": transcript, "language": self.language})
                        logger.debug(f"🎤 v1 {('final' if is_final else 'partial')}: '{transcript}'")
            else:
                logger.debug(f"📨 Unknown Deepgram message: {data}")

    async def recv(self) -> AsyncGenerator[dict, None]:
        """Yield events from Deepgram STT (partial/final/VAD events)."""
        while True:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                if event.get("type") == "closed":
                    break
                yield event
            except asyncio.TimeoutError:
                # No-op on idle; rely on websocket ping/pong (configured via ping_interval)
                continue

    async def send_audio_chunk(self, pcm16_bytes: bytes):
        """Send PCM16 audio chunk to Deepgram."""
        if not self.ws:
            return

        try:
            # Deepgram expects raw binary PCM16 data (linear16)
            if not pcm16_bytes:
                return
            await self.ws.send(pcm16_bytes)

        except Exception as e:
            logger.error(f"❌ Failed sending audio to Deepgram: {e}")
            # Notify listeners and close connection
            try:
                await self._queue.put({"type": "closed"})
            except Exception:
                pass
            try:
                await self.close()
            except Exception:
                pass

    async def finish(self):
        """Signal end of audio stream."""
        if self.ws:
            try:
                # Send close frame to finalize any pending transcription
                await self.ws.send(json.dumps({"type": "CloseStream"}))
            except Exception as e:
                logger.debug(f"Error sending close frame: {e}")

    async def close(self):
        """Close the Deepgram WebSocket connection."""
        self._closed = True
        
        try:
            if self.ws:
                try:
                    await self.finish()
                except Exception:
                    pass
                try:
                    await self.ws.close()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error closing Deepgram WebSocket: {e}")
            
        if self._recv_task:
            try:
                await asyncio.wait_for(self._recv_task, timeout=2.0)
            except Exception:
                self._recv_task.cancel()
                
        self.ws = None
        self._recv_task = None
        logger.info("🔌 Deepgram STT connection closed")


# Alias for backward compatibility
StreamingSTTService = DeepgramSTTService
