# ProfAI_PROD End-to-End API Flow Documentation

## Overview

This document provides a comprehensive mapping of the end-to-end API flows in the ProfAI_PROD system, detailing every file, function, and service involved from initial API trigger to final response delivery. The system is a multilingual AI-powered educational assistant with PDF processing, course generation, RAG-based chat, and voice interaction capabilities.

## System Architecture Summary

### Core Components
- **Frontend**: Web-based interface (`web/` directory)
- **API Layer**: FastAPI application (`app.py`)
- **Services Layer**: Business logic services (`services/` directory)
- **Core Layer**: Course generation and vectorization (`core/` directory)
- **Processors Layer**: Document and text processing (`processors/` directory)
- **Models Layer**: Pydantic schemas (`models/` directory)
- **Utils Layer**: Connection monitoring and utilities (`utils/` directory)

### External Integrations
- **OpenAI GPT-4o-mini**: Content generation and general LLM tasks
- **Sarvam AI**: Multilingual TTS/STT/translation (11 Indian languages)
- **ChromaDB/FAISS**: Vector storage for RAG
- **Groq API**: RAG-based question answering

---

## E2E Flow #0: System Startup & Initialization

### **Entry Point**: `run_profai_websocket.py`

This is the **primary entry point** for the ProfAI_PROD system that starts both FastAPI and WebSocket servers.

### **Startup Sequence**

#### 1. Main Entry Point
**File**: `run_profai_websocket.py`  
**Function**: `main()`  
**Lines**: 31-96

```python
def main()
├── Port availability check for 5001 (FastAPI) and 8765 (WebSocket)
├── Starts FastAPI server in background thread via start_fastapi_server()
├── Starts WebSocket server via start_websocket_server()
└── Handles graceful shutdown on KeyboardInterrupt
```

#### 2. FastAPI Server Initialization
**Function**: `start_fastapi_server()`  
**Lines**: 16-22

```python
def start_fastapi_server()
├── Imports uvicorn and app from app.py
├── Starts FastAPI server on host="0.0.0.0", port=5001
└── Makes web interface available at http://localhost:5001
```

**File**: `app.py`  
**Lines**: 44-82
```python
# FastAPI App Initialization
app = FastAPI(title="ProfAI API", version="2.0.0")
├── Configures CORS middleware (allow_origins=["*"])
├── Mounts static files from web/ directory
├── Initializes all services:
│   ├── ChatService() - RAG-based conversations
│   ├── DocumentService() - PDF processing
│   ├── AudioService() - TTS/STT operations
│   └── TeachingService() - Educational content delivery
└── Registers API endpoints for PDF upload and processing
```

#### 3. WebSocket Server Initialization
**Function**: `start_websocket_server()`  
**Lines**: 24-29

```python
def start_websocket_server()
├── Imports websocket_server.start_websocket_server
├── Starts WebSocket server on host="0.0.0.0", port=8765
└── Makes WebSocket interface available at ws://localhost:8765
```

**File**: `websocket_server.py`  
**Function**: `start_websocket_server()`
```python
async def start_websocket_server(host, port)
├── Initializes WebSocket connection handler
├── Sets up client connection management
├── Registers message handlers for different message types
├── Starts listening for WebSocket connections
└── Handles client connections via handle_client() function
```

---

## E2E Flow #1: PDF Upload & Course Generation

### **Trigger**: `POST /api/upload-pdfs`

### **Entry Point**
**File**: `app.py`  
**Function**: `upload_and_process_pdfs()`  
**Lines**: 86-108

### **Flow Sequence**

#### 1. Request Validation & File Handling
```python
# app.py:86-108
async def upload_and_process_pdfs(files: List[UploadFile], course_title: str)
├── Validates service availability (SERVICES_AVAILABLE check)
├── Calls document_service.process_pdfs_and_generate_course()
```

#### 2. Document Service Processing
**File**: `services/document_service.py`  
**Function**: `DocumentService.process_pdfs_and_generate_course()`  
**Lines**: 24-26
```python
async def process_pdfs_and_generate_course() 
└── Delegates to process_uploaded_pdfs()
```

