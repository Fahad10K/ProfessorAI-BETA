"""
RAG Service - Handles Retrieval-Augmented Generation
"""

import logging
import json
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from typing import List, Any, Dict, Optional
import config
from services.hybrid_retriever import HybridRetriever

class RAGService:
    """Service for RAG-based question answering."""
    
    def __init__(self, vectorstore: Chroma = None, all_documents: List[Any] = None):
        from langchain_openai import OpenAIEmbeddings
        
        # Load course details from JSON
        self.courses_data = self._load_courses_json()

        if vectorstore is None:
            if config.USE_CHROMA_CLOUD:
                from core.cloud_vectorizer import CloudVectorizer
                cloud_vectorizer = CloudVectorizer()
                self.vectorstore = cloud_vectorizer.get_vector_store()
            else:
                from core.vectorizer import Vectorizer
                embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME, openai_api_key=config.OPENAI_API_KEY, chunk_size=200)
                self.vectorstore = Vectorizer.load_vector_store(config.FAISS_DB_PATH, embeddings)
                if not self.vectorstore:
                    # If loading fails, create an empty FAISS store to avoid crashing
                    from langchain_community.vectorstores import FAISS
                    import numpy as np
                    # Create a dummy document and embedding to initialize an empty store
                    dummy_doc = ["Initial empty document"]
                    dummy_embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL_NAME, openai_api_key=config.OPENAI_API_KEY, chunk_size=200)
                    self.vectorstore = FAISS.from_texts(dummy_doc, dummy_embeddings)
        else:
            self.vectorstore = vectorstore
        
        # Store all documents for BM25 indexing
        self.all_documents = all_documents or []

        # Use Groq for RAG - 100 tokens/sec (5-10x faster than OpenAI)
        self.llm = ChatGroq(
            model=config.RAG_MODEL_NAME,
            temperature=0.1,  # Lower temp for more consistent RAG answers
            groq_api_key=config.GROQ_API_KEY
        )
        logging.info(f"✅ Using Groq {config.RAG_MODEL_NAME} for fast RAG generation")
        self.prompt = ChatPromptTemplate.from_template(config.QA_PROMPT_TEMPLATE)
        
        # Create base vector retriever
        self.base_retriever = self.vectorstore.as_retriever(
            search_type=config.RETRIEVAL_SEARCH_TYPE,
            search_kwargs={"k": 10}  # Get more initially for hybrid search
        )
        
        # Create hybrid retriever with BM25 + reranking
        self.retriever = self._create_hybrid_retriever()
        
        self._initialize_chain()
    
    def _load_courses_json(self) -> List[Dict]:
        """Load course details from JSON file."""
        try:
            json_path = os.path.join(config.BASE_DIR, "courses_week_topics.json")
            if not os.path.exists(json_path):
                logging.warning(f"⚠️ courses_week_topics.json not found at {json_path}")
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                courses_data = json.load(f)
                logging.info(f"✅ Loaded {len(courses_data)} courses from JSON")
                return courses_data
        except FileNotFoundError:
            logging.warning(f"⚠️ Could not find courses JSON file")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"❌ Failed to parse courses JSON: {e}")
            return []
    
    def _format_course_details(self, course_id: int) -> str:
        """Format course details for the selected course.
        
        Args:
            course_id: The course ID to get details for
            
        Returns:
            Formatted string with course title and week-wise topics
        """
        if not self.courses_data:
            return "No course details available."
        
        # Find course by course_id
        course = next((c for c in self.courses_data if c.get('course_id') == course_id), None)
        
        if not course:
            return f"Course ID {course_id} not found."
        
        # Format course details
        course_title = course.get('course_title', 'Unknown Course')
        weeks = course.get('weeks', [])
        
        details = [f"**Course: {course_title}**\n"]
        details.append(f"This course has {len(weeks)} weeks covering the following topics:\n")
        
        for week in weeks:
            week_num = week.get('week_number', '?')
            week_title = week.get('week_title', 'Unknown')
            topics = week.get('topics', [])
            
            details.append(f"\nWeek {week_num}: {week_title}")
            if topics:
                topic_titles = [t.get('topic_title', '') for t in topics]
                details.append(f"  Topics: {', '.join(topic_titles)}")
        
        formatted = '\n'.join(details)
        logging.info(f"📋 Formatted course details for course_id {course_id}: {course_title}")
        return formatted
    
    def _initialize_chain(self):
        """Initialize the RAG chain."""
        def format_docs(docs: List[Any]) -> str:
            return "\n\n".join(doc.page_content for doc in docs)
        
        def retrieve_and_log_context(x):
            """Retrieve context and log it for debugging. Cache docs to avoid double retrieval."""
            question = x["question"]
            retrieved_docs = self.retriever.invoke(question)
            
            # Cache retrieved docs for get_answer to return (avoid double retrieval)
            self._last_retrieved_docs = retrieved_docs
            
            # Log retrieved documents for debugging
            logging.info(f"📚 Retrieved {len(retrieved_docs)} documents from vector store for query: '{question}'")
            
            if not retrieved_docs:
                logging.warning("⚠️ NO DOCUMENTS RETRIEVED from vector store!")
                return "No relevant context found in the knowledge base."
            
            # Log first 200 chars of each document
            for idx, doc in enumerate(retrieved_docs):
                preview = doc.page_content[:200].replace('\n', ' ')
                logging.info(f"   Doc {idx+1}: {preview}...")
            
            context = format_docs(retrieved_docs)
            logging.info(f"📝 Total context length: {len(context)} characters")
            
            return context

        self.rag_chain = (
            {
                "context": retrieve_and_log_context,
                "question": lambda x: x["question"],
                "conversation_history": lambda x: x.get("conversation_history", ""),
                "response_language": lambda x: x["response_language"],
                "selected_course_details": lambda x: x.get("selected_course_details", "No course selected")
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
    
    async def get_answer(self, question: str, response_language: str = "English", conversation_context: str = None, course_id: int = None):
        """Get an answer using the RAG chain with conversation context.
        
        Args:
            question: User's question
            response_language: Language for the response
            conversation_context: Previous conversation history
            course_id: Optional course ID for filtering results to specific course
        
        Returns:
            Dict with 'answer' (str) and 'source_documents' (List[Document]) from cached retrieval
        """
        try:
            # If course_id provided, recreate retriever with metadata filter
            if course_id is not None:
                logging.info(f"🎯 Filtering RAG to course_id: {course_id}")
                metadata_filter = {"course_id": course_id}
                self.retriever = self._create_hybrid_retriever(metadata_filter=metadata_filter)
                self._initialize_chain()
            
            # Build enhanced question with conversation context
            enhanced_question = question
            if conversation_context:
                enhanced_question = f"{conversation_context}\n\nCurrent question: {question}"
                context_preview = conversation_context[:150] + "..." if len(conversation_context) > 150 else conversation_context
                logging.info(f"💬 [RAG SERVICE] Using conversation context: {context_preview}")
            else:
                logging.info(f"📭 [RAG SERVICE] No conversation context - first query in session")
            
            # Get course details if course_id provided
            course_details = "No course selected"
            if course_id is not None:
                course_details = self._format_course_details(course_id)
            
            # Initialize cache
            self._last_retrieved_docs = []
            
            logging.info(f"🚀 [RAG SERVICE] Invoking RAG chain with conversation_history length: {len(conversation_context or '')}")
            
            answer = await self.rag_chain.ainvoke({
                "question": question,
                "conversation_history": conversation_context or "",
                "response_language": response_language,
                "selected_course_details": course_details
            })
            logging.info(f"[Current Answer] {answer}")
            
            # Return answer + cached docs (avoids double retrieval)
            return {
                "answer": answer,
                "source_documents": self._last_retrieved_docs
            }
        except Exception as e:
            print(f"Error in RAG chain: {e}")
            raise e
    
    def update_vectorstore(self, vectorstore: Chroma, all_documents: List[Any] = None):
        """Update the vectorstore and reinitialize the chain with hybrid retriever."""
        self.vectorstore = vectorstore
        self.all_documents = all_documents or []
        
        # Recreate base retriever
        self.base_retriever = vectorstore.as_retriever(
            search_type=config.RETRIEVAL_SEARCH_TYPE,
            search_kwargs={"k": 10}
        )
        
        # Recreate hybrid retriever
        self.retriever = self._create_hybrid_retriever()
        
        self._initialize_chain()
        logging.info("✅ Vectorstore and hybrid retriever updated")
    
    def _create_hybrid_retriever(self, metadata_filter: dict = None):
        """Create hybrid retriever with optional metadata filtering.
        
        Args:
            metadata_filter: Optional dict for filtering (e.g., {"course_id": 3})
        """
        try:
            # Create base retriever with optional metadata filter
            search_kwargs = {"k": 10}
            if metadata_filter:
                search_kwargs["filter"] = metadata_filter
            
            base_retriever = self.vectorstore.as_retriever(
                search_type=config.RETRIEVAL_SEARCH_TYPE,
                search_kwargs=search_kwargs
            )
            
            # Load documents for BM25 if we have vectorstore
            documents = []
            if self.all_documents:
                documents = self.all_documents
                logging.info(f"📚 Creating hybrid retriever with {len(documents)} documents for BM25")
            else:
                # Try to get documents from vectorstore
                try:
                    if hasattr(self.vectorstore, '_collection'):
                        # ChromaDB
                        result = self.vectorstore._collection.get()
                        if result and 'documents' in result:
                            from langchain_core.documents import Document
                            documents = [
                                Document(
                                    page_content=doc,
                                    metadata=meta if meta else {}
                                )
                                for doc, meta in zip(
                                    result['documents'],
                                    result['metadatas'] if result.get('metadatas') else [{}] * len(result['documents'])
                                )
                            ]
                            logging.info(f"📚 Loaded {len(documents)} documents from ChromaDB for BM25")
                except Exception as e:
                    logging.warning(f"⚠️ Could not load documents for BM25: {e}")
            
            # Create hybrid retriever with metadata filter
            hybrid_retriever = HybridRetriever(
                vector_retriever=base_retriever,
                documents=documents,
                k=10,  # Get 10 docs before reranking
                rerank_top_k=config.RETRIEVAL_K,  # Return top 3 after reranking
                alpha=0.6,  # 60% vector, 40% BM25
                metadata_filter=metadata_filter
            )
            
            logging.info("✅ Hybrid retriever initialized")
            return hybrid_retriever
            
        except Exception as e:
            logging.error(f"❌ Failed to create hybrid retriever: {e}")
            logging.info("⚠️ Falling back to vector-only retriever")
            return self.base_retriever