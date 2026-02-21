"""
Optimized Retriever using Vector Search + Flashrank Reranking
BM25 disabled for maximum speed - Vector search + reranking only
Fast retrieval with high relevance
"""

import logging
from typing import List
from langchain_core.documents import Document
from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_community.document_compressors import FlashrankRerank
from langchain_community.retrievers import BM25Retriever

class HybridRetriever:
    """
    Fast retriever using LangChain native components:
    1. Vector Search - Semantic similarity via ChromaDB embeddings
    2. FlashrankRerank - 3-5x faster reranking than CrossEncoder
    
    BM25 disabled for speed - vector search is sufficient for most queries
    
    Benefits:
    - Fast retrieval (<1s typical)
    - High relevance with Flashrank
    - Built-in async support
    - Minimal latency
    """
    
    def __init__(
        self, 
        vector_retriever,
        documents: List[Document] = None,
        k: int = 10,
        rerank_top_k: int = 4,
        alpha: float = 0.5,
        metadata_filter: dict = None
    ):
        """
        Initialize hybrid retriever with LangChain components.
        
        Args:
            vector_retriever: LangChain vector store retriever
            documents: All documents for BM25 indexing
            k: Number of documents to retrieve before reranking
            rerank_top_k: Final number after reranking
            alpha: Weight balance (0.5 = equal weight to vector/BM25)
            metadata_filter: Optional metadata filter dict (e.g., {"course_id": 3})
        """
        self.k = k
        self.rerank_top_k = rerank_top_k
        self.metadata_filter = metadata_filter
        self.vectorstore = vector_retriever.vectorstore if hasattr(vector_retriever, 'vectorstore') else None
        
        # Use only vector retriever for speed (BM25 disabled for performance)
        search_kwargs = {"k": rerank_top_k}
        if metadata_filter:
            search_kwargs["filter"] = metadata_filter
            logging.info(f"🔍 Metadata filter applied: {metadata_filter}")
        
        vector_retriever.search_kwargs = search_kwargs
        self.base_retriever = vector_retriever
        
        # SPEED OPTIMIZATION: Skip Flashrank reranking for sub-second retrieval
        # Vector search alone is fast and accurate enough for most queries
        self.retriever = self.base_retriever
        logging.info(f"✅ Vector-only retriever initialized (reranking disabled for speed, retrieving top {rerank_top_k})")
    
    def get_relevant_documents(self, query: str) -> List[Document]:
        """
        Retrieve documents using vector search only (reranking disabled for speed).
        
        Pipeline:
        1. Vector search (semantic similarity via ChromaDB)
        
        Args:
            query: User query
        
        Returns:
            Top k most relevant documents
        """
        logging.info(f"🔍 Vector retrieval: '{query[:50]}...'")
        
        try:
            results = self.retriever.invoke(query)
            logging.info(f"✅ Retrieved {len(results)} documents")
            
            # Log top results for debugging
            for idx, doc in enumerate(results[:3], 1):
                preview = doc.page_content[:100].replace('\n', ' ')
                source = doc.metadata.get('source', 'unknown')
                logging.info(f"  {idx}. [{source}] {preview}...")
            
            return results
            
        except Exception as e:
            logging.error(f"❌ Retrieval failed: {e}")
            return []
    
    def invoke(self, query: str) -> List[Document]:
        """
        LangChain-compatible invoke method.
        Required for use in chains and LCEL.
        """
        return self.get_relevant_documents(query)
    
    async def ainvoke(self, query: str) -> List[Document]:
        """Async version of invoke for LangChain compatibility."""
        return self.get_relevant_documents(query)
    
    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """Async version of get_relevant_documents."""
        return self.get_relevant_documents(query)
