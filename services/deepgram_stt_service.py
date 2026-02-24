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
        self._audio_received = False  # Track if real audio has been sent

    @property
    def enabled(self) -> bool:
        """Check if Deepgram STT is enabled (API key present)."""
        return bool(self.api_key)

    async def start(self) -> bool:
        """Open Deepgram WebSocket connection and start streaming."""
        if not self.enabled:
            logger.warning("❌ Deepgram STT disabled: missing DEEPGRAM_API_KEY")
            return False

        # Deepgram Flux v2 — proper turn-taking model (matches AUM reference)
        # Flux v2 emits TurnInfo events (StartOfTurn, EndOfTurn, EagerEndOfTurn)
        # which are far more reliable than v1's basic SpeechStarted VAD
        params = {
            "encoding": "linear16",
            "sample_rate": str(self.sample_rate),
            "model": "flux-general-en",
        }
        
        url = "wss://api.deepgram.com/v2/listen?" + "&".join([f"{k}={v}" for k, v in params.items()])
        logger.info(f"🔗 Deepgram URL: {url}")

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

    def _is_noise_transcript(self, text: str) -> bool:
        """Filter out transcripts that are likely noise, not real speech."""
        cleaned = text.strip().lower()
        if not cleaned:
            return True
        # Reject single-char transcripts — likely noise artifacts
        if len(cleaned) <= 1:
            logger.debug(f"🔇 Noise filter: too short '{cleaned}'")
            return True
        # Only filter actual filler sounds / noise artifacts
        # Do NOT filter valid words like 'yes', 'no', 'ok', 'continue'
        noise_sounds = {
            'um', 'uh', 'hmm', 'hm', 'mm', 'mhm', 'ah', 'eh',
        }
        words = cleaned.split()
        if len(words) == 1 and words[0].rstrip('.!?,') in noise_sounds:
            logger.debug(f"🔇 Noise filter: filler sound '{cleaned}'")
            return True
        return False

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
                logger.info("🗣️ StartOfTurn")
            elif event == "EagerEndOfTurn":
                # Medium-confidence end; surface as partial-final to start LLM early if desired
                if transcript.strip() and not self._is_noise_transcript(transcript):
                    await self._queue.put({"type": "partial", "text": transcript, "language": self.language})
                    logger.info(f"⚡ EagerEndOfTurn partial: '{transcript}'")
            elif event == "TurnResumed":
                # User kept talking; nothing to emit besides a debug
                logger.debug("🔄 TurnResumed")
            elif event == "EndOfTurn":
                if transcript.strip() and not self._is_noise_transcript(transcript):
                    await self._queue.put({"type": "final", "text": transcript, "language": self.language})
                    logger.info(f"✅ EndOfTurn final: '{transcript}'")
                elif transcript.strip():
                    logger.debug(f"🔇 Filtered noise transcript: '{transcript}'")
                await self._queue.put({"type": "utterance_end"})
                logger.info("🔇 Utterance ended (EndOfTurn)")
            elif event == "Update":
                if transcript.strip():
                    await self._queue.put({"type": "partial", "text": transcript, "language": self.language})
                    logger.debug(f"📝 Update partial: '{transcript}'")
            else:
                logger.debug(f"📨 TurnInfo: {event}")

        # v1 SpeechStarted event (vad_events=true)
        elif message_type == "SpeechStarted":
            await self._queue.put({"type": "speech_started"})
            logger.info("🗣️ SpeechStarted (VAD v1)")

        # v1 UtteranceEnd event (utterance_end_ms param)
        elif message_type == "UtteranceEnd":
            await self._queue.put({"type": "utterance_end"})
            logger.debug("🔇 UtteranceEnd (v1)")

        elif message_type in ("Connected", "Metadata"):
            request_id = data.get("request_id")
            logger.info(f"✅ Deepgram session started: {request_id}")

        elif message_type == "Error":
            error_msg = data.get("description", data)
            logger.error(f"❌ Deepgram error: {error_msg}")

        # v1 Results messages (primary format for nova-2)
        elif message_type == "Results":
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [])
            if alternatives:
                alternative = alternatives[0]
                transcript = alternative.get("transcript", "")
                is_final = data.get("is_final", False)
                speech_final = data.get("speech_final", False)
                
                if transcript.strip() and not self._is_noise_transcript(transcript):
                    if is_final or speech_final:
                        await self._queue.put({"type": "final", "text": transcript, "language": self.language})
                        logger.info(f"✅ v1 final: '{transcript}'")
                    else:
                        await self._queue.put({"type": "partial", "text": transcript, "language": self.language})
                        logger.info(f"📝 v1 partial: '{transcript}'")
                elif transcript.strip():
                    logger.info(f"🔇 v1 noise filtered: '{transcript}'")

        else:
            logger.info(f"📨 Unknown Deepgram message type: {message_type} — keys: {list(data.keys())}")

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