**Function**: `DocumentService.process_uploaded_pdfs()`  
**Lines**: 28-96
```python
def process_uploaded_pdfs(pdf_files, course_title)
├── Clears/prepares documents directory (config.DOCUMENTS_DIR)
├── Saves uploaded PDFs to disk
├── STEP 1: Extract text from PDFs
├── STEP 2: Chunk documents  
├── STEP 3: Create vector store
├── STEP 4: Generate course
└── STEP 5: Save course output
```

#### 3. PDF Text Extraction
**File**: `processors/pdf_extractor.py`  
**Class**: `PDFExtractor`  
**Function**: `extract_text_from_directory()`  
**Lines**: 37-69
```python
def extract_text_from_directory(directory_path)
├── Iterates through PDF files in directory
├── Calls _extract_from_pdf() for each PDF
└── Returns List[Dict[str, str]] with source and content
```

**Function**: `_extract_from_pdf()`  
**Lines**: 14-24
```python
def _extract_from_pdf(file_path)
├── Uses PyPDF2.PdfReader to read PDF
├── Extracts text from each page
└── Returns concatenated text content
```

#### 4. Text Chunking
**File**: `processors/text_chunker.py`  
**Class**: `TextChunker`  
**Function**: `chunk_documents()`  
**Lines**: 20-41
```python
def chunk_documents(documents: List[Dict[str, str]])
├── Uses RecursiveCharacterTextSplitter
├── Splits each document into chunks
├── Creates Document objects with metadata
└── Returns List[Document] with chunked content
```

#### 5. Vector Store Creation
**File**: `core/vectorizer.py`  
**Class**: `Vectorizer`  
**Function**: `create_vector_store()`  
**Lines**: 18-31
```python
def create_vector_store(chunks: List[Document])
├── Uses OpenAIEmbeddings for embeddings
├── Creates FAISS vector store from documents
└── Returns FAISS vectorstore object
```

**Function**: `save_vector_store()`  
**Lines**: 33-43
```python
def save_vector_store(vector_store, path)
├── Creates directory structure
├── Saves FAISS vector store to local path
└── Persists for future retrieval operations
```

#### 6. Course Generation
**File**: `core/course_generator.py`  
**Class**: `CourseGenerator`  
**Function**: `generate_course()`  
**Lines**: 32-50
```python
def generate_course(documents, retriever, course_title)
├── Step 1: Generate curriculum structure (_generate_curriculum)
└── Step 2: Generate content for each topic (_generate_content)
```

**Function**: `_generate_curriculum()`  
**Lines**: 52-95
```python
def _generate_curriculum(documents, course_title)
├── Creates context from all documents
├── Uses ChatOpenAI with curriculum generation model
├── Applies curriculum prompt template
├── Uses JsonOutputParser with CourseLMS schema
└── Returns structured CourseLMS curriculum
```

**Function**: `_generate_content()`  
**Lines**: 97-154
```python
def _generate_content(curriculum, retriever)
├── For each module and sub-topic in curriculum:
│   ├── Retrieves relevant documents using retriever
│   ├── Creates context-aware content generation prompt
│   ├── Uses ChatOpenAI content generation model
│   └── Generates detailed content for sub-topic
└── Returns complete CourseLMS with content
```

#### 7. Response Formation & Persistence
**File**: `services/document_service.py`  
**Lines**: 85-92
```python
# Save course output
├── Creates courses directory (config.COURSES_DIR)
├── Saves course JSON to OUTPUT_JSON_PATH
└── Returns final_course.dict() as API response
```

### **Models Used**
**File**: `models/schemas.py`  
- `CourseLMS`: Main course structure (lines 19-22)
- `Module`: Week-based module structure (lines 13-17)  
- `SubTopic`: Individual topic with content (lines 8-11)

