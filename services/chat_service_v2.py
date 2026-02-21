"""
Chat Service V2 - LangChain 1.0 Implementation
Uses create_agent pattern with tools for RAG-based conversations
"""

import time
import logging
from typing import Dict, Any, List
import config
from services.document_service import DocumentProcessor
from services.llm_service import LLMService
from services.sarvam_service import SarvamService
from services.semantic_router_service import SemanticRouterService
from services.retrieval_tool import RetrievalToolFactory
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ChatServiceV2:
    """
    LangChain 1.0 Chat Service using Agent pattern.
    
    Architecture:
    - Semantic Router for intent classification
    - Agent with retrieval tool for RAG
    - Message-based conversation state
    - Tool-based architecture (modern LangChain pattern)
    """
    
    def __init__(self):
        logger.info("🚀 Initializing ChatServiceV2 (LangChain 1.0)")
        
        # Initialize services
        self.llm_service = LLMService()
        self.sarvam_service = SarvamService()
        self.document_processor = DocumentProcessor()
        self.vector_store = self._initialize_vector_store()
        
        # Initialize Semantic Router
        self.semantic_router = SemanticRouterService()
        
        # Session state: session_id -> list of message dicts
        self.sessions = {}
        self.max_messages = 20  # Keep last 20 messages (10 exchanges)
        
        # Initialize agent if vector store is available
        if self.vector_store:
            self._initialize_agent()
            self.is_rag_active = True
            logger.info("✅ RAG Agent initialized successfully")
        else:
            self.agent = None
            self.is_rag_active = False
            logger.warning("❗ No vectorstore - RAG unavailable, general LLM only")
    
    def _initialize_vector_store(self):
        """Initialize vector store from ChromaDB Cloud or local FAISS."""
        try:
            if config.USE_CHROMA_CLOUD:
                from core.cloud_vectorizer import CloudVectorizer
                logger.info("Loading vector store from ChromaDB Cloud...")
                cloud_vectorizer = CloudVectorizer()
                vector_store = cloud_vectorizer.get_vector_store()
                
                if vector_store:
                    try:
                        collection = vector_store._collection
                        doc_count = collection.count()
                        logger.info(f"📊 ChromaDB: {doc_count} documents in collection '{config.CHROMA_COLLECTION_NAME}'")
                        
                        if doc_count == 0:
                            logger.error("❌ ChromaDB collection is EMPTY!")
                            return None
                        else:
                            logger.info(f"✅ ChromaDB ready with {doc_count} documents")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not verify collection: {e}")
                
                return vector_store
            else:
                logger.info("Loading vector store from local FAISS...")
                return self.document_processor.get_vectorstore()
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            return None
    
    def _initialize_agent(self):
        """Initialize LangChain agent with retrieval tool."""
        try:
            # Create LLM
            model = ChatOpenAI(
                model=config.LLM_MODEL_NAME,
                temperature=0,
                openai_api_key=config.OPENAI_API_KEY
            )
            
            # Create retrieval tool
            retrieval_factory = RetrievalToolFactory(self.vector_store)
            
            # Check if hybrid retriever is available
            try:
                from services.hybrid_retriever import HybridRetriever
                from services.rag_service import RAGService
                
                # Get all documents for BM25
                rag_temp = RAGService(self.vector_store)
                if hasattr(rag_temp, 'all_documents') and rag_temp.all_documents:
                    hybrid_retriever = HybridRetriever(
                        vector_retriever=self.vector_store.as_retriever(search_kwargs={"k": 10}),
                        all_documents=rag_temp.all_documents
                    )
                    retrieval_tool = retrieval_factory.create_hybrid_retrieval_tool(hybrid_retriever, k=5)
                    logger.info("✅ Using hybrid retrieval (Vector + BM25 + Reranking)")
                else:
                    retrieval_tool = retrieval_factory.create_retrieval_tool(k=5)
                    logger.info("✅ Using standard vector retrieval")
            except Exception as e:
                logger.warning(f"⚠️ Hybrid retrieval unavailable: {e}, using standard retrieval")
                retrieval_tool = retrieval_factory.create_retrieval_tool(k=5)
            
            # Build system prompt
            system_prompt = self._build_system_prompt()
            
            # Create agent
            self.agent = create_agent(
                model=model,
                tools=[retrieval_tool],
                system_prompt=system_prompt
            )
            
            logger.info("✅ Agent created with retrieval tool")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize agent: {e}")
            self.agent = None
            raise
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt for the agent."""
        return f"""You are Professor AI, an intelligent educational assistant helping students learn course material.

**Your Capabilities:**
- You have access to a tool that retrieves relevant content from course materials
- Use the retrieval tool when students ask questions about course content
- Provide clear, accurate, and educational responses
- If you cannot find relevant information in the course materials, say so honestly

