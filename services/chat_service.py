"""
Chat Service - Handles RAG-based conversations and multilingual support
Now with Semantic Router for intelligent query routing (10x faster, 100x cheaper)
"""

import time
import logging
from typing import Dict, Any
import config
from services.document_service import DocumentProcessor
from services.rag_service import RAGService
from services.llm_service import LLMService
from services.sarvam_service import SarvamService
from services.semantic_router_service import SemanticRouterService

class ChatService:
    """Main chat service that coordinates RAG, translation, and LLM services."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.sarvam_service = SarvamService()
        self.document_processor = DocumentProcessor()
        self.vector_store = self._initialize_vector_store()
        
        # Initialize Semantic Router for intent classification
        self.semantic_router = SemanticRouterService()
        
        # Conversation memory storage (session_id -> list of messages)
        # LangChain 1.0: ConversationBufferWindowMemory deprecated, using simple dict
        self.session_memories = {}
        self.max_history_length = 10  # Keep last 10 exchanges
        
        if self.vector_store:
            self.rag_service = RAGService(self.vector_store)
            self.is_rag_active = True
            logging.info("✅ Vectorstore loaded and RAG chain initialized")
        else:
            self.rag_service = None
            self.is_rag_active = False
            logging.warning("❗ No vectorstore found. Operating in general knowledge mode")

    def _initialize_vector_store(self):
        """Initializes the vector store from ChromaDB Cloud or local FAISS."""
        try:
            if config.USE_CHROMA_CLOUD:
                from core.cloud_vectorizer import CloudVectorizer
                logging.info("Attempting to load vector store from ChromaDB Cloud...")
                cloud_vectorizer = CloudVectorizer()
                vector_store = cloud_vectorizer.get_vector_store()
                
                # CRITICAL: Verify the collection has documents
                if vector_store:
                    try:
                        # Get collection metadata
                        collection = vector_store._collection
                        doc_count = collection.count()
                        logging.info(f"📊 ChromaDB Collection Status:")
                        logging.info(f"   - Collection Name: {config.CHROMA_COLLECTION_NAME}")
                        logging.info(f"   - Document Count: {doc_count}")
                        
                        if doc_count == 0:
                            logging.error("❌ ChromaDB collection is EMPTY! No documents found.")
                            logging.error("   This will cause RAG to fail. Please upload course content first.")
                            return None
                        else:
                            logging.info(f"✅ ChromaDB collection is healthy with {doc_count} documents")
                    except Exception as e:
                        logging.warning(f"⚠️ Could not verify collection health: {e}")
                
                return vector_store
            else:
                logging.info("Attempting to load vector store from local FAISS...")
                return self.document_processor.get_vectorstore()
        except Exception as e:
            logging.error(f"Failed to initialize vector store: {e}")
            return None

    def _is_garbage_response(self, text: str) -> bool:
        """
        Detect if the response is garbage/hallucination.
        Returns True if the response appears to be nonsense.
        """
        import re
        
        if not text or len(text.strip()) < 10:
            return True
        
        # Check for excessive character repetition (like "क े ब ो क े ब ो")
        # Split into words and check if same pattern repeats many times
        words = text.split()
        if len(words) > 10:
            # Check if the same 2-3 word pattern repeats excessively
            pattern_length = 3
            patterns = {}
            for i in range(len(words) - pattern_length):
                pattern = ' '.join(words[i:i+pattern_length])
                patterns[pattern] = patterns.get(pattern, 0) + 1
            
            # If any pattern repeats more than 20 times, it's likely garbage
            max_repetitions = max(patterns.values()) if patterns else 0
            if max_repetitions > 20:
                logging.warning(f"⚠️ Detected excessive pattern repetition: {max_repetitions} times")
                return True
        
        # Check for excessive single character with spaces (like "क े ब ो")
        single_char_pattern = re.findall(r'(\S)\s+', text)
        if len(single_char_pattern) > 100:
            unique_chars = len(set(single_char_pattern))
            if unique_chars < 10:  # Few unique characters repeated many times
                logging.warning(f"⚠️ Detected excessive single character repetition")
                return True
        
        # Check if response is too long (>5000 chars) with low information density
        if len(text) > 5000:
            unique_words = len(set(words))
            total_words = len(words)
            if total_words > 0 and (unique_words / total_words) < 0.1:  # Less than 10% unique words
                logging.warning(f"⚠️ Detected low information density in long response")
                return True
        
        return False
    
    def _fix_tts_pronunciation(self, text: str) -> str:
        """Fix common abbreviations for better TTS pronunciation."""
        import re
        
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
            r'\bRAM\b': 'Random Access Memory',
            r'\bCPU\b': 'Central Processing Unit',
            r'\bGPU\b': 'Graphics Processing Unit',
            
            # Common abbreviations
            r'\betc\.?\b': 'et cetera',
            r'\be\.g\.?\b': 'for example',
            r'\bi\.e\.?\b': 'that is',
            r'\bvs\.?\b': 'versus',
            
            # Symbols
            r'@': ' at ',
            r'&': ' and ',
            r'%': ' percent ',
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

    async def ask_question(self, query: str, query_language_code: str = "en-IN", session_id: str = None, conversation_history: list = None, course_id: int = None) -> Dict[str, Any]:
        """Answer a question using RAG with multilingual support, conversation history, and intelligent routing."""
        
        # Cache formatted conversation context to avoid re-logging in fallbacks
        self._cached_context = None
        
        response_lang_name = next(
            (lang["name"] for lang in config.SUPPORTED_LANGUAGES if lang["code"] == query_language_code), 
            "English"
        )
        
        # STEP 1: Route the query using Semantic Router (ultra-fast intent classification)
        logging.info("[STEP 1] Classifying query intent with Semantic Router...")
        start_time = time.time()
        routing_result = self.semantic_router.classify_intent(query)
        route_name = routing_result["route_name"]
        should_use_rag = routing_result["should_use_rag"]
        confidence = routing_result["confidence"]
        end_time = time.time()
        
        logging.info(f"  > Intent: {route_name} (confidence: {confidence:.2f}) in {end_time - start_time:.3f}s")
        logging.info(f"  > RAG Required: {should_use_rag}")
        
        # STEP 2: Handle based on route
        
        # Route 1: Greetings - Ultra-fast response (no LLM/RAG needed)
        if route_name == "greeting":
            logging.info("[ROUTE] Greeting detected - using pre-defined response")
            greeting_response = self.semantic_router.get_greeting_response(query, response_lang_name)
            self._save_to_memory(session_id, query, greeting_response)
            return {
                "answer": greeting_response,
                "sources": [{"type": "greeting", "content": "Greeting Handler"}],
                "route": "greeting",
                "confidence": confidence
            }
        
        # Route 2: General questions - Use general LLM (skip RAG)
        if route_name == "general_question":
            logging.info("[ROUTE] General question detected - using general LLM (no RAG)")
            start_time = time.time()
            history = self._get_conversation_context(session_id, conversation_history)
            answer = await self.llm_service.get_general_response(query, response_lang_name, history)
            answer = self._fix_tts_pronunciation(answer)
            end_time = time.time()
            logging.info(f"  > General LLM response in {end_time - start_time:.2f}s")
            self._save_to_memory(session_id, query, answer)
            return {
                "answer": answer,
                "sources": [{"type": "general_llm", "content": "General Knowledge"}],
                "route": "general_question",
                "confidence": confidence
            }
        
        # Route 3: Course-related query - Use RAG
        logging.info("[ROUTE] Course query detected - using RAG pipeline")

        if self.is_rag_active and should_use_rag:
            # Translate query to English if needed
            start_time = time.time()
            english_query = query
            if query_language_code != "en-IN":
                logging.info("[TASK] Translating query to English using Sarvam AI...")
                english_query = await self.sarvam_service.translate_text(
                    text=query,
                    source_language_code=query_language_code,
                    target_language_code="en-IN"
                )
                end_time = time.time()
                logging.info(f"[Current Query] {english_query}")
                logging.info(f"  > Translation complete in {end_time - start_time:.2f}s. (Query: '{english_query}')")
            
            # CRITICAL: Validate course_id relevance before applying filter
            # If course_id provided but query is NOT course-specific (e.g., "what's the weather"),
            # bypass RAG entirely and route to general LLM for faster response
            if course_id is not None:
                is_course_specific = self.semantic_router.is_query_course_specific(english_query)
                if not is_course_specific:
                    logging.warning(f"🚫 course_id={course_id} provided but query is NOT course-specific.")
                    logging.info("⚡ Bypassing RAG, routing directly to general LLM for faster response...")
                    start_time = time.time()
                    history = self._get_conversation_context(session_id, conversation_history)
                    answer = await self.llm_service.get_general_response(english_query, response_lang_name, history)
                    answer = self._fix_tts_pronunciation(answer)
                    end_time = time.time()
                    logging.info(f"  > General LLM response (bypassed RAG) in {end_time - start_time:.2f}s")
                    self._save_to_memory(session_id, query, answer)
                    return {
                        "answer": answer,
                        "sources": [{"type": "general_llm", "content": "General Knowledge"}],
                        "route": "general_bypassed_rag",
                        "confidence": confidence
                    }
                else:
                    logging.info(f"✅ course_id={course_id} validated - query IS course-specific. Applying filter.")
            
            try:
                # Execute RAG chain with conversation context
                logging.info("[TASK] Executing RAG chain...")
                start_time = time.time()
                
                # Get conversation history for context from database
                history = self._get_conversation_context(session_id, conversation_history)
                
                # Get RAG response with course_id filter (if provided and validated)
                rag_result = await self.rag_service.get_answer(english_query, response_lang_name, history, course_id)
                answer = rag_result["answer"]
                source_docs = rag_result["source_documents"]
                
                end_time = time.time()
                logging.info(f"  > RAG chain complete in {end_time - start_time:.2f}s.")
                logging.info(f"  > Retrieved {len(source_docs)} source documents")
                
                # Save the current exchange to session memory
                self._save_to_memory(session_id, query, answer)
                
                # CRITICAL: Detect garbage/hallucinated responses
                if self._is_garbage_response(answer):
                    logging.error("❌ GARBAGE RESPONSE DETECTED from RAG! Response contains repeated characters or nonsense.")
                    logging.error(f"   Bad response preview: {answer[:200]}...")
                    logging.info("  > Falling back to general LLM due to garbage response...")
                    start_time = time.time()
                    history = self._get_conversation_context(session_id, conversation_history)
                    answer = await self.llm_service.get_general_response(query, response_lang_name, history)
                    answer = self._fix_tts_pronunciation(answer)
                    end_time = time.time()
                    logging.info(f"  > Fallback complete in {end_time - start_time:.2f}s.")
                    self._save_to_memory(session_id, query, answer)
                    return {
                        "answer": answer,
                        "sources": [{"type": "fallback", "content": "General Knowledge Fallback"}],
                        "route": "course_query",
                        "confidence": confidence
                    }
                
                # Fix TTS pronunciation issues
                answer = self._fix_tts_pronunciation(answer)
                
                # Check if RAG found an answer
                if "I cannot find the answer" in answer:
                    logging.info("  > RAG chain failed. Falling back to general LLM...")
                    start_time = time.time()
                    history = self._get_conversation_context(session_id, conversation_history)
                    answer = await self.llm_service.get_general_response(query, response_lang_name, history)
                    answer = self._fix_tts_pronunciation(answer)
                    end_time = time.time()
                    logging.info(f"  > Fallback complete in {end_time - start_time:.2f}s.")
                    self._save_to_memory(session_id, query, answer)
                    return {
                        "answer": answer,
                        "sources": [{"type": "fallback", "content": "General Knowledge Fallback"}],
                        "route": "course_query",
                        "confidence": confidence
                    }

                # Format sources from retrieved documents
                sources = []
                seen_sources = set()
                for doc in source_docs:
                    source_name = doc.metadata.get('source', 'Course Content')
                    if source_name not in seen_sources:
                        sources.append({
                            "type": "rag",
                            "content": source_name,
                            "chunk_id": doc.metadata.get('chunk_id', 'unknown')
                        })
                        seen_sources.add(source_name)
                
                if not sources:
                    sources = [{"type": "rag", "content": "Course Content", "chunk_id": "unknown"}]

                return {
                    "answer": answer,
                    "sources": sources,
                    "route": "course_query",
                    "confidence": confidence
                }

            except Exception as e:
                logging.error(f"  > Error during RAG chain invocation: {e}. Falling back...")
        
        # Fallback to general knowledge
        logging.info("[TASK] Using general knowledge fallback...")
        start_time = time.time()
        history = self._get_conversation_context(session_id, conversation_history)
        answer = await self.llm_service.get_general_response(query, response_lang_name, history)
        answer = self._fix_tts_pronunciation(answer)
        end_time = time.time()
        logging.info(f"  > General knowledge fallback complete in {end_time - start_time:.2f}s.")
        self._save_to_memory(session_id, query, answer)
        return {
            "answer": answer,
            "sources": [{"type": "fallback", "content": "General Knowledge"}],
            "route": route_name if 'route_name' in locals() else "fallback",
            "confidence": confidence if 'confidence' in locals() else 0.5
        }
    
    def _get_or_create_memory(self, session_id: str) -> list:
        """Get or create message list for the session."""
        if session_id and session_id not in self.session_memories:
            self.session_memories[session_id] = []
        
        return self.session_memories.get(session_id, [])
    
    def _get_conversation_context(self, session_id: str, db_conversation_history: list = None) -> str:
        """Get formatted conversation context from database history.
        
        Args:
            session_id: Session ID for logging
            db_conversation_history: List of messages from database [{'role': 'user', 'content': '...'}, ...]
        """
        # Return cached context if available (avoids re-logging in fallbacks)
        if hasattr(self, '_cached_context') and self._cached_context is not None:
            logging.info(f"📋 [CHAT SERVICE] Using cached conversation context")
            return self._cached_context
        
        logging.info(f"🔍 [CHAT SERVICE] Getting conversation context for session: {session_id}")
        
        # Use database history if provided, otherwise fall back to in-memory
        messages = db_conversation_history if db_conversation_history else self._get_or_create_memory(session_id)
        
        if not messages:
            logging.info("📭 [CHAT SERVICE] No conversation history available")
            return ""
        
        logging.info(f"📚 [CHAT SERVICE] Found {len(messages)} messages in conversation history")
        
        # Use ALL messages from DB (already limited to 5 interactions = 10 messages in app_celery)
        context = "\n\nPrevious conversation:\n"
        
        for idx, msg in enumerate(messages):
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            role_label = "User" if role == "user" else "Assistant"
            context += f"{role_label}: {content}\n"
            
            # Log each message being included
            content_preview = content[:80] + "..." if len(content) > 80 else content
            logging.info(f"  [{idx+1}] {role_label}: {content_preview}")
        
        logging.info(f"✅ [CHAT SERVICE] Formatted conversation context with {len(messages)} messages")
        
        # Cache for subsequent fallback calls
        self._cached_context = context
        return context
    
    def _save_to_memory(self, session_id: str, query: str, answer: str):
        """Save the current exchange to session memory."""
        messages = self._get_or_create_memory(session_id)
        messages.append({"role": "user", "content": query})
        messages.append({"role": "assistant", "content": answer})
        
        # Trim to max history length (keep last N exchanges)
        max_messages = self.max_history_length * 2  # 2 messages per exchange
        if len(messages) > max_messages:
            self.session_memories[session_id] = messages[-max_messages:]
    
    def update_with_course_content(self, course_data: dict):
        """Update the RAG system with new course content."""
        try:
            # Extract course documents
            course_documents = self.document_processor.extract_course_documents(course_data)
            
            if course_documents:
                # Split documents
                split_course_docs = self.document_processor.split_documents(course_documents)
                
                # Add to vectorstore
                if self.vector_store:
                    self.vector_store.add_documents(split_course_docs)
                else:
                    # This case is unlikely if initialization is correct, but handled for safety
                    self.vector_store = self._initialize_vector_store()
                    if self.vector_store:
                        self.vector_store.add_documents(split_course_docs)
                        self.rag_service = RAGService(self.vector_store)
                        self.is_rag_active = True
                
                logging.info(f"✅ Added {len(split_course_docs)} course content chunks to RAG system")
                
        except Exception as e:
            logging.error(f"⚠️ Error updating RAG with course content: {e}")
            raise e