### **Configuration Dependencies**
**File**: `config.py`
- `DOCUMENTS_DIR`: PDF storage location
- `VECTORSTORE_DIR`: Vector embeddings storage  
- `COURSES_DIR`: Generated course output location
- `CHUNK_SIZE`, `CHUNK_OVERLAP`: Text chunking parameters
- `EMBEDDING_MODEL_NAME`: OpenAI embedding model
- `CURRICULUM_GENERATION_MODEL`: GPT model for curriculum
- `CONTENT_GENERATION_MODEL`: GPT model for content

---

## E2E Flow #2: WebSocket Chat with RAG

### **Trigger**: WebSocket message sent to `ws://localhost:8765`

### **Entry Point**
**File**: `websocket_server.py`  
**Function**: `handle_client(websocket, path)`

**WebSocket Connection**: Client connects to `ws://localhost:8765`

### **Complete E2E Flow Sequence**

#### 0. WebSocket Connection & Message Reception
**File**: `websocket_server.py`
```python
async def handle_client(websocket, path)
├── Accepts WebSocket connection
├── Generates unique client_id using timestamp + random
├── Logs connection with client_id
├── Enters message receiving loop:
│   ├── Receives JSON message from client
│   ├── Parses message type and content
│   └── Routes to appropriate handler based on message type
├── Handles connection errors and disconnections
└── Cleans up resources on disconnect
```

#### 1. Chat Request Processing
**File**: `services/chat_service.py`  
**Class**: `ChatService`  
**Function**: `ask_question()`  
**Lines**: 61-111

```python
async def ask_question(query, query_language_code)
├── Determines response language from config.SUPPORTED_LANGUAGES
├── If non-English query:
│   └── Translates to English using SarvamService
├── Executes RAG chain via RAGService
├── If RAG fails:
│   └── Falls back to general LLM response
└── Returns {"answer": str, "sources": List[str]}
```

#### 2. RAG Service Processing
**File**: `services/rag_service.py`  
**Class**: `RAGService`  
**Function**: `get_answer()`  
**Lines**: 45-55

```python
async def get_answer(question, response_language)
├── Invokes RAG chain with question and response language
├── Chain components:
│   ├── Retriever: Gets relevant documents from vectorstore
│   ├── Context formatter: Formats retrieved documents
│   ├── Prompt: QA_PROMPT_TEMPLATE with context and question
│   ├── LLM: ChatGroq with llama-3.1-8b-instant
│   └── Parser: StrOutputParser for text output
└── Returns generated answer string
```

#### 3. Document Retrieval
**File**: `services/rag_service.py`  
**Lines**: 22-26, 34-43
```python
# Retriever initialization
self.retriever = vectorstore.as_retriever(
    search_type=config.RETRIEVAL_SEARCH_TYPE,
    search_kwargs={"k": config.RETRIEVAL_K}
)

# RAG Chain execution
rag_chain = {
    "context": lambda x: format_docs(retriever.invoke(x["question"])),
    "question": lambda x: x["question"], 
    "response_language": lambda x: x["response_language"]
} | prompt | llm | parser
```

#### 4. Multilingual Translation (if needed)
**File**: `services/sarvam_service.py`  
**Class**: `SarvamService`  
**Function**: `translate_text()`
```python
async def translate_text(text, source_language_code, target_language_code)
├── Makes API call to Sarvam AI translation endpoint
├── Handles 11 supported Indian languages + English
└── Returns translated text
```

#### 5. LLM Fallback Processing
**File**: `services/llm_service.py`  
**Class**: `LLMService`  
**Function**: `get_general_response()`  
**Lines**: 18-37

```python
async def get_general_response(query, target_language)
├── Creates system prompt with target language instruction
├── Uses AsyncOpenAI client with GPT model
├── Applies temperature=0.7 for creativity
└── Returns general knowledge response
```

### **Vector Store Management**
**File**: `services/document_service.py`  
**Class**: `DocumentProcessor`  
**Function**: `get_vectorstore()`  
**Lines**: 107-127

```python
def get_vectorstore(recreate=False, documents=None)
├── If recreating: Creates new Chroma vectorstore
├── If loading: Loads existing Chroma from CHROMA_DB_PATH
├── Uses OpenAIEmbeddings for embedding function
└── Returns Chroma vectorstore instance
```

