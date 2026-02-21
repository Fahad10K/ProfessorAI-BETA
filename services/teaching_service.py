"""
Teaching Service - Converts course content into proper teaching format with streaming support
"""

import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from services.llm_service import LLMService

class TeachingService:
    """Service for converting course content into teaching-friendly format."""
    
    def __init__(self):
        self.llm_service = LLMService()
        
    async def generate_teaching_content_stream(
        self, 
        module_title: str, 
        sub_topic_title: str, 
        raw_content: str,
        language: str = "en-IN"
    ) -> AsyncGenerator[str, None]:
        """
        Stream teaching content generation in real-time chunks.
        
        Args:
            module_title: The module/week title
            sub_topic_title: The specific sub-topic title
            raw_content: Raw content from the course JSON
            language: Language for the teaching content
            
        Yields:
            Chunks of teaching content as they are generated
        """
        try:
            # Create a comprehensive teaching prompt
            teaching_prompt = self._create_teaching_prompt(
                module_title, sub_topic_title, raw_content, language
            )
            
            logging.info(f"Starting streaming content generation for: {sub_topic_title}")
            
            # Stream teaching content using LLM
            async for chunk in self.llm_service.generate_response_stream(teaching_prompt):
                if chunk.strip():  # Only yield non-empty chunks
                    yield chunk
            
            logging.info(f"Completed streaming content generation for: {sub_topic_title}")
            
        except Exception as e:
            logging.error(f"Error in streaming teaching content: {e}")
            # Fallback to basic content if streaming fails
            fallback_content = self._create_fallback_content(module_title, sub_topic_title, raw_content)
            yield fallback_content

    async def generate_teaching_content(
        self, 
        module_title: str, 
        sub_topic_title: str, 
        raw_content: str,
        language: str = "en-IN"
    ) -> str:
        """
        Convert raw course content into a proper teaching format with timeout handling.
        
        Args:
            module_title: The module/week title
            sub_topic_title: The specific sub-topic title
            raw_content: Raw content from the course JSON
            language: Language for the teaching content
            
        Returns:
            Formatted teaching content ready for TTS
        """
        try:
            # Truncate content if too long to avoid timeout
            if len(raw_content) > 6000:
                raw_content = raw_content[:5500] + "..."
                logging.info(f"Truncated content to 5500 chars for faster processing")
            
            # Create a comprehensive teaching prompt
            teaching_prompt = self._create_teaching_prompt(
                module_title, sub_topic_title, raw_content, language
            )
            
            # Generate teaching content using LLM with timeout
            teaching_content = await asyncio.wait_for(
                self.llm_service.generate_response(teaching_prompt, temperature=1),
                timeout=5.0  # 5 second timeout for LLM generation
            )
            
            # Post-process the content for better TTS delivery
            formatted_content = self._format_for_tts(teaching_content)
            
            logging.info(f"Generated teaching content for: {sub_topic_title} ({len(formatted_content)} chars)")
            return formatted_content
            
        except asyncio.TimeoutError:
            logging.warning(f"Teaching content generation timeout for: {sub_topic_title}")
            return self._create_fallback_content(module_title, sub_topic_title, raw_content)
        except Exception as e:
            logging.error(f"Error generating teaching content: {e}")
            # Fallback to basic format if LLM fails
            return self._create_fallback_content(module_title, sub_topic_title, raw_content)
    
    def _create_teaching_prompt(
        self, 
        module_title: str, 
        sub_topic_title: str, 
        raw_content: str,
        language: str
    ) -> str:
        """Create a comprehensive prompt for teaching content generation."""
        
        language_instruction = self._get_language_instruction(language)
        
        prompt = f"""You are ProfessorAI, an expert educator teaching a LIVE CLASSROOM. Your task is to transform the given course content into an engaging, comprehensive teaching lesson that will be delivered via TEXT-TO-SPEECH audio.

CONTEXT:
- Module: {module_title}
- Topic: {sub_topic_title}
- Language: {language_instruction}
- Delivery: Audio (Text-to-Speech)

RAW CONTENT TO TEACH:
{raw_content}

CRITICAL TTS PRONUNCIATION RULES:
1. **NEVER use abbreviations or acronyms** - Always spell them out:
   - Write "Artificial Intelligence" NOT "A.I" or "AI"
   - Write "Machine Learning" NOT "ML"
   - Write "Natural Language Processing" NOT "NLP"
   - Write "Application Programming Interface" NOT "API"
   - Write "et cetera" NOT "etc"
   - Write "for example" NOT "e.g."
   - Write "that is" NOT "i.e."
   - Write "versus" NOT "vs"
2. Write numbers as words for better pronunciation:
   - Write "twenty twenty-four" NOT "2024"
   - Write "one hundred" NOT "100"
3. Avoid special characters and symbols - spell them out:
   - Write "at" NOT "@"
   - Write "and" NOT "&"
   - Write "percent" NOT "%"

LIVE CLASSROOM TEACHING PRINCIPLES:
1. **Engage Like a Real Teacher:**
   - Welcome students warmly as if they're sitting in front of you
   - Use phrases like "Hello students", "Let me explain", "Let's explore together"
   - Ask rhetorical questions: "Have you ever wondered why?", "Can you imagine?"
   - Show enthusiasm: "This is fascinating!", "Here's the exciting part!"

2. **Structure Like a Live Lecture:**
   - Start with a hook to grab attention
   - Provide context and relevance ("Why should you care about this?")
   - Break concepts into digestible chunks
   - Use transitions: "Now that we understand X, let's move to Y"
   - Summarize periodically: "So far, we've learned..."

3. **Teach for Understanding:**
   - Explain concepts from first principles
   - Use everyday analogies and real-world examples
   - Relate abstract concepts to familiar experiences
   - Build concepts progressively - don't assume prior knowledge
   - Anticipate confusion and address it proactively

4. **Make it Conversational:**
   - Speak as if talking to a friend, not reading a textbook
   - Use simple, clear language
   - Avoid jargon unless you explain it first
   - Use "we" and "you" to create connection: "Let's discover", "You'll notice"
   - Add personality and warmth

5. **Encourage Active Learning:**
   - Pause for reflection: "Take a moment to think about..."
   - Encourage mental practice: "Try to visualize...", "Imagine if..."
   - Connect to student experiences: "You might have seen this when..."
   - Preview what's coming: "In the next part, we'll explore..."

6. **Maintain Energy and Pace:**
   - Vary sentence length and structure
   - Use emphasis naturally: "This is REALLY important"
   - Include natural pauses for comprehension
   - Don't rush - teach at a comfortable pace

7. **Be a Mentor, Not Just an Instructor:**
   - Show passion for the subject
   - Share insights and "aha" moments
   - Encourage curiosity and further exploration
   - Make students feel capable: "You can master this"
   - End with encouragement and next steps

RESPONSE STRUCTURE:
1. Warm Welcome ("Hello students! Welcome to today's lesson on [topic]")
2. Hook/Motivation (Why is this interesting or important?)
3. Core Content (Broken into 3-5 digestible sections with clear transitions)
4. Real-World Application (Where will you see this in practice?)
5. Summary ("Let's recap what we've learned today")
6. Encouragement & Closing ("I hope this was helpful. Feel free to ask questions!")

RESPONSE FORMAT:
Provide ONLY the teaching content, ready to be converted to speech. Do NOT include:
- Meta-commentary or instructions
- Stage directions or formatting notes
- Abbreviations or acronyms (spell everything out)
- Any text that shouldn't be spoken aloud

{language_instruction}

Begin teaching the live classroom now:"""

        return prompt
    
    def _get_language_instruction(self, language: str) -> str:
        """Get language-specific instruction for the prompt."""
        language_map = {
            "en-IN": "Respond in clear, natural English suitable for Indian students.",
            "hi-IN": "हिंदी में स्पष्ट और प्राकृतिक भाषा में उत्तर दें।",
            "ta-IN": "தெளிவான மற்றும் இயல்பான தமிழில் பதிலளிக்கவும்।",
            "te-IN": "స్పష్టమైన మరియు సహజమైన తెలుగులో సమాధానం ఇవ్వండి.",
            "kn-IN": "ಸ್ಪಷ್ಟ ಮತ್ತು ನೈಸರ್ಗಿಕ ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ.",
            "ml-IN": "വ്യക്തവും സ്വാഭാവികവുമായ മലയാളത്തിൽ ഉത്തരം നൽകുക.",
            "gu-IN": "સ્પષ્ટ અને કુદરતી ગુજરાતીમાં જવાબ આપો.",
            "mr-IN": "स्पष्ट आणि नैसर्गिक मराठीत उत्तर द्या.",
            "bn-IN": "স্পষ্ট এবং প্রাকৃতিক বাংলায় উত্তর দিন.",
            "pa-IN": "ਸਪੱਸ਼ਟ ਅਤੇ ਕੁਦਰਤੀ ਪੰਜਾਬੀ ਵਿੱਚ ਜਵਾਬ ਦਿਓ.",
            "ur-IN": "واضح اور فطری اردو میں جواب دیں۔"
        }
        return language_map.get(language, "Respond in clear, natural English.")
    
    def _format_for_tts(self, content: str) -> str:
        """Format the content for better TTS delivery and fix pronunciation issues."""
        import re
        
        # Fix common abbreviations that TTS mispronounces
        replacements = {
            # AI/ML abbreviations
            r'\bA\.I\.?\b': 'Artificial Intelligence',
            r'\bAI\b': 'Artificial Intelligence',
            r'\bM\.L\.?\b': 'Machine Learning',
            r'\bML\b': 'Machine Learning',
            r'\bN\.L\.P\.?\b': 'Natural Language Processing',
            r'\bNLP\b': 'Natural Language Processing',
            r'\bA\.P\.I\.?\b': 'Application Programming Interface',
            r'\bAPI\b': 'Application Programming Interface',
            r'\bUI\b': 'User Interface',
            r'\bUX\b': 'User Experience',
            r'\bDB\b': 'Database',
            r'\bSQL\b': 'Structured Query Language',
            r'\bHTML\b': 'Hypertext Markup Language',
            r'\bCSS\b': 'Cascading Style Sheets',
            r'\bJS\b': 'JavaScript',
            r'\bJSON\b': 'JSON',  # Keep as JSON as it's pronounced correctly
            r'\bRAM\b': 'Random Access Memory',
            r'\bCPU\b': 'Central Processing Unit',
            r'\bGPU\b': 'Graphics Processing Unit',
            
            # Common abbreviations
            r'\betc\.?\b': 'et cetera',
            r'\be\.g\.?\b': 'for example',
            r'\bi\.e\.?\b': 'that is',
            r'\bvs\.?\b': 'versus',
            r'\bDr\.\b': 'Doctor',
            r'\bMr\.\b': 'Mister',
            r'\bMrs\.\b': 'Missus',
            r'\bMs\.\b': 'Miss',
            
            # Symbols
            r'@': ' at ',
            r'&': ' and ',
            r'%': ' percent ',
            r'\$': ' dollars ',
            r'#': ' number ',
        }
        
        # Apply all replacements
        for pattern, replacement in replacements.items():
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        
        # Add natural pauses
        content = content.replace(". ", ". ... ")
        content = content.replace("? ", "? ... ")
        content = content.replace("! ", "! ... ")
        
        # Add longer pauses for paragraph breaks
        content = content.replace("\n\n", " ... ... ")
        
        # Ensure proper sentence endings
        if not content.endswith(('.', '!', '?')):
            content += "."
        
        # Add a natural ending
        content += " ... Thank you for your attention. Feel free to ask any questions about this topic."
        
        return content
    
    def _create_fallback_content(
        self, 
        module_title: str, 
        sub_topic_title: str, 
        raw_content: str
    ) -> str:
        """Create basic teaching content if LLM fails."""
        # Extract first meaningful paragraph or sentences
        import re
        
        # Clean the raw content
        cleaned_content = re.sub(r'#+ ', '', raw_content)  # Remove markdown headers
        cleaned_content = re.sub(r'\n+', ' ', cleaned_content)  # Replace newlines with spaces
        cleaned_content = re.sub(r'\s+', ' ', cleaned_content)  # Normalize spaces
        
        # Take first 800 characters for a reasonable explanation
        if len(cleaned_content) > 800:
            # Try to end at a sentence boundary
            truncated = cleaned_content[:800]
            last_period = truncated.rfind('.')
            if last_period > 600:  # Only if we don't lose too much
                cleaned_content = truncated[:last_period + 1]
            else:
                cleaned_content = truncated + "."
        
        return f"""Welcome to today's lesson on {sub_topic_title} from the module {module_title}. 

Let me explain this important topic to you.

{cleaned_content}

This covers the key concepts you need to understand about {sub_topic_title}. I hope this explanation helps you grasp the important points. 

Please feel free to ask if you have any questions about this topic. Thank you for your attention."""

    async def generate_lesson_outline(
        self, 
        module_title: str, 
        sub_topics: list,
        language: str = "en-IN"
    ) -> str:
        """Generate a lesson outline for an entire module."""
        try:
            outline_prompt = f"""Create a comprehensive lesson outline for the module: {module_title}

Sub-topics to cover:
{chr(10).join([f"- {topic.get('title', 'Unknown topic')}" for topic in sub_topics])}

Create an engaging introduction that:
1. Welcomes students to the module
2. Explains what they will learn
3. Shows the relevance and importance
4. Outlines the learning journey

Language: {self._get_language_instruction(language)}

Provide only the introduction content, ready for speech synthesis."""

            outline = await self.llm_service.generate_response(outline_prompt)
            return self._format_for_tts(outline)
            
        except Exception as e:
            logging.error(f"Error generating lesson outline: {e}")
            return f"Welcome to {module_title}. In this module, we will explore several important topics that will enhance your understanding of the subject."