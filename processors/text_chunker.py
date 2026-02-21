"""
Text Chunker - Splits raw text into smaller, structured Document objects
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List, Dict
import logging

class TextChunker:
    """Splits raw text into smaller, structured Document objects."""

    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    def chunk_documents(self, documents: List[Dict[str, str]]) -> List[Document]:
        """
        Takes raw document content and splits it into chunks.
        Each chunk is a LangChain Document object with metadata.
        """
        logging.info(f"Starting to chunk {len(documents)} documents...")
        all_chunks = []
        
        for doc in documents:
            chunks = self.text_splitter.split_text(doc['content'])
            for i, chunk in enumerate(chunks):
                all_chunks.append(Document(
                    page_content=chunk, 
                    metadata={
                        "source": doc['source'],
                        "chunk_id": i,
                        "total_chunks": len(chunks)
                    }
                ))
        
        logging.info(f"Successfully created {len(all_chunks)} chunks")
        return all_chunks