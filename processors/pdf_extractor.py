"""
PDF Extractor - Extracts text content from PDF documents
"""

import os
import PyPDF2
import docx
import logging
from typing import List, Dict

class PDFExtractor:
    """Extracts text content from various document types."""

    def _extract_from_pdf(self, file_path: str) -> str:
        """Extracts text from a single PDF file."""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
            logging.info(f"Successfully extracted text from PDF: {os.path.basename(file_path)}")
            return text
        except Exception as e:
            logging.error(f"Could not read PDF {file_path}: {e}")
            return ""

    def _extract_from_docx(self, file_path: str) -> str:
        """Extracts text from a single DOCX file."""
        try:
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs if para.text])
            logging.info(f"Successfully extracted text from DOCX: {os.path.basename(file_path)}")
            return text
        except Exception as e:
            logging.error(f"Could not read DOCX {file_path}: {e}")
            return ""

    def extract_text_from_directory(self, directory_path: str) -> List[Dict[str, str]]:
        """
        Iterates through a directory and extracts text from all supported files.
        Returns a list of dictionaries, each containing the source filename and its content.
        """
        all_documents = []
        logging.info(f"Starting text extraction from directory: {directory_path}")
        
        if not os.path.exists(directory_path):
            logging.error(f"Directory does not exist: {directory_path}")
            return all_documents
        
        for filename in os.listdir(directory_path):
            file_path = os.path.join(directory_path, filename)
            content = ""
            
            if filename.lower().endswith('.pdf'):
                content = self._extract_from_pdf(file_path)
            elif filename.lower().endswith('.docx'):
                content = self._extract_from_docx(file_path)
            else:
                logging.warning(f"Skipping unsupported file type: {filename}")
                continue

            if content:
                all_documents.append({"source": filename, "content": content})

        if not all_documents:
            logging.warning("No documents were successfully processed in the directory")
        else:
            logging.info(f"Successfully processed {len(all_documents)} documents")
        
        return all_documents