---

## Complete E2E Request-Response Flow Summary

### **From Entry Point to Response: Complete Execution Path**

#### **Entry Point → Initialization → Processing → Response**

```
🚀 SYSTEM STARTUP
run_profai_websocket.py (main entry)
├── Port checks (5001 FastAPI, 8765 WebSocket)
├── FastAPI server start (background thread)
│   └── app.py initialization with all services
└── WebSocket server start (main thread)
    └── websocket_server.py connection handling

📱 CLIENT REQUEST FLOW
Client connects to ws://localhost:8765
├── websocket_server.py: handle_client()
├── Message parsing and routing
├── Service processing (ChatService/AudioService/TeachingService)
├── External API calls (OpenAI/Sarvam/Groq)
├── Response generation
└── WebSocket response to client

📊 DATA PROCESSING PIPELINE
PDF Upload → Text Extraction → Chunking → Vectorization → Course Generation
Chat Query → Translation → RAG Retrieval → LLM Processing → Response
TTS Request → Sarvam AI → Audio Generation → Streaming to Client
```

---

## E2E Flow #3: Text-to-Speech (TTS) Audio Generation

### **Trigger**: TTS request via WebSocket message

### **Entry Point**
**File**: `websocket_server.py` → `services/audio_service.py`  
**Class**: `AudioService`

### **Flow Sequence**

#### 1. Audio Service Processing
**Function**: `generate_audio_from_text()`  
**Lines**: 22-37
```python
async def generate_audio_from_text(text, language, ultra_fast=False)
├── Determines effective language (defaults to first supported)
├── If ultra_fast=True:
│   └── Calls sarvam_service.generate_audio_ultra_fast()
├── Else:
│   └── Calls sarvam_service.generate_audio()
└── Returns io.BytesIO audio buffer
```

#### 2. Streaming Audio Generation
**Function**: `stream_audio_from_text()`  
**Lines**: 39-71
```python
async def stream_audio_from_text(text, language, websocket)
├── Calls sarvam_service.stream_audio_generation()
├── Yields audio chunks as they're generated
├── Handles disconnection gracefully using connection_monitor utils
├── Falls back to ultra_fast generation if streaming fails
└── Async generator yielding audio chunk bytes
```

#### 3. Sarvam AI Integration
**File**: `services/sarvam_service.py`  
**Class**: `SarvamService`  
**Function**: `generate_audio()`
```python
async def generate_audio(text, language_code, speaker)
├── Makes API call to Sarvam TTS endpoint
├── Handles language-specific voice selection
├── Returns audio data as BytesIO buffer
└── Supports 11 Indian languages + English
```

#### 4. Connection Monitoring
**File**: `utils/connection_monitor.py`  
**Functions**: Multiple utilities for WebSocket state management
```python
is_client_connected(websocket) # Lines 81-113
├── Checks websocket.state for OPEN status
├── Validates connection health
└── Returns boolean connection status

send_chunk_safely(websocket, chunk_data, client_id) # Lines 143-171  
├── Validates connection before sending
├── Sends JSON-encoded chunk data
├── Handles ConnectionClosed exceptions
└── Returns success boolean
```

---

## E2E Flow #4: Teaching Content Generation

### **Trigger**: Teaching content request via WebSocket

### **Entry Point**
**File**: `websocket_server.py` → `services/teaching_service.py`  
**Class**: `TeachingService`

### **Complete Execution Path**
```
WebSocket Message (teaching request)
↓
websocket_server.py: handle_client() - message parsing
↓
services/teaching_service.py: generate_teaching_content()
↓
services/llm_service.py: generate_response() - OpenAI API call
↓
Content formatting for TTS
↓
services/audio_service.py: generate_audio_from_text()
↓
services/sarvam_service.py: generate_audio() - Sarvam AI API
↓
WebSocket response with audio chunks
↓
Client receives streamed audio response
```

### **Flow Sequence**

