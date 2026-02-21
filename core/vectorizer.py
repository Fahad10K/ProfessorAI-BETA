"""
Vectorizer - Handles vector embeddings and vector store operations
"""

import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from typing import List
import logging

class Vectorizer:
    """Handles the creation, saving, and loading of vector embeddings and the vector store."""

    def __init__(self, embedding_model: str, api_key: str):
        self.embeddings = OpenAIEmbeddings(model=embedding_model, openai_api_key=api_key, chunk_size=200)

    def create_vector_store(self, chunks: List[Document]):
        """Creates a FAISS vector store from a list of document chunks."""
        if not chunks:
            logging.error("Cannot create vector store: No chunks provided")
            return None
            
        logging.info("Creating new vector store from chunks...")
        try:
            vector_store = FAISS.from_documents(chunks, self.embeddings)
            logging.info("Vector store created successfully")
            return vector_store
        except Exception as e:
            logging.error(f"Failed to create vector store: {e}")
            return None

    def save_vector_store(self, vector_store, path: str):
        """Saves the FAISS vector store to a local path."""
        if not vector_store:
            logging.error("Cannot save: Invalid vector store provided")
            return
        try:
            os.makedirs(path, exist_ok=True)
            vector_store.save_local(path)
            logging.info(f"Vector store saved successfully to {path}")
        except Exception as e:
            logging.error(f"Failed to save vector store: {e}")

    @staticmethod
    def load_vector_store(path: str, embeddings):
        """Loads a FAISS vector store from a local path."""
        if not os.path.exists(path):
            logging.error(f"Cannot load vector store: Path does not exist at {path}")
            return None
        try:
            vector_store = FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)
            logging.info(f"Vector store loaded successfully from {path}")
            return vector_store
        except Exception as e:
            logging.error(f"Failed to load vector store: {e}")
            return None