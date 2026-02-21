"""
Document Extractor Service - Handles document content extraction using LangChain
Supports PDF, DOCX, TXT files
"""

import logging
import tempfile
import os
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

class DocumentExtractor:
    """Extract text content from various document types using LangChain loaders"""
    
    def __init__(self):
        self.supported_types = ['pdf', 'docx', 'doc', 'txt']
    
    def extract_content(self, file_path: str, file_type: str) -> Optional[str]:
        """
        Extract text content from a document file
        
        Args:
            file_path: Path to the document file
            file_type: Type of document (pdf, docx, txt)
            
        Returns:
            Extracted text content or None if extraction fails
        """
        try:
            file_type = file_type.lower().replace('.', '')
            
            if file_type not in self.supported_types:
                raise ValueError(f"Unsupported file type: {file_type}. Supported types: {self.supported_types}")
            
            if file_type == 'pdf':
                return self._extract_pdf(file_path)
            elif file_type in ['docx', 'doc']:
                return self._extract_docx(file_path)
            elif file_type == 'txt':
                return self._extract_txt(file_path)
            
        except Exception as e:
            logger.error(f"Error extracting content from {file_type} file: {e}")
            return None
    
    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF using LangChain PyPDFLoader"""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            
            # Combine all pages into single text
            content = "\n\n".join([doc.page_content for doc in documents])
            logger.info(f"Extracted {len(documents)} pages from PDF")
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            raise
    
    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX using LangChain Docx2txtLoader"""
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            
            loader = Docx2txtLoader(file_path)
            documents = loader.load()
            
            # Combine all content
            content = "\n\n".join([doc.page_content for doc in documents])
            logger.info(f"Extracted content from DOCX")
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting DOCX content: {e}")
            raise
    
    def _extract_txt(self, file_path: str) -> str:
        """Extract text from TXT file using LangChain TextLoader"""
        try:
            from langchain_community.document_loaders import TextLoader
            
            loader = TextLoader(file_path, encoding='utf-8')
            documents = loader.load()
            
            # Combine all content
            content = "\n\n".join([doc.page_content for doc in documents])
            logger.info(f"Extracted content from TXT")
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting TXT content: {e}")
            raise
    
    def extract_from_bytes(self, file_bytes: bytes, file_name: str, file_type: str) -> Optional[str]:
        """
        Extract content from file bytes by creating temporary file
        
        Args:
            file_bytes: File content as bytes
            file_name: Original file name
            file_type: File type extension
            
        Returns:
            Extracted text content
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=f'.{file_type}') as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name
            
            # Extract content
            content = self.extract_content(tmp_path, file_type)
            
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting content from bytes: {e}")
            return None
    
    def validate_file_type(self, file_name: str) -> bool:
        """Check if file type is supported"""
        file_ext = Path(file_name).suffix.lower().replace('.', '')
        return file_ext in self.supported_types
    
    def get_file_type(self, file_name: str) -> str:
        """Get file type from file name"""
        return Path(file_name).suffix.lower().replace('.', '')