#### 1. Teaching Content Generation
**Function**: `generate_teaching_content()`  
**Lines**: 56-104
```python
async def generate_teaching_content(module_title, sub_topic_title, raw_content, language)
├── Truncates content if >6000 chars to avoid timeout
├── Creates comprehensive teaching prompt via _create_teaching_prompt()
├── Generates content using LLMService with 5s timeout
├── Formats content for TTS via _format_for_tts()
├── Falls back to _create_fallback_content() if LLM fails
└── Returns formatted teaching content string
```

#### 2. Streaming Teaching Content
**Function**: `generate_teaching_content_stream()`  
**Lines**: 16-54
```python
async def generate_teaching_content_stream(module_title, sub_topic_title, raw_content, language)
├── Creates teaching prompt via _create_teaching_prompt()
├── Streams content using llm_service.generate_response_stream()
├── Yields chunks as they're generated
├── Falls back to basic content if streaming fails
└── Async generator yielding content chunks
```

#### 3. Teaching Prompt Creation
**Function**: `_create_teaching_prompt()`  
**Lines**: 106-153
```python
def _create_teaching_prompt(module_title, sub_topic_title, raw_content, language)
├── Gets language-specific instruction via _get_language_instruction()
├── Creates comprehensive teaching prompt with:
│   ├── Context (module, topic, language)
│   ├── Raw content to teach
│   ├── Teaching instructions (9 detailed steps)
│   ├── Teaching style guidelines
│   └── Response format requirements
└── Returns complete prompt string
```

#### 4. Content Formatting for TTS
**Function**: `_format_for_tts()`  
**Lines**: 172-189
```python
def _format_for_tts(content)
├── Adds natural pauses after punctuation (". " → ". ... ")
├── Adds longer pauses for paragraph breaks ("\n\n" → " ... ... ")
├── Ensures proper sentence endings
├── Adds natural closing statement
└── Returns TTS-optimized content string
```

#### 5. Multilingual Support
**Function**: `_get_language_instruction()`  
**Lines**: 155-170
```python
def _get_language_instruction(language)
├── Maps language codes to native language instructions
├── Supports 11 Indian languages + English
├── Provides language-specific response instructions
└── Returns localized instruction string
```

---

## Error Handling & Connection Management

### **WebSocket Connection Management**
**File**: `utils/connection_monitor.py`

#### Connection State Validation
```python
is_normal_closure(exception) # Lines 20-48
├── Checks for ConnectionClosedOK exceptions
├── Validates closure codes (1000=OK, 1001=Going Away)
├── Analyzes error messages for normal closure indicators
└── Returns boolean indicating normal vs error disconnect

validate_connection_before_operation(websocket, client_id, operation) # Lines 236-254
├── Checks connection state before operations
├── Logs disconnection with appropriate context
└── Returns boolean operation permission
```

#### Connection Monitoring Class
```python
ConnectionStateMonitor # Lines 256-318
├── Tracks connection metrics (chunks_sent, bytes_sent, disconnections)
├── Monitors session duration and activity timestamps  
├── Provides health checks with configurable idle timeouts
└── Generates detailed connection diagnostics
```

### **Service Error Handling Patterns**

#### Chat Service
- Translation fallback to original text if Sarvam AI fails
- RAG to general LLM fallback if retrieval fails  
- Timeout handling for external API calls

#### Audio Service  
- Streaming to ultra_fast fallback if real-time fails
- Connection validation before each chunk send
- Graceful handling of client disconnections

#### Teaching Service
- Content truncation to prevent timeouts
- LLM generation to fallback content if AI fails
- Streaming to batch generation fallback

---

## Configuration & Dependencies