**Teaching Guidelines:**
- Break down complex concepts into simple explanations
- Use examples and analogies when helpful
- Encourage critical thinking
- Be patient and supportive
- Adapt your explanation style based on the student's level

**Content Safety:**
- Do not provide answers to homework or exam questions directly
- Guide students to learn rather than giving away answers
- Refuse inappropriate requests politely

**Response Format:**
- Keep answers concise but complete
- Use clear structure with paragraphs or bullet points
- Cite sources when using retrieved content
- Always be encouraging and positive

Remember: Your goal is to help students LEARN, not just get answers.
"""
    
    async def ask_question(
        self,
        query: str,
        query_language_code: str = "en-IN",
        session_id: str = None,
        conversation_history: list = None
    ) -> Dict[str, Any]:
        """
        Answer a question using LangChain 1.0 agent with conversation history.
        
        Args:
            query: User's question
            query_language_code: Language code for the query
            session_id: Session ID for conversation continuity
            conversation_history: Optional conversation history (legacy support)
            
        Returns:
            Dict with answer, sources, route, and confidence
        """
        
        response_lang_name = next(
            (lang["name"] for lang in config.SUPPORTED_LANGUAGES if lang["code"] == query_language_code),
            "English"
        )
        
        # STEP 1: Semantic Router - Ultra-fast intent classification
        logger.info("[STEP 1] 🎯 Classifying query intent...")
        start_time = time.time()
        routing_result = self.semantic_router.classify_intent(query)
        route_name = routing_result["route_name"]
        should_use_rag = routing_result["should_use_rag"]
        confidence = routing_result["confidence"]
        routing_time = time.time() - start_time
        
        logger.info(f"  ✓ Intent: {route_name} (confidence: {confidence:.2f}) in {routing_time:.3f}s")
        
        # STEP 2: Handle Greetings - No LLM/RAG needed
        if route_name == "greeting":
            logger.info("[ROUTE] 👋 Greeting - pre-defined response")
            greeting = self.semantic_router.get_greeting_response(query, response_lang_name)
            self._add_message(session_id, "user", query)
            self._add_message(session_id, "assistant", greeting)
            return {
                "answer": greeting,
                "sources": [{"type": "greeting", "content": "Greeting Handler"}],
                "route": "greeting",
                "confidence": confidence,
                "session_id": session_id
            }
        
        # STEP 3: Translate if needed
        english_query = query
        if query_language_code != "en-IN":
            logger.info("[STEP 2] 🌐 Translating to English...")
            start_time = time.time()
            english_query = await self.sarvam_service.translate_text(
                text=query,
                source_language_code=query_language_code,
                target_language_code="en-IN"
            )
            logger.info(f"  ✓ Translation complete in {time.time() - start_time:.2f}s")
        
        # STEP 4: Route based on intent
        
        # Route A: Course Query with RAG Agent
        if route_name == "course_query" and self.is_rag_active and should_use_rag:
            logger.info("[ROUTE] 📚 Course query - using RAG agent")
            return await self._handle_course_query_with_agent(
                english_query,
                session_id,
                response_lang_name,
                confidence
            )
        
        # Route B: General Question with LLM (no RAG)
        logger.info(f"[ROUTE] 💬 {route_name} - using general LLM")
        return await self._handle_general_query(
            query,
            session_id,
            response_lang_name,
            route_name,
            confidence
        )
    
    async def _handle_course_query_with_agent(
        self,
        query: str,
        session_id: str,
        language: str,
        confidence: float
    ) -> Dict[str, Any]:
        """Handle course query using LangChain agent with retrieval tool."""
        try:
            logger.info("[TASK] 🤖 Invoking RAG agent...")
            start_time = time.time()
            
            # Get conversation history
            messages = self._get_messages(session_id)
            
            # Add current user message
            messages.append({"role": "user", "content": query})
            
            # Invoke agent with full message history
            response = await self.agent.ainvoke(
                {"messages": messages},
                {"configurable": {"thread_id": session_id}}
            )
            
            # Extract answer from agent response
            agent_messages = response.get("messages", [])
            if agent_messages:
                answer = agent_messages[-1].content
            else:
                raise Exception("No response from agent")
            
            elapsed = time.time() - start_time
            logger.info(f"  ✓ Agent response in {elapsed:.2f}s")
            
            # Check for garbage response
            if self._is_garbage_response(answer):
                logger.error("❌ Garbage response detected! Falling back to general LLM")
                return await self._handle_general_query(
                    query, session_id, language, "course_query", confidence
                )
            
            # Fix TTS pronunciation
            answer = self._fix_tts_pronunciation(answer)
            
            # Save to conversation history
            self._add_message(session_id, "user", query)
            self._add_message(session_id, "assistant", answer)
            
            return {
                "answer": answer,
                "sources": [{"type": "course_content", "content": "Course Content (Agent)"}],
                "route": "course_query",
                "confidence": confidence,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"❌ Agent error: {e}")
            logger.info("  ↳ Falling back to general LLM")
            return await self._handle_general_query(
                query, session_id, language, "course_query", confidence
            )
    
    async def _handle_general_query(
        self,
        query: str,
        session_id: str,
        language: str,
        route_name: str,
        confidence: float
    ) -> Dict[str, Any]:
        """Handle general query using LLM service."""
        logger.info("[TASK] 💬 Using general LLM...")
        start_time = time.time()
        
        # Get conversation context
        history = self._get_conversation_context(session_id)
        
        # Generate response
        answer = await self.llm_service.get_general_response(query, language, history)
        answer = self._fix_tts_pronunciation(answer)
        
        elapsed = time.time() - start_time
        logger.info(f"  ✓ General LLM response in {elapsed:.2f}s")
        
        # Save to conversation history
        self._add_message(session_id, "user", query)
        self._add_message(session_id, "assistant", answer)
        
        return {
            "answer": answer,
            "sources": [{"type": "general_knowledge", "content": "General Knowledge"}],
            "route": route_name,
            "confidence": confidence,
            "session_id": session_id
        }
    
    def _get_messages(self, session_id: str) -> List[Dict[str, str]]:
        """Get message history for session."""
        if not session_id or session_id not in self.sessions:
            return []
        return self.sessions[session_id].copy()
    
    def _add_message(self, session_id: str, role: str, content: str):
        """Add message to session history with automatic trimming."""
        if not session_id:
            return
        
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        
        self.sessions[session_id].append({"role": role, "content": content})
        
        # Trim to max_messages
        if len(self.sessions[session_id]) > self.max_messages:
            self.sessions[session_id] = self.sessions[session_id][-self.max_messages:]
    
    def _get_conversation_context(self, session_id: str) -> str:
        """Get formatted conversation context for LLM service."""
        messages = self._get_messages(session_id)
        if not messages:
            return ""
        
        context = "\n\nPrevious conversation:\n"
        for msg in messages[-6:]:  # Last 3 exchanges
            role_label = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role_label}: {msg['content']}\n"
        
        return context
    
    def _is_garbage_response(self, text: str) -> bool:
        """Detect garbage/hallucinated responses."""
        import re
        
        if not text or len(text.strip()) < 10:
            return True
        
        words = text.split()
        if len(words) > 10:
            pattern_length = 3
            patterns = {}
            for i in range(len(words) - pattern_length):
                pattern = ' '.join(words[i:i+pattern_length])
                patterns[pattern] = patterns.get(pattern, 0) + 1
            
            max_repetitions = max(patterns.values()) if patterns else 0
            if max_repetitions > 20:
                logger.warning(f"⚠️ Excessive pattern repetition: {max_repetitions} times")
                return True
        
        single_char_pattern = re.findall(r'(\S)\s+', text)
        if len(single_char_pattern) > 100:
            unique_chars = len(set(single_char_pattern))
            if unique_chars < 10:
                logger.warning("⚠️ Excessive single character repetition")
                return True
        
        if len(text) > 5000:
            unique_words = len(set(words))
            total_words = len(words)
            if total_words > 0 and (unique_words / total_words) < 0.1:
                logger.warning("⚠️ Low information density")
                return True
        
        return False
    
    def _fix_tts_pronunciation(self, text: str) -> str:
        """Fix abbreviations for better TTS pronunciation."""
        import re
        
        replacements = {
            r'\bA\.I\.?\b': 'Artificial Intelligence',
            r'\bAI\b': 'Artificial Intelligence',
            r'\bM\.L\.?\b': 'Machine Learning',
            r'\bML\b': 'Machine Learning',
            r'\bN\.L\.P\.?\b': 'Natural Language Processing',
            r'\bNLP\b': 'Natural Language Processing',
            r'\bA\.P\.I\.?\b': 'Application Programming Interface',
            r'\bAPI\b': 'Application Programming Interface',
            r'\betc\.?\b': 'et cetera',
            r'\be\.g\.?\b': 'for example',
            r'\bi\.e\.?\b': 'that is',
            r'@': ' at ',
            r'&': ' and ',
            r'%': ' percent ',
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def update_with_course_content(self, course_data: dict):
        """Update RAG system with new course content."""
        try:
            course_documents = self.document_processor.extract_course_documents(course_data)
            
            if course_documents:
                split_docs = self.document_processor.split_documents(course_documents)
                
                if self.vector_store:
                    self.vector_store.add_documents(split_docs)
                else:
                    self.vector_store = self._initialize_vector_store()
                    if self.vector_store:
                        self.vector_store.add_documents(split_docs)
                        self._initialize_agent()
                        self.is_rag_active = True
                
                logger.info(f"✅ Added {len(split_docs)} chunks to RAG system")
                
        except Exception as e:
            logger.error(f"⚠️ Error updating RAG: {e}")
            raise e
