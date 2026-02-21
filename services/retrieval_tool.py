"""
Retrieval Tool for LangChain 1.0 Agent
Uses @tool decorator pattern for RAG retrieval
"""

import logging
from typing import Tuple, List
from langchain.tools import tool
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class RetrievalToolFactory:
    """Factory to create retrieval tools bound to a specific vector store."""
    
    def __init__(self, vector_store):
        """
        Initialize with vector store.
        
        Args:
            vector_store: LangChain vector store (Chroma, FAISS, etc.)
        """
        self.vector_store = vector_store
        logger.info("✅ RetrievalToolFactory initialized")
    
    def create_retrieval_tool(self, k: int = 5):
        """
        Create a retrieval tool for the agent.
        
        Args:
            k: Number of documents to retrieve
            
        Returns:
            LangChain tool function
        """
        vector_store = self.vector_store
        
        @tool(response_format="content_and_artifact")
        def retrieve_course_context(query: str) -> Tuple[str, List[Document]]:
            """
            Retrieve relevant course content to help answer student questions.
            Use this tool when you need to find information from the course materials.
            
            Args:
                query: The search query to find relevant course content
                
            Returns:
                Tuple of (formatted_context_string, list_of_documents)
            """
            try:
                logger.info(f"🔍 Retrieving context for: {query[:50]}...")
                
                # Retrieve documents using similarity search
                retrieved_docs = vector_store.similarity_search(query, k=k)
                
                if not retrieved_docs:
                    logger.warning("⚠️ No documents retrieved")
                    return "No relevant course content found.", []
                
                logger.info(f"✅ Retrieved {len(retrieved_docs)} documents")
                
                # Format documents for the agent
                formatted_parts = []
                for i, doc in enumerate(retrieved_docs, 1):
                    source = doc.metadata.get('source', 'Unknown')
                    content = doc.page_content
                    formatted_parts.append(
                        f"--- Document {i} ---\n"
                        f"Source: {source}\n"
                        f"Content: {content}\n"
                    )
                
                serialized = "\n".join(formatted_parts)
                
                return serialized, retrieved_docs
                
            except Exception as e:
                logger.error(f"❌ Error retrieving context: {e}")
                return f"Error retrieving course content: {str(e)}", []
        
        return retrieve_course_context
    
    def create_hybrid_retrieval_tool(self, hybrid_retriever, k: int = 5):
        """
        Create a retrieval tool using hybrid retriever (vector + BM25 + reranking).
        
        Args:
            hybrid_retriever: HybridRetriever instance
            k: Number of documents to retrieve
            
        Returns:
            LangChain tool function
        """
        
        @tool(response_format="content_and_artifact")
        def retrieve_course_context_hybrid(query: str) -> Tuple[str, List[Document]]:
            """
            Retrieve relevant course content using advanced hybrid search (vector + BM25 + reranking).
            Use this for better retrieval accuracy on complex queries.
            
            Args:
                query: The search query to find relevant course content
                
            Returns:
                Tuple of (formatted_context_string, list_of_documents)
            """
            try:
                logger.info(f"🔍 [HYBRID] Retrieving context for: {query[:50]}...")
                
                # Use hybrid retriever for better results
                retrieved_docs = hybrid_retriever.get_relevant_documents(query)
                
                if not retrieved_docs:
                    logger.warning("⚠️ No documents retrieved")
                    return "No relevant course content found.", []
                
                # Limit to k documents
                retrieved_docs = retrieved_docs[:k]
                logger.info(f"✅ Retrieved {len(retrieved_docs)} documents (hybrid)")
                
                # Format documents for the agent
                formatted_parts = []
                for i, doc in enumerate(retrieved_docs, 1):
                    source = doc.metadata.get('source', 'Unknown')
                    content = doc.page_content
                    formatted_parts.append(
                        f"--- Document {i} ---\n"
                        f"Source: {source}\n"
                        f"Content: {content}\n"
                    )
                
                serialized = "\n".join(formatted_parts)
                
                return serialized, retrieved_docs
                
            except Exception as e:
                logger.error(f"❌ Error in hybrid retrieval: {e}")
                return f"Error retrieving course content: {str(e)}", []
        
        return retrieve_course_context_hybrid
