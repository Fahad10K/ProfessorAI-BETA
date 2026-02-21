"""
Audio Service - Handles audio transcription and generation
"""

import io
import logging
from typing import Optional
import config
from services.sarvam_service import SarvamService
from utils.connection_monitor import is_client_connected, is_normal_closure

logger = logging.getLogger(__name__)

class AudioService:
    """Service for audio processing operations with multiple provider support."""
    
    def __init__(self):
        # Get provider preferences from config
        self.stt_provider = config.AUDIO_STT_PROVIDER
        self.tts_provider = config.AUDIO_TTS_PROVIDER
        
        # Initialize Sarvam (always available as fallback)
        self.sarvam_service = SarvamService()
        
        # Initialize Deepgram STT (if enabled)
        self.deepgram_service = None
        if self.stt_provider == "deepgram":
            try:
                from services.deepgram_stt_service import DeepgramSTTService
                self.deepgram_service = DeepgramSTTService()
                if self.deepgram_service.enabled:
                    logger.info("✅ Deepgram STT initialized")
                else:
                    logger.warning("⚠️ Deepgram STT disabled (no API key), falling back to Sarvam")
                    self.stt_provider = "sarvam"
            except Exception as e:
                logger.error(f"❌ Failed to initialize Deepgram: {e}")
                self.stt_provider = "sarvam"
        
        # Initialize ElevenLabs TTS (if enabled)
        self.elevenlabs_service = None
        if self.tts_provider == "elevenlabs":
            try:
                from services.elevenlabs_service import ElevenLabsService
                self.elevenlabs_service = ElevenLabsService()
                if self.elevenlabs_service.enabled:
                    logger.info("✅ ElevenLabs TTS initialized")
                else:
                    logger.warning("⚠️ ElevenLabs TTS disabled (no API key), falling back to Sarvam")
                    self.tts_provider = "sarvam"
            except Exception as e:
                logger.error(f"❌ Failed to initialize ElevenLabs: {e}")
                self.tts_provider = "sarvam"
        
        logger.info(f"📡 Audio Service: STT={self.stt_provider}, TTS={self.tts_provider}")
    
    async def transcribe_audio(self, audio_file_buffer: io.BytesIO, language: Optional[str] = None) -> str:
        """
        Transcribe audio to text using the configured provider.
        Falls back to Sarvam if primary provider fails.
        
        Args:
            audio_file_buffer: Audio data as BytesIO
            language: Language code (e.g., "en-IN")
            
        Returns:
            Transcribed text
        """
        effective_language = language or config.SUPPORTED_LANGUAGES[0]['code']
        
        # Try primary provider first
        if self.stt_provider == "deepgram" and self.deepgram_service:
            try:
                # Note: Deepgram is for real-time streaming.
                # For file-based transcription, we still use Sarvam or fallback to OpenAI Whisper
                logger.info("ℹ️ Deepgram is for streaming; using Sarvam for file transcription")
                return await self.sarvam_service.transcribe_audio(audio_file_buffer, effective_language)
            except Exception as e:
                logger.warning(f"⚠️ Deepgram transcription failed: {e}, falling back to Sarvam")
        
        # Default/fallback to Sarvam
        return await self.sarvam_service.transcribe_audio(audio_file_buffer, effective_language)
    
    async def generate_audio_from_text(self, text: str, language: Optional[str] = None, ultra_fast: bool = False) -> io.BytesIO:
        """
        Generate audio from text using the configured provider.
        Falls back to Sarvam if primary provider fails.
        
        Args:
            text: Text to convert to speech
            language: Language code (optional, ElevenLabs doesn't use this)
            ultra_fast: Use fastest generation mode (for Sarvam)
            
        Returns:
            Audio data as BytesIO
        """
        effective_language = language or config.SUPPORTED_LANGUAGES[0]['code']
        
        # Try ElevenLabs first if configured
        if self.tts_provider == "elevenlabs" and self.elevenlabs_service:
            try:
                logger.info(f"🎙️ Generating audio with ElevenLabs: {len(text)} chars")
                audio_buffer = await self.elevenlabs_service.generate_audio_from_text(text, language)
                logger.info(f"✅ ElevenLabs audio generated: {audio_buffer.getbuffer().nbytes} bytes")
                return audio_buffer
            except Exception as e:
                logger.error(f"❌ ElevenLabs TTS failed: {e}, falling back to Sarvam")
        
        # Fallback to Sarvam
        logger.info(f"🎙️ Generating audio with Sarvam: {len(text)} chars")
        if ultra_fast:
            return await self.sarvam_service.generate_audio_ultra_fast(
                text, 
                effective_language, 
                config.SARVAM_TTS_SPEAKER
            )
        else:
            return await self.sarvam_service.generate_audio(
                text, 
                effective_language, 
                config.SARVAM_TTS_SPEAKER
            )
    
    async def stream_audio_from_text(self, text: str, language: Optional[str] = None, websocket=None):
        """
        Stream audio chunks as they're generated for real-time playback.
        Tries primary TTS provider first, falls back to Sarvam on error.
        
        Args:
            text: Text to convert to speech
            language: Language code (optional)
            websocket: WebSocket connection for error handling
            
        Yields:
            Audio chunks as bytes
        """
        effective_language = language or config.SUPPORTED_LANGUAGES[0]['code']
        
        # Try ElevenLabs streaming first if configured
        if self.tts_provider == "elevenlabs" and self.elevenlabs_service:
            try:
                logger.info(f"🎙️ Streaming audio with ElevenLabs: {len(text)} chars")
                chunk_count = 0
                async for audio_chunk in self.elevenlabs_service.text_to_speech_stream(text):
                    if audio_chunk and len(audio_chunk) > 0:
                        chunk_count += 1
                        logger.debug(f"📦 ElevenLabs chunk #{chunk_count}: {len(audio_chunk)} bytes")
                        yield audio_chunk
                logger.info(f"✅ ElevenLabs streaming completed: {chunk_count} chunks")
                return  # Success, exit
            except Exception as e:
                logger.error(f"❌ ElevenLabs streaming failed: {e}, falling back to Sarvam")
        
        # Fallback to Sarvam streaming
        try:
            logger.info(f"🎙️ Streaming audio with Sarvam: {len(text)} chars")
            async for audio_chunk in self.sarvam_service.stream_audio_generation(
                text, 
                effective_language, 
                config.SARVAM_TTS_SPEAKER,
                websocket
            ):
                if audio_chunk and len(audio_chunk) > 0:
                    yield audio_chunk
        except Exception as e:
            error_msg = str(e)
            # Check if this is a normal disconnection
            if self._is_normal_disconnection(error_msg):
                logger.info(f"🔌 Client disconnected during audio streaming: {e}")
                logger.info(f"⚠️ Stopping audio streaming - client no longer connected")
                return
            else:
                logger.error(f"❌ Error in audio streaming: {e}")
                # Only fallback for actual errors, not disconnections
                if not websocket or not self._is_client_disconnected(websocket):
                    try:
                        audio_buffer = await self.generate_audio_from_text(text, language, ultra_fast=True)
                        if audio_buffer and audio_buffer.getbuffer().nbytes > 0:
                            # Yield the entire audio as a single chunk
                            yield audio_buffer.getvalue()
                    except Exception as fallback_error:
                        logger.error(f"Fallback audio generation also failed: {fallback_error}")
                        # Return empty generator
                        return
    
    def _is_client_disconnected(self, websocket) -> bool:
        """Check if WebSocket client is disconnected."""
        try:
            if not websocket:
                return False
            
            # Check if WebSocket is closed or closing
            if hasattr(websocket, 'closed') and websocket.closed:
                return True
            
            if hasattr(websocket, 'state'):
                # WebSocket states: CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3
                return websocket.state in [2, 3]  # CLOSING or CLOSED
            
            return False
        except Exception:
            # If we can't check the state, assume disconnected for safety
            return True
    
    def _is_normal_disconnection(self, error_msg: str) -> bool:
        """Check if error message indicates a normal client disconnection."""
        if not error_msg:
            return False
        
        error_msg = str(error_msg).lower()
        
        # Check for normal WebSocket closure codes
        normal_codes = ["1000", "1001"]  # OK, Going Away
        for code in normal_codes:
            if code in error_msg:
                return True
        
        # Check for common disconnection phrases
        disconnection_phrases = [
            "connection closed",
            "client disconnected", 
            "going away",
            "connection lost"
        ]
        
        for phrase in disconnection_phrases:
            if phrase in error_msg:
                return True
        
        return False