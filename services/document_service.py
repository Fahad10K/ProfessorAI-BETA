"""
Document Service - Handles PDF processing and course generation
"""

import os
import shutil
import json
import logging
from typing import List
from fastapi import UploadFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

import config

class DocumentService:
    """Service for processing documents and generating courses."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor()
        
        # Initialize database service (if enabled)
        try:
            from services.database_service_actual import get_database_service
            self.db_service = get_database_service()
            if self.db_service:
                logging.info("DocumentService initialized with database support")
            else:
                logging.info("DocumentService initialized (JSON mode - database disabled)")
        except Exception as e:
            logging.warning(f"Database service not available: {e}")
            self.db_service = None
            logging.info("DocumentService initialized (JSON mode)")
    
    async def process_pdfs_and_generate_course(self, pdf_files: List[UploadFile], course_title: str = None):
        """Process uploaded PDF files and generate course content."""
        return self.process_uploaded_pdfs(pdf_files, course_title)
    
    def process_pdf_files_from_paths(self, file_paths: List[dict], course_title: str = None, country: str = None, progress_callback=None):
        """
        Process PDF files from file paths (used by Celery tasks).
        
        Args:
            file_paths: List of dicts with 'path' and 'filename' keys
            course_title: Optional course title
            country: Country where course is offered (e.g., 'India', 'USA')
            progress_callback: Optional callback for progress updates
        
        Returns:
            Course dictionary
        """
        try:
            if progress_callback:
                progress_callback(10, "Starting PDF processing...")
            
            # Clear and prepare documents directory
            self._safe_cleanup_directory(config.DOCUMENTS_DIR)
            os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
            
            if progress_callback:
                progress_callback(15, "Copying PDF files...")
            
            # Copy files to documents directory
            saved_files = []
            for file_info in file_paths:
                file_path = file_info['path']
                filename = file_info['filename']
                
                if not filename.lower().endswith('.pdf'):
                    raise ValueError(f"File {filename} is not a PDF")
                
                dest_path = os.path.join(config.DOCUMENTS_DIR, filename)
                shutil.copy2(file_path, dest_path)
                saved_files.append(dest_path)
                logging.info(f"Copied PDF: {filename}")
            
            if progress_callback:
                progress_callback(20, f"Processing {len(saved_files)} PDF files...")
            
            # Import processing modules
            from core.course_generator import CourseGenerator
            from processors.pdf_extractor import PDFExtractor
            from processors.text_chunker import TextChunker
            from core.vectorizer import Vectorizer
            
            # Process documents
            if progress_callback:
                progress_callback(30, "Extracting text from PDFs...")
            
            logging.info("STEP 1: Extracting text from PDFs...")
            extractor = PDFExtractor()
            raw_docs = extractor.extract_text_from_directory(config.DOCUMENTS_DIR)
            if not raw_docs:
                raise Exception("No text could be extracted from uploaded documents")

            if progress_callback:
                progress_callback(50, "Chunking documents...")
            
            logging.info("STEP 2: Chunking documents...")
            chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
            doc_chunks = chunker.chunk_documents(raw_docs)
            if not doc_chunks:
                raise Exception("No chunks could be created from documents")

            if progress_callback:
                progress_callback(60, "Creating vector store...")
            
            logging.info("STEP 3: Creating vector store...")
            vector_store = None
            if config.USE_CHROMA_CLOUD:
                from core.cloud_vectorizer import CloudVectorizer
                logging.info("Using ChromaDB Cloud for vector store.")
                cloud_vectorizer = CloudVectorizer()
                vector_store = cloud_vectorizer.create_vector_store_from_documents(doc_chunks)
            else:
                logging.info("Using local FAISS for vector store.")
                vectorizer = Vectorizer(embedding_model=config.EMBEDDING_MODEL_NAME, api_key=config.OPENAI_API_KEY)
                self._safe_cleanup_vectorstore()
                vector_store = vectorizer.create_vector_store(doc_chunks)
                if vector_store:
                    vectorizer.save_vector_store(vector_store, config.FAISS_DB_PATH)

            if not vector_store:
                raise Exception("Vector store could not be created")

            if progress_callback:
                progress_callback(75, "Generating course content...")
            
            logging.info("STEP 4: Generating course...")
            course_generator = CourseGenerator()
            
            # Get the primary PDF filename for source filtering
            primary_pdf_filename = None
            if file_paths:
                primary_pdf_filename = file_paths[0]['filename']
                logging.info(f"Using primary PDF source for filtering: {primary_pdf_filename}")
            
            final_course = course_generator.generate_course(
                doc_chunks, 
                vector_store.as_retriever(), 
                course_title,
                source_filter=primary_pdf_filename
            )
            
            if not final_course:
                raise Exception("Course generation failed")

            if progress_callback:
                progress_callback(90, "Saving course...")
            
            # Save course output
            logging.info("STEP 5: Saving course...")
            os.makedirs(config.COURSES_DIR, exist_ok=True)
            
            # Convert course to dictionary and validate structure
            course_dict = self._validate_and_prepare_course(final_course, course_title)
            if country:
                course_dict['country'] = country
                logging.info(f"Course country set to: {country}")
            # Try database first (if enabled)
            if self.db_service:
                try:
                    course_id = self.db_service.create_course(course_dict, teacher_id='system')
                    
                    # Fetch full course to get course_number and other fields
                    full_course = self.db_service.get_course(course_id)
                    if full_course:
                        course_dict['course_id'] = course_id  # TEXT UUID from database
                        course_dict['course_number'] = full_course.get('course_number')  # INTEGER for easy reference
                        logging.info(f" Course saved to database! Course ID: {course_id}, Course Number: {full_course.get('course_number')}")
                    else:
                        course_dict['course_id'] = course_id
                        logging.info(f" Course saved to database! Course ID: {course_id}")
                    
                    if progress_callback:
                        progress_callback(100, "Course generation completed!")
                    
                    return course_dict
                except Exception as e:
                    logging.warning(f"Failed to save course to database, using JSON fallback: {e}")
            
            # Fallback to JSON files (original logic)
            existing_courses = self._load_existing_courses()
            next_course_id = self._get_next_course_id(existing_courses)
            
            # Ensure unique course title
            course_dict = self._ensure_unique_title(course_dict, existing_courses)
            
            # Assign course id (INTEGER for JSON)
            course_dict['course_id'] = next_course_id
            
            # Append new course to existing courses
            existing_courses.append(course_dict)
            
            self._save_courses_to_file(existing_courses)
            
            logging.info(f" Course saved to JSON! Course ID: {next_course_id}")
            logging.info(f"Total courses in database: {len(existing_courses)}")
            
            if progress_callback:
                progress_callback(100, "Course generation completed!")
            
            return course_dict
            
        except Exception as e:
            logging.error(f"Error processing PDFs from paths: {e}")
            raise e
    
    def process_uploaded_pdfs(self, pdf_files: List[UploadFile], course_title: str = None):
        """Process uploaded PDF files and generate course content."""
        try:
            # Clear and prepare documents directory
            self._safe_cleanup_directory(config.DOCUMENTS_DIR)
            os.makedirs(config.DOCUMENTS_DIR, exist_ok=True)
            
            # Save uploaded PDFs
            saved_files = []
            for pdf_file in pdf_files:
                if not pdf_file.filename.lower().endswith('.pdf'):
                    raise ValueError(f"File {pdf_file.filename} is not a PDF")
                
                file_path = os.path.join(config.DOCUMENTS_DIR, pdf_file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(pdf_file.file, buffer)
                saved_files.append(file_path)
                logging.info(f"Saved uploaded PDF: {pdf_file.filename}")
            
            # Import processing modules
            from core.course_generator import CourseGenerator
            from processors.pdf_extractor import PDFExtractor
            from processors.text_chunker import TextChunker
            from core.vectorizer import Vectorizer
            
            # Process documents
            logging.info("STEP 1: Extracting text from PDFs...")
            extractor = PDFExtractor()
            raw_docs = extractor.extract_text_from_directory(config.DOCUMENTS_DIR)
            if not raw_docs:
                raise Exception("No text could be extracted from uploaded documents")

            logging.info("STEP 2: Chunking documents...")
            chunker = TextChunker(chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP)
            doc_chunks = chunker.chunk_documents(raw_docs)
            if not doc_chunks:
                raise Exception("No chunks could be created from documents")

            logging.info("STEP 3: Creating vector store...")
            vector_store = None
            if config.USE_CHROMA_CLOUD:
                from core.cloud_vectorizer import CloudVectorizer
                logging.info("Using ChromaDB Cloud for vector store.")
                cloud_vectorizer = CloudVectorizer()
                vector_store = cloud_vectorizer.create_vector_store_from_documents(doc_chunks)
            else:
                logging.info("Using local FAISS for vector store.")
                vectorizer = Vectorizer(embedding_model=config.EMBEDDING_MODEL_NAME, api_key=config.OPENAI_API_KEY)
                self._safe_cleanup_vectorstore()
                vector_store = vectorizer.create_vector_store(doc_chunks)
                if vector_store:
                    vectorizer.save_vector_store(vector_store, config.FAISS_DB_PATH)

            if not vector_store:
                raise Exception("Vector store could not be created")

            logging.info("STEP 4: Generating course...")
            course_generator = CourseGenerator()
            
            # Get the primary PDF filename for source filtering
            primary_pdf_filename = None
            if pdf_files:
                primary_pdf_filename = pdf_files[0].filename  # Use first uploaded PDF as primary source
                logging.info(f"Using primary PDF source for filtering: {primary_pdf_filename}")
            
            final_course = course_generator.generate_course(
                doc_chunks, 
                vector_store.as_retriever(), 
                course_title,
                source_filter=primary_pdf_filename
            )
            
            if not final_course:
                raise Exception("Course generation failed")

            # Save course output
            logging.info("STEP 5: Saving course...")
            os.makedirs(config.COURSES_DIR, exist_ok=True)
            
            # Convert course to dictionary and validate structure
            course_dict = self._validate_and_prepare_course(final_course, course_title)
            
            # Try database first (if enabled)
            if self.db_service:
                try:
                    course_id = self.db_service.create_course(course_dict, teacher_id='system')
                    
                    # Fetch full course to get course_number and other fields
                    full_course = self.db_service.get_course(course_id)
                    if full_course:
                        course_dict['course_id'] = course_id  # TEXT UUID from database
                        course_dict['course_number'] = full_course.get('course_number')  # INTEGER for easy reference
                        logging.info(f" Course saved to database! Course ID: {course_id}, Course Number: {full_course.get('course_number')}")
                    else:
                        course_dict['course_id'] = course_id
                        logging.info(f" Course saved to database! Course ID: {course_id}")
                    
                    logging.info(f"Course generation completed successfully!")
                    return course_dict
                except Exception as e:
                    logging.warning(f"Failed to save course to database, using JSON fallback: {e}")
            
            # Fallback to JSON files (original logic)
            existing_courses = self._load_existing_courses()
            next_course_id = self._get_next_course_id(existing_courses)
            
            # Ensure unique course title
            course_dict = self._ensure_unique_title(course_dict, existing_courses)
            
            # Assign course id (INTEGER for JSON)
            course_dict['course_id'] = next_course_id
            
            # Append new course to existing courses
            existing_courses.append(course_dict)
            
            self._save_courses_to_file(existing_courses)
            
            logging.info(f" Course saved to JSON! Course ID: {next_course_id}")
            logging.info(f"Total courses in database: {len(existing_courses)}")
            return course_dict
            
        except Exception as e:
            logging.error(f"Error processing PDFs: {e}")
            raise e
    
    def _validate_and_prepare_course(self, course, course_title: str = None):
        """Validate and prepare course data for saving."""
        try:
            # Convert course to dictionary if it's a Pydantic model
            if hasattr(course, 'dict'):
                course_dict = course.dict()
            elif isinstance(course, dict):
                course_dict = course.copy()
            else:
                raise ValueError("Invalid course format")
            
            # Validate required fields
            required_fields = ['course_title', 'modules']
            for field in required_fields:
                if field not in course_dict:
                    raise ValueError(f"Missing required field: {field}")
            
            # Override title if provided
            if course_title:
                course_dict['course_title'] = course_title
            
            # Validate modules structure
            if not isinstance(course_dict['modules'], list):
                raise ValueError("Modules must be a list")
            
            for i, module in enumerate(course_dict['modules']):
                if not isinstance(module, dict):
                    raise ValueError(f"Module {i} must be a dictionary")
                
                # Ensure required module fields
                if 'week' not in module:
                    module['week'] = i + 1
                if 'title' not in module:
                    module['title'] = f"Module {i + 1}"
                if 'sub_topics' not in module:
                    module['sub_topics'] = []
                
                # Validate sub_topics
                if not isinstance(module['sub_topics'], list):
                    module['sub_topics'] = []
                
                for j, sub_topic in enumerate(module['sub_topics']):
                    if not isinstance(sub_topic, dict):
                        continue
                    if 'title' not in sub_topic:
                        sub_topic['title'] = f"Topic {j + 1}"
                    if 'content' not in sub_topic:
                        sub_topic['content'] = ""
            
            logging.info(f"Course validation successful: {course_dict['course_title']}")
            logging.info(f"Course has {len(course_dict['modules'])} modules")
            return course_dict
            
        except Exception as e:
            logging.error(f"Course validation failed: {e}")
            raise ValueError(f"Course validation failed: {e}")
    
    def _load_existing_courses(self):
        """Load existing courses from file and return as list."""
        existing_courses = []
        
        if os.path.exists(config.OUTPUT_JSON_PATH):
            try:
                with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                
                # Handle both single course and multi-course formats
                if isinstance(existing_data, dict) and 'course_title' in existing_data:
                    # Single course format - convert to list
                    existing_courses = [existing_data]
                    logging.info("Loaded single course format, converting to multi-course format")
                elif isinstance(existing_data, list):
                    # Multi-course format
                    existing_courses = existing_data
                    logging.info(f"Loaded {len(existing_courses)} existing courses")
                else:
                    logging.warning("Invalid course data format, starting fresh")
                    existing_courses = []
                    
            except Exception as e:
                logging.warning(f"Could not load existing courses: {e}")
                existing_courses = []
        else:
            logging.info("No existing course file found, starting fresh")
        
        return existing_courses
    
    def _get_next_course_id(self, existing_courses):
        """Get the next available course ID."""
        if not existing_courses:
            return 1
        
        # Find the maximum course ID
        max_id = 0
        for course in existing_courses:
            course_id = course.get('course_id', 0)
            if isinstance(course_id, int) and course_id > max_id:
                max_id = course_id
        
        return max_id + 1
    
    def _ensure_unique_title(self, course_dict, existing_courses):
        """Ensure the course title is unique by appending a number if necessary."""
        original_title = course_dict['course_title']
        title = original_title
        counter = 1
        
        # Check if title already exists
        existing_titles = [course.get('course_title', '') for course in existing_courses]
        
        while title in existing_titles:
            counter += 1
            title = f"{original_title} ({counter})"
        
        if title != original_title:
            logging.info(f"Course title changed from '{original_title}' to '{title}' to ensure uniqueness")
            course_dict['course_title'] = title
        
        return course_dict
    
    def _save_courses_to_file(self, courses):
        """Save courses to file with proper formatting and validation."""
        try:
            # Validate that courses is a list
            if not isinstance(courses, list):
                raise ValueError("Courses must be a list")
            
            # Validate each course has required fields
            for i, course in enumerate(courses):
                if not isinstance(course, dict):
                    raise ValueError(f"Course {i} must be a dictionary")
                if 'course_id' not in course:
                    raise ValueError(f"Course {i} missing course_id")
                if 'course_title' not in course:
                    raise ValueError(f"Course {i} missing course_title")
                if 'modules' not in course:
                    raise ValueError(f"Course {i} missing modules")
            
            # Always save as array format for consistency
            with open(config.OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
                json.dump(courses, f, indent=4, ensure_ascii=False)
            
            logging.info(f"Successfully saved {len(courses)} courses to {config.OUTPUT_JSON_PATH}")
            
        except Exception as e:
            logging.error(f"Failed to save courses: {e}")
            raise ValueError(f"Failed to save courses: {e}")
    
    def _safe_cleanup_directory(self, directory_path: str, max_retries: int = 3):
        """Safely clean up a directory with retries for Windows file locking issues."""
        import time
        
        if not os.path.exists(directory_path):
            return
            
        for attempt in range(max_retries):
            try:
                shutil.rmtree(directory_path)
                logging.info(f"Successfully cleaned up directory: {directory_path}")
                return
            except PermissionError as e:
                if attempt < max_retries - 1:
                    logging.warning(f"Cleanup attempt {attempt + 1} failed, retrying in 1 second: {e}")
                    time.sleep(1)
                else:
                    logging.error(f"Failed to cleanup directory after {max_retries} attempts: {e}")
                    # Try to remove individual files if directory removal fails
                    self._force_cleanup_directory(directory_path)
            except Exception as e:
                logging.error(f"Unexpected error during directory cleanup: {e}")
                break
    
    def _force_cleanup_directory(self, directory_path: str):
        """Force cleanup by removing individual files and subdirectories."""
        try:
            for root, dirs, files in os.walk(directory_path, topdown=False):
                # Remove files
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.chmod(file_path, 0o777)  # Change permissions
                        os.remove(file_path)
                    except Exception as e:
                        logging.warning(f"Could not remove file {file_path}: {e}")
                
                # Remove directories
                for dir in dirs:
                    dir_path = os.path.join(root, dir)
                    try:
                        os.rmdir(dir_path)
                    except Exception as e:
                        logging.warning(f"Could not remove directory {dir_path}: {e}")
            
            # Finally try to remove the root directory
            try:
                os.rmdir(directory_path)
                logging.info(f"Force cleanup successful for: {directory_path}")
            except Exception as e:
                logging.warning(f"Could not remove root directory {directory_path}: {e}")
                
        except Exception as e:
            logging.error(f"Force cleanup failed: {e}")
    
    def _safe_cleanup_vectorstore(self):
        """Safely cleanup vector store directories."""
        # Clean up both FAISS and Chroma directories
        self._safe_cleanup_directory(config.FAISS_DB_PATH)
        self._safe_cleanup_directory(config.CHROMA_DB_PATH)
        
        # Recreate the directories
        os.makedirs(config.FAISS_DB_PATH, exist_ok=True)
        os.makedirs(config.CHROMA_DB_PATH, exist_ok=True)


class DocumentProcessor:
    """Helper class for document processing operations."""
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL_NAME, 
            openai_api_key=config.OPENAI_API_KEY,
            chunk_size=200   # Process documents in batches of 200 to satisfy ChromaDB Cloud's limit of 300 per upsert
        )
    
    def get_vectorstore(self, recreate: bool = False, documents: List[Document] = None):
        """Get or create vectorstore using FAISS (more reliable on Windows)."""
        from langchain_community.vectorstores import FAISS
        
        if recreate:
            # Use FAISS instead of Chroma to avoid Windows file locking issues
            if not documents:
                raise ValueError("Documents must be provided when recreating vectorstore")
            return FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings
            )
        else:
            # Try to load existing FAISS vectorstore
            if os.path.exists(config.FAISS_DB_PATH):
                try:
                    return FAISS.load_local(
                        config.FAISS_DB_PATH, 
                        self.embeddings, 
                        allow_dangerous_deserialization=True
                    )
                except Exception as e:
                    logging.warning(f"Could not load existing vectorstore: {e}")
                    return None
            return None
    
    def create_vectorstore_from_documents(self, documents: List[Document]):
        """Create a new vectorstore from documents using FAISS."""
        from langchain_community.vectorstores import FAISS
        return FAISS.from_documents(
            documents=documents,
            embedding=self.embeddings
        )
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """Split documents into chunks."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.MAX_CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
        return text_splitter.split_documents(documents)
    
    def load_course_content_as_documents(self, course_json_path: str) -> List[Document]:
        """Load generated course content from JSON file and convert to Document objects."""
        if not os.path.exists(course_json_path):
            return []
        
        try:
            with open(course_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            all_documents = []
            
            # Handle both single course and multi-course formats
            if isinstance(data, dict) and 'course_title' in data:
                # Single course format
                all_documents.extend(self.extract_course_documents(data))
            elif isinstance(data, list):
                # Multi-course format - process all courses
                for course_data in data:
                    if isinstance(course_data, dict):
                        all_documents.extend(self.extract_course_documents(course_data))
            else:
                print("⚠️ Invalid course data format")
                return []
            
            return all_documents            
        except Exception as e:
            print(f"Error loading course content: {e}")
            return []
    
    def extract_course_documents(self, course_data: dict) -> List[Document]:
        """Extract documents from course data."""
        documents = []
        
        # Add course title and overview
        if course_data.get("course_title"):
            documents.append(Document(
                page_content=f"Course Title: {course_data['course_title']}",
                metadata={"source": "course_overview", "type": "title"}
            ))
        
        # Add module and sub-topic content
        for module in course_data.get("modules", []):
            module_content = f"Week {module.get('week', 'N/A')}: {module.get('title', 'Untitled Module')}"
            documents.append(Document(
                page_content=module_content,
                metadata={"source": "course_module", "week": module.get('week'), "type": "module"}
            ))
            
            for sub_topic in module.get("sub_topics", []):
                if sub_topic.get("content"):
                    sub_topic_content = f"Topic: {sub_topic.get('title', 'Untitled Topic')}\n\n{sub_topic['content']}"
                    documents.append(Document(
                        page_content=sub_topic_content,
                        metadata={
                            "source": "course_content", 
                            "week": module.get('week'),
                            "topic": sub_topic.get('title'),
                            "type": "content"
                        }
                    ))
        
        return documents