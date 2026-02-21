"""
Transcription Service for ProfAI
Handles audio-to-text conversion using multiple providers
"""

import logging
import io
import tempfile
import os
from typing import Optional
import asyncio

class TranscriptionService:
    """Handles audio transcription using multiple providers."""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        
    async def transcribe_audio(self, audio_buffer: io.BytesIO, language: str = "en-IN") -> Optional[str]:
        """
        Transcribe audio to text using available transcription services.
        
        Args:
            audio_buffer: Audio data as BytesIO
            language: Language code for transcription
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            logging.info(f"🎤 Starting audio transcription (language: {language})")
            logging.info(f"   Audio size: {audio_buffer.getbuffer().nbytes} bytes")
            
            # Try different transcription methods in order of preference
            transcription_methods = [
                self._transcribe_with_openai_whisper,
                self._transcribe_with_sarvam,
                self._transcribe_with_speech_recognition
            ]
            
            for method in transcription_methods:
                try:
                    # Reset buffer position
                    audio_buffer.seek(0)
                    
                    result = await method(audio_buffer, language)
                    if result and result.strip():
                        logging.info(f"✅ Transcription successful: {len(result)} characters")
                        logging.info(f"   Preview: {result[:100]}...")
                        return result.strip()
                        
                except Exception as e:
                    logging.warning(f"Transcription method failed: {method.__name__}: {e}")
                    continue
            
            logging.error("❌ All transcription methods failed")
            return None
            
        except Exception as e:
            logging.error(f"❌ Error in transcription service: {e}")
            return None
    
    async def _transcribe_with_openai_whisper(self, audio_buffer: io.BytesIO, language: str) -> Optional[str]:
        """Transcribe using OpenAI Whisper API."""
        try:
            import openai
            from config import OPENAI_API_KEY
            
            if not OPENAI_API_KEY:
                logging.info("OpenAI API key not available")
                return None
            
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Create temporary file for Whisper API
            temp_path = os.path.join(self.temp_dir, f"temp_audio_{os.getpid()}.wav")
            
            try:
                # Write audio to temporary file
                with open(temp_path, 'wb') as f:
                    f.write(audio_buffer.getvalue())
                
                # Transcribe with Whisper
                with open(temp_path, 'rb') as audio_file:
                    # Map language codes
                    whisper_language = self._map_language_for_whisper(language)
                    
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=whisper_language,
                        response_format="text"
                    )
                
                logging.info("✅ OpenAI Whisper transcription successful")
                return transcript
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                        
        except Exception as e:
            logging.warning(f"OpenAI Whisper transcription failed: {e}")
            return None
    
    async def _transcribe_with_sarvam(self, audio_buffer: io.BytesIO, language: str) -> Optional[str]:
        """Transcribe using Sarvam AI speech-to-text."""
        try:
            # Check if Sarvam service is available
            from services.sarvam_service import SarvamService
            from config import SARVAM_API_KEY
            
            if not SARVAM_API_KEY:
                logging.info("Sarvam API key not available")
                return None
            
            sarvam_service = SarvamService()
            
            # Use Sarvam's speech-to-text if available
            # Note: This would need to be implemented in SarvamService
            # For now, we'll skip this method
            logging.info("Sarvam transcription not yet implemented")
            return None
            
        except Exception as e:
            logging.warning(f"Sarvam transcription failed: {e}")
            return None
    
    async def _transcribe_with_speech_recognition(self, audio_buffer: io.BytesIO, language: str) -> Optional[str]:
        """Transcribe using speech_recognition library with Google Speech Recognition."""
        try:
            import speech_recognition as sr
            
            # Create recognizer
            recognizer = sr.Recognizer()
            
            # Create temporary file
            temp_path = os.path.join(self.temp_dir, f"temp_audio_{os.getpid()}.wav")
            
            try:
                # Write audio to temporary file
                with open(temp_path, 'wb') as f:
                    f.write(audio_buffer.getvalue())
                
                # Load audio file
                with sr.AudioFile(temp_path) as source:
                    # Adjust for ambient noise
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    # Record the audio
                    audio_data = recognizer.record(source)
                
                # Map language code for Google Speech Recognition
                google_language = self._map_language_for_google(language)
                
                # Transcribe using Google Speech Recognition
                text = recognizer.recognize_google(audio_data, language=google_language)
                
                logging.info("✅ Google Speech Recognition transcription successful")
                return text
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                        
        except ImportError:
            logging.info("speech_recognition library not available")
            return None
        except Exception as e:
            logging.warning(f"Google Speech Recognition failed: {e}")
            return None
    
    def _map_language_for_whisper(self, language: str) -> str:
        """Map language codes for OpenAI Whisper."""
        language_map = {
            'en-IN': 'en',
            'hi-IN': 'hi',
            'ta-IN': 'ta',
            'te-IN': 'te',
            'kn-IN': 'kn',
            'ml-IN': 'ml',
            'gu-IN': 'gu',
            'mr-IN': 'mr',
            'bn-IN': 'bn',
            'pa-IN': 'pa',
            'or-IN': 'or',
            'as-IN': 'as'
        }
        return language_map.get(language, 'en')
    
    def _map_language_for_google(self, language: str) -> str:
        """Map language codes for Google Speech Recognition."""
        # Google uses the full language codes
        language_map = {
            'en-IN': 'en-IN',
            'hi-IN': 'hi-IN',
            'ta-IN': 'ta-IN',
            'te-IN': 'te-IN',
            'kn-IN': 'kn-IN',
            'ml-IN': 'ml-IN',
            'gu-IN': 'gu-IN',
            'mr-IN': 'mr-IN',
            'bn-IN': 'bn-IN',
            'pa-IN': 'pa-IN'
        }
        return language_map.get(language, 'en-IN')
    
    async def get_transcription_info(self, audio_buffer: io.BytesIO) -> dict:
        """Get information about the audio for transcription."""
        try:
            audio_size = audio_buffer.getbuffer().nbytes
            duration_estimate = audio_size / (16000 * 2)  # Rough estimate for 16kHz 16-bit mono
            
            return {
                "audio_size_bytes": audio_size,
                "audio_size_mb": round(audio_size / (1024 * 1024), 2),
                "estimated_duration_seconds": round(duration_estimate, 1),
                "estimated_duration_minutes": round(duration_estimate / 60, 1)
            }
        except Exception as e:
            logging.error(f"Error getting transcription info: {e}")
            return {}