### **Key Configuration Files**
**File**: `config.py`
```python
# API Keys
OPENAI_API_KEY, GROQ_API_KEY, SARVAM_API_KEY

# Models  
LLM_MODEL_NAME = "gpt-4o-mini"
CURRICULUM_GENERATION_MODEL = "gpt-4o-mini"
CONTENT_GENERATION_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# Storage Paths
DOCUMENTS_DIR, VECTORSTORE_DIR, COURSES_DIR, OUTPUT_JSON_PATH
CHROMA_DB_PATH, CHROMA_COLLECTION_NAME

# Processing Parameters
CHUNK_SIZE = 1000, CHUNK_OVERLAP = 200, MAX_CHUNK_SIZE = 1500
RETRIEVAL_SEARCH_TYPE = "similarity", RETRIEVAL_K = 3

# Languages
SUPPORTED_LANGUAGES = [11 Indian languages + English with codes and names]
```

### **External Service Dependencies**
1. **OpenAI API**: GPT-4o-mini for content generation, embeddings
2. **Sarvam AI API**: TTS/STT/translation for Indian languages  
3. **Groq API**: Llama-3.1-8b-instant for RAG-based QA
4. **ChromaDB/FAISS**: Vector storage and similarity search
5. **FastAPI/WebSocket**: Real-time communication infrastructure

---

## Performance Considerations

### **Optimization Strategies**
1. **Content Truncation**: Teaching service limits content to 5500 chars
2. **Timeout Management**: 5s LLM timeouts, 8s OpenAI client timeouts
3. **Streaming**: Real-time audio and text generation with fallbacks
4. **Connection Validation**: Pre-operation WebSocket state checks
5. **Vector Store Persistence**: Reuse of embeddings across sessions
6. **Chunked Processing**: Document splitting for efficient retrieval

### **Scalability Features**
1. **Async/Await**: Full async processing pipeline
2. **Connection Monitoring**: Detailed metrics and health checks
3. **Graceful Degradation**: Multiple fallback layers
4. **Modular Services**: Independent, replaceable service components
5. **Language Support**: 12 total languages with unified interface

---

## Complete System Flow Summary

### **Primary Execution Paths in ProfAI_PROD**

1. **System Startup**: `run_profai_websocket.py` → Dual server initialization (FastAPI + WebSocket)
2. **PDF Processing**: HTTP POST → Document processing → Course generation → JSON response
3. **Chat Interaction**: WebSocket → RAG processing → LLM response → Client delivery
4. **Audio Generation**: WebSocket → TTS processing → Audio streaming → Client playback
5. **Teaching Content**: WebSocket → Content generation → Audio synthesis → Educational delivery

### **Key Integration Points**
- **Entry Point**: `run_profai_websocket.py` (primary startup script)
- **Core Services**: All located in `services/` directory
- **External APIs**: OpenAI, Sarvam AI, Groq integrated via service layer
- **Data Storage**: Vector stores (ChromaDB/FAISS) for RAG operations
- **Response Delivery**: Real-time WebSocket streaming with fallback mechanisms

### **Architecture Verification**
✅ **Confirmed**: This documentation covers **only ProfAI_PROD folder** components
✅ **No references** to ProdAI-Roll folder or components
✅ **Complete E2E flows** from `run_profai_websocket.py` entry point to response delivery
✅ **All file paths** relative to ProfAI_PROD directory structure

---

## 5. Quiz Generation and Evaluation Flow

### **Module Quiz Generation (20 Questions)**

**HTTP Request**: `POST /api/quiz/generate-module`

**Entry Point**: `app.py` line 147 (`generate_module_quiz()`)

**Request Flow**:
1. **API Handler**: `app.py:147-186`
   - Validates quiz service availability
   - Loads course content from `config.OUTPUT_JSON_PATH`
   - Validates module week exists in course modules

2. **Quiz Service Initialization**: `services/quiz_service.py:24-33`
   - Creates quiz storage directories (`data/quizzes`, `data/quiz_answers`)
   - Initializes LLMService for question generation

3. **Module Quiz Generation**: `services/quiz_service.py:35-73`
   - `generate_module_quiz()` extracts specific module content
   - `_extract_module_content()` line 187 formats module text
   - `_create_module_quiz_prompt()` line 225 creates LLM prompt
   - LLMService generates 20 MCQ questions via OpenAI API

4. **Question Processing**: `services/quiz_service.py:274-305`
   - `_parse_quiz_response()` parses LLM output into structured questions
   - `_create_question_object()` creates QuizQuestion objects
   - Ensures exactly 20 questions with 4 options each

