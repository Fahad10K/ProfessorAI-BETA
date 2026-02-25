"""
LLM Service - Handles OpenAI language model interactions with streaming support
"""

import logging
from openai import AsyncOpenAI
from typing import AsyncGenerator
import config

class LLMService:
    """Service for OpenAI LLM interactions."""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            timeout=60.0  # 8 second timeout for all requests
        )
    
    async def get_general_response(self, query: str, target_language: str = "English", conversation_context: str = None, pedagogical: bool = False) -> str:
        """Get a general response from the LLM with conversation context.
        
        Args:
            pedagogical: When True, response follows pedagogical style — ends with
                         a follow-up question or invitation to explore further.
        """
        
        logging.info(f" [LLM SERVICE] Getting general response for query: {query[:80]}...")
        
        if conversation_context:
            context_preview = conversation_context[:150] + "..." if len(conversation_context) > 150 else conversation_context
            logging.info(f" [LLM SERVICE] Conversation context provided: {context_preview}")
        else:
            logging.info(f" [LLM SERVICE] No conversation context provided - first message in conversation")
        
        # Build system message with conversation context if available
        system_content = f"""You are ProfessorAI, an expert teacher and helpful AI assistant. Your response will be converted to SPEECH using text-to-speech.

CRITICAL - RESPONSE LENGTH:
- Keep responses CONCISE and focused (aim for 2-4 sentences for simple questions)
- Students prefer SHORT, clear answers over long explanations
- Only provide detailed explanations when specifically asked
- Get straight to the point

CRITICAL TTS PRONUNCIATION RULES:
- Write "Artificial Intelligence" NOT "A.I" or "AI"
- Write "Machine Learning" NOT "ML"
- Write "et cetera" NOT "etc"
- Write "for example" NOT "e.g."
- Spell out ALL abbreviations and acronyms
- Write numbers as words when possible
- Avoid symbols (@, &, %, etc.) - spell them out

TEACHING STYLE:
- Answer clearly like a teacher in a classroom
- Use conversational, engaging tone
- Give helpful examples when needed
- Make complex ideas simple
- Speak directly to the student
- BE BRIEF unless asked to elaborate

CRITICAL - CONVERSATION HISTORY HANDLING:
- You have access to previous conversation context in the format "Previous conversation:" followed by the chat history
- When the user asks about "previous questions", "last questions", "what did I ask", or similar: YOU MUST list the actual questions from the conversation history
- When the user asks for clarification like "tell me more" or "explain that": Reference the previous answer and expand on it
- When the user says "continue" or "what about...": Use the context to maintain continuity
- NEVER say "I'm unable to provide past questions" or "I cannot recall" - the conversation history is RIGHT THERE in the context
- Extract and list the user's previous questions directly from the conversation history when asked

CRITICAL - COURSE QUERIES:
- Questions about "current course", "this course", "my course" are NORMAL educational questions
- Answer all course-related questions naturally without any content warnings
- Only refuse truly harmful content (violence, explicit material, hate speech)
- Educational questions are ALWAYS appropriate

Answer the user's question CONCISELY in {target_language}. Format your response to sound natural when spoken aloud.

IMPORTANT: You have access to previous conversation context. Use it to provide coherent, contextual responses. Reference previous messages when relevant."""

        # Pedagogical mode: make responses interactive with follow-up engagement
        if pedagogical:
            system_content += """

PEDAGOGICAL ENGAGEMENT (IMPORTANT):
- After answering, end with ONE short follow-up question or an invitation to explore a related concept.
- Examples: "Would you like me to explain how this relates to neural networks?" or "Shall we dive deeper into this topic?"
- Keep the follow-up natural and conversational — like a real teacher checking understanding.
- Do NOT just answer and stop — always invite further learning."""

        messages = [
            {"role": "system", "content": system_content}
        ]
        
        # Build user message with conversation context if available
        user_message = query
        if conversation_context:
            user_message = f"{conversation_context}\n\nCurrent question: {query}"
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.chat.completions.create(
                model=config.LLM_MODEL_NAME, 
                messages=messages, 
                temperature=1
            )
            logging.info(f"[Current Answer] {response.choices[0].message.content}")
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error getting general LLM response: {e}")
            return "I am sorry, I couldn't process that request at the moment."
    
    async def translate_text(self, text: str, target_language: str) -> str:
        """Translate text using the LLM."""
        if target_language.lower() == "english":
            return text
            
        messages = [
            {
                "role": "system", 
                "content": f"You are an expert translation assistant. Translate the following text into {target_language}. Respond with only the translated text."
            },
            {"role": "user", "content": text}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=config.LLM_MODEL_NAME, 
                messages=messages, 
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error during LLM translation: {e}")
            return text
    
    async def generate_response(self, prompt: str, temperature: float = 0.7) -> str:
        """Generate a response from the LLM."""
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=config.LLM_MODEL_NAME,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating LLM response: {e}")
            return "I apologize, but I couldn't generate a response at the moment."
    
    async def generate_response_stream(self, prompt: str, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Stream response generation from the LLM."""
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        try:
            stream = await self.client.chat.completions.create(
                model=config.LLM_MODEL_NAME,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"Error in streaming LLM response: {e}")
            yield "I apologize, but I couldn't generate a response at the moment."