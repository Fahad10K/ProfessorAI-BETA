"""
Cloud Vectorizer - Handles connection to ChromaDB Cloud
"""

import logging
import chromadb
from langchain_openai import OpenAIEmbeddings
try:
    from langchain_chroma import Chroma
except ImportError:
    # Fallback to old import for compatibility
    from langchain_community.vectorstores import Chroma

import config

class CloudVectorizer:
    """Handles connection and operations with ChromaDB Cloud."""

    def __init__(self):
        """Initializes the connection to ChromaDB Cloud."""
        if not all([config.CHROMA_CLOUD_API_KEY, config.CHROMA_CLOUD_TENANT, config.CHROMA_CLOUD_DATABASE]):
            raise ValueError("ChromaDB Cloud credentials are not fully configured in the .env file.")
        
        self.client = chromadb.CloudClient(
            api_key=config.CHROMA_CLOUD_API_KEY,
            tenant=config.CHROMA_CLOUD_TENANT,
            database=config.CHROMA_CLOUD_DATABASE
        )
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL_NAME, 
            openai_api_key=config.OPENAI_API_KEY,
            chunk_size=200   # Process documents in batches of 200 to satisfy ChromaDB Cloud's limit of 300 per upsert
        )
        logging.info("ChromaDB Cloud client initialized.")

    def get_vector_store(self):
        """
        Retrieves the existing vector store from ChromaDB Cloud.
        This is used for querying (e.g., in ChatService).
        """
        try:
            logging.info(f"Loading existing ChromaDB Cloud collection: {config.CHROMA_COLLECTION_NAME}")
            vector_store = Chroma(
                client=self.client,
                collection_name=config.CHROMA_COLLECTION_NAME,
                embedding_function=self.embeddings
            )
            return vector_store
        except Exception as e:
            logging.error(f"Failed to load ChromaDB collection: {e}")
            # This might happen if the collection doesn't exist yet.
            # It will be created when documents are added.
            return None

    def create_vector_store_from_documents(self, documents):
        """
        Creates a new vector store in ChromaDB Cloud from a list of documents.
        This is used for ingestion (e.g., in DocumentService).
        """
        if not documents:
            logging.error("Cannot create vector store: No documents provided.")
            return None
        
        try:
            logging.info(f"Creating/updating ChromaDB Cloud collection '{config.CHROMA_COLLECTION_NAME}' with {len(documents)} documents.")
            
            # Manual batching to respect ChromaDB Cloud's 300 record limit per upsert
            batch_size = 200
            vector_store = None
            
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                logging.info(f"Processing batch {i//batch_size + 1}: {len(batch)} documents")
                
                if vector_store is None:
                    # Create the initial vector store with the first batch
                    vector_store = Chroma.from_documents(
                        documents=batch,
                        embedding_function=self.embeddings,
                        client=self.client,
                        collection_name=config.CHROMA_COLLECTION_NAME,
                    )
                else:
                    # Add subsequent batches to the existing vector store
                    vector_store.add_documents(batch)
            
            logging.info("ChromaDB Cloud collection created/updated successfully.")
            
            # Verify upload
            try:
                collection = self.client.get_collection(name=config.CHROMA_COLLECTION_NAME)
                doc_count = collection.count()
                logging.info(f"✅ VERIFICATION: ChromaDB now contains {doc_count} total documents")
                
                # Sample a few documents to verify
                sample = collection.peek(limit=3)
                if sample and 'documents' in sample:
                    logging.info(f"📋 Sample documents in collection:")
                    for idx, doc in enumerate(sample['documents'][:3], 1):
                        preview = doc[:100].replace('\n', ' ')
                        logging.info(f"   {idx}. {preview}...")
            except Exception as e:
                logging.warning(f"⚠️ Could not verify upload: {e}")
            
            return vector_store
        except Exception as e:
            logging.error(f"Failed to create ChromaDB collection from documents: {e}")
            raise
    
    def add_course_content_to_vectorstore(self, course_data: dict, skip_duplicates: bool = True):
        """
        Add course content to ChromaDB with metadata for filtering.
        Supports both database schema (id, title, modules->topics) and legacy JSON schema.
        
        Args:
            course_data: Dict containing course information from database
            skip_duplicates: If True, check if course_id already exists in vectorstore
        """
        from langchain_core.documents import Document
        
        try:
            # Support both 'id' (database) and 'course_id' (legacy JSON)
            course_id = course_data.get('id') or course_data.get('course_number') or course_data.get('course_id')
            # Support both 'title' (database) and 'course_title' (legacy JSON)
            course_title = course_data.get('title') or course_data.get('course_title', '')
            modules = course_data.get('modules', [])
            
            if not course_id:
                logging.error("Cannot add course content: course_id/id is required")
                return False
            
            logging.info(f"📚 Processing course_id={course_id}, title='{course_title}'")
            
            # Check for duplicates if requested
            if skip_duplicates:
                vector_store = self.get_vector_store()
                if vector_store:
                    try:
                        # Query for existing documents with this course_id
                        results = vector_store._collection.get(
                            where={"course_id": int(course_id)},
                            limit=1
                        )
                        if results and results.get('ids'):
                            logging.warning(f"⚠️ Course {course_id} already exists in ChromaDB. Skipping to avoid duplicates.")
                            logging.info(f"   To force re-add, delete existing course {course_id} documents first.")
                            return True  # Not an error, just already exists
                    except Exception as e:
                        logging.debug(f"Could not check for duplicates: {e}")
            
            documents = []
            
            # Create documents from each topic with metadata
            for module in modules:
                week = module.get('week', 0)
                module_title = module.get('title', '')
                
                # Support both 'topics' (database) and 'sub_topics' (legacy JSON)
                topics = module.get('topics', module.get('sub_topics', []))
                
                for topic in topics:
                    topic_title = topic.get('title', '')
                    content = topic.get('content', '')
                    
                    if content and content.strip():
                        # Chunk content if too large (ChromaDB has 16KB limit per document)
                        content_chunks = self._chunk_content(content, max_size=15000)  # Leave some buffer
                        
                        for chunk_idx, chunk in enumerate(content_chunks):
                            chunk_title = topic_title if len(content_chunks) == 1 else f"{topic_title} (Part {chunk_idx + 1})"
                            
                            # Create document with rich metadata for filtering
                            doc = Document(
                                page_content=chunk,
                                metadata={
                                    'course_id': int(course_id),
                                    'course_name': course_title,
                                    'module': module_title,
                                    'week': int(week),
                                    'title': chunk_title,
                                    'source': f"{course_title} - Week {week} - {topic_title}",
                                    'type': 'course_content'
                                }
                            )
                            documents.append(doc)
            
            if not documents:
                logging.warning(f"No content found in course {course_id} ('{course_title}') to add to vectorstore")
                return False
            
            logging.info(f"📦 Adding {len(documents)} course content chunks to ChromaDB for course_id: {course_id} ('{course_title}')")
            
            # Get existing vectorstore or create new one
            vector_store = self.get_vector_store()
            
            if vector_store is None:
                # Create new vectorstore with these documents
                vector_store = self.create_vector_store_from_documents(documents)
            else:
                # Add to existing vectorstore in batches
                batch_size = 200
                for i in range(0, len(documents), batch_size):
                    batch = documents[i:i + batch_size]
                    logging.info(f"Adding course content batch {i//batch_size + 1}: {len(batch)} documents")
                    vector_store.add_documents(batch)
            
            logging.info(f"✅ Successfully added course {course_id} ('{course_title}') content to ChromaDB")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to add course {course_id} ('{course_title}') to vectorstore: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def _chunk_content(self, content: str, max_size: int = 15000) -> list:
        """
        Chunk content into smaller pieces if it exceeds max_size bytes.
        Tries to split at paragraph boundaries when possible.
        
        Args:
            content: Text content to chunk
            max_size: Maximum size in bytes per chunk
            
        Returns:
            List of content chunks
        """
        # Check if chunking is needed
        if len(content.encode('utf-8')) <= max_size:
            return [content]
        
        chunks = []
        paragraphs = content.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            # If adding this paragraph would exceed limit, save current chunk
            test_chunk = current_chunk + "\n\n" + para if current_chunk else para
            if len(test_chunk.encode('utf-8')) > max_size:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = para
                else:
                    # Single paragraph too large, split by sentences
                    sentences = para.split('. ')
                    for sentence in sentences:
                        if len((current_chunk + '. ' + sentence).encode('utf-8')) > max_size:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sentence
                        else:
                            current_chunk = current_chunk + '. ' + sentence if current_chunk else sentence
            else:
                current_chunk = test_chunk
        
        if current_chunk:
            chunks.append(current_chunk)
        
        logging.info(f"   Chunked large content into {len(chunks)} parts")
        return chunks