5. **Data Storage**: `services/quiz_service.py:307-337`
   - `_store_quiz()` saves quiz to JSON files
   - Stores answers separately for security in `quiz_answers` directory
   - Returns quiz without answers to client

**Response**: Quiz object with 20 questions (answers removed for security)

---

### **Course Quiz Generation (40 Questions)**

**HTTP Request**: `POST /api/quiz/generate-course`

**Entry Point**: `app.py` line 188 (`generate_course_quiz()`)

**Request Flow**:
1. **API Handler**: `app.py:188-217`
   - Loads complete course content from JSON file
   - Initiates comprehensive quiz generation

2. **Course Content Processing**: `services/quiz_service.py:75-114`
   - `generate_course_quiz()` extracts all module content
   - `_extract_all_course_content()` line 209 compiles full course text
   - Generates 40 questions in two 20-question batches for better quality

3. **Batch Question Generation**: `services/quiz_service.py:92-108`
   - `_create_course_quiz_prompt()` creates comprehensive prompts
   - Two separate LLM calls for questions 1-20 and 21-40
   - Combines results into single 40-question quiz

4. **Quiz Assembly and Storage**: Similar to module quiz
   - Validates 40 questions total
   - Stores quiz and answers separately
   - Returns display version without correct answers

**Response**: Quiz object with 40 questions covering entire course

---

### **Quiz Submission and Evaluation Flow**

**HTTP Request**: `POST /api/quiz/submit`

**Entry Point**: `app.py` line 219 (`submit_quiz()`)

**Request Flow**:
1. **API Handler**: `app.py:219-241`
   - Receives QuizSubmission with user answers
   - Validates quiz service availability

2. **Answer Evaluation**: `services/quiz_service.py:116-162`
   - `evaluate_quiz()` loads stored correct answers
   - `_load_quiz_answers()` retrieves answer key from secure storage
   - Compares user answers with correct answers

3. **Score Calculation**: `services/quiz_service.py:133-150`
   - Calculates total score and percentage
   - Determines pass/fail status (60% threshold)
   - Creates detailed results for each question

4. **Result Storage**: `services/quiz_service.py:341-362`
   - `_store_submission_result()` saves submission and results
   - Creates audit trail with timestamps
   - Returns QuizResult with score and detailed feedback

**Response**: QuizResult object with score, percentage, and detailed question-by-question results

---

### **Quiz Retrieval Flow**

**HTTP Request**: `GET /api/quiz/{quiz_id}`

**Entry Point**: `app.py` line 243 (`get_quiz()`)

**Request Flow**:
1. **API Handler**: `app.py:243-260`
   - Validates quiz_id parameter
   - Checks quiz service availability

2. **Secure Quiz Loading**: `services/quiz_service.py:164-185`
   - `get_quiz_without_answers()` loads quiz from storage
   - Removes correct answers and explanations for security
   - Returns display-safe quiz version

**Response**: Quiz object without correct answers for frontend display

---

### **Quiz API Integration Points**

**Data Storage Structure**:
```
ProfAI_PROD/data/
├── quizzes/           # Quiz questions and metadata
│   └── {quiz_id}.json
├── quiz_answers/      # Secure answer storage
│   ├── {quiz_id}_answers.json
│   └── {quiz_id}_{user_id}_submission.json
```

**Security Features**:
- Correct answers stored separately from quiz questions
- Client never receives correct answers until submission
- Answer validation occurs server-side only
- Submission audit trail with timestamps

**External Dependencies**:
- **LLMService**: OpenAI GPT-4o-mini for question generation
- **Course Content**: Requires generated course JSON from DocumentService
- **File System**: JSON-based storage for quizzes and results

---

This documentation provides a complete mapping of all E2E flows in the **ProfAI_PROD system only**, including the new quiz generation and evaluation capabilities, enabling developers to understand the full request lifecycle from the `run_profai_websocket.py` entry point through service processing to response delivery.
