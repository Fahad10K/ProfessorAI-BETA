# ProfAI Architecture Diagrams

This document contains comprehensive Mermaid diagrams showing the complete architecture of the ProfAI system, including API endpoints, service connections, and frontend integrations.

## 1. Overall System Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI1[index.html<br/>Main Dashboard]
        UI2[chat.html<br/>Chat Interface]
        UI3[upload.html<br/>PDF Upload]
        UI4[course.html<br/>Course Viewer]
        UI5[courses.html<br/>Course List]
        UI6[stream-test.html<br/>WebSocket Test]
        UI7[websocket-status.html<br/>WS Status]
    end
    
    subgraph "API Layer - FastAPI"
        API[app.py<br/>Main FastAPI App]
        
        subgraph "REST Endpoints"
            REST1["/api/upload-pdfs"]
            REST2["/api/courses"]
            REST3["/api/course/{id}"]
            REST4["/api/chat"]
            REST5["/api/chat-with-audio"]
            REST6["/api/transcribe"]
            REST7["/api/start-class"]
            REST8["/health"]
            REST9["/test-services"]
            REST10["/websocket-info"]
        end
        
        subgraph "WebSocket Endpoints"
            WS1["/ws/test"]
            WS2["/ws/audio-stream"]
        end
        
        subgraph "Static Routes"
            STATIC["/static files"]
            ROUTES["HTML routes"]
        end
    end
    
    subgraph "Service Layer"
        CHAT[ChatService]
        DOC[DocumentService]
        AUDIO[AudioService]
        TEACH[TeachingService]
        LLM[LLMService]
        RAG[RAGService]
        SARVAM[SarvamService]
    end
    
    subgraph "Core Layer"
        COURSE[CourseGenerator]
        VECTOR[Vectorizer]
    end
    
    subgraph "Processor Layer"
        PDF[PDFExtractor]
        CHUNK[TextChunker]
    end
    
    subgraph "External APIs"
        OPENAI[OpenAI API]
        SARVAM_API[Sarvam AI API]
        GROQ[Groq API]
    end
    
    subgraph "Data Storage"
        CHROMA[ChromaDB<br/>Vector Store]
        FILES[File System<br/>PDFs & JSON]
    end
    
    %% Frontend to API connections
    UI1 --> REST2
    UI1 --> REST3
    UI1 --> REST5
    UI1 --> REST6
    UI1 --> REST7
    UI1 --> WS2
    
    UI2 --> REST4
    UI2 --> REST6
    
    UI3 --> REST1
    
    UI4 --> REST3
    
    UI5 --> REST2
    
    UI6 --> WS1
    UI6 --> WS2
    UI6 --> REST9
    
    UI7 --> REST10
    UI7 --> WS1
    UI7 --> WS2
    
    %% API to Service connections
    API --> CHAT
    API --> DOC
    API --> AUDIO
    API --> TEACH
    
    %% Service interconnections
    CHAT --> LLM
    CHAT --> RAG
    CHAT --> SARVAM
    CHAT --> DOC
    
    DOC --> COURSE
    DOC --> VECTOR
    DOC --> PDF
    DOC --> CHUNK
    
    AUDIO --> SARVAM
    
    TEACH --> LLM
    
    RAG --> GROQ
    
    LLM --> OPENAI
    
    SARVAM --> SARVAM_API
    
    %% Data connections
    VECTOR --> CHROMA
    RAG --> CHROMA
    DOC --> FILES
    COURSE --> FILES
```

## 2. API Endpoint Details

```mermaid
graph LR
    subgraph "Course Management APIs"
        A1["POST /api/upload-pdfs"]
        A2["GET /api/courses"]
        A3["GET /api/course/{id}"]
        
        A1 --> |"files: List[UploadFile]<br/>course_title: str"| DS[DocumentService]
        A2 --> |"Read course_output.json"| FS[File System]
        A3 --> |"course_id: str"| FS
        
        DS --> |"Process PDFs<br/>Generate Course"| CG[CourseGenerator]
        DS --> |"Extract Text"| PE[PDFExtractor]
        DS --> |"Create Vectors"| VZ[Vectorizer]
    end
    
    subgraph "Chat & Communication APIs"
        B1["POST /api/chat"]
        B2["POST /api/chat-with-audio"]
        B3["POST /api/transcribe"]
        
        B1 --> |"message: str<br/>language: str"| CS[ChatService]
        B2 --> |"message: str<br/>language: str"| CS
        B2 --> |"Generate Audio"| AS[AudioService]
        B3 --> |"audio_file: UploadFile<br/>language: str"| AS
        
        CS --> |"RAG Query"| RS[RAGService]
        CS --> |"Translation"| SS[SarvamService]
        CS --> |"Fallback"| LS[LLMService]
        
        AS --> |"TTS/STT"| SS
    end
    
    subgraph "Teaching APIs"
        C1["POST /api/start-class"]
        
        C1 --> |"course_id: str<br/>module_index: int<br/>sub_topic_index: int<br/>language: str"| TS[TeachingService]
        C1 --> |"Generate Audio"| AS
        
        TS --> |"Content Generation"| LS
    end
    
    subgraph "System APIs"
        D1["GET /health"]
        D2["GET /test-services"]
        D3["GET /websocket-info"]
        
        D1 --> |"Service Status"| SYS[System Check]
        D2 --> |"Test All Services"| SYS
        D3 --> |"WebSocket Endpoints Info"| SYS
    end
```

## 3. WebSocket Architecture

```mermaid
sequenceDiagram
    participant Client as Frontend Client
    participant WS as WebSocket Handler
    participant Chat as ChatService
    participant Audio as AudioService
    participant Teaching as TeachingService
    participant Sarvam as SarvamService
    
    Note over Client,Sarvam: WebSocket Connection Flow
    
    Client->>WS: Connect to /ws/audio-stream
    WS->>Client: connection_ready + service status
    
    Note over Client,Sarvam: Chat with Audio Flow
    
    Client->>WS: {"type": "chat_with_audio", "message": "...", "language": "..."}
    WS->>Client: {"type": "processing_started"}
    
    WS->>Chat: ask_question(query, language)
    Chat->>Chat: RAG processing / LLM fallback
    Chat->>WS: response_data
    
    WS->>Client: {"type": "text_response", "text": "...", "metadata": "..."}
    WS->>Client: {"type": "audio_stream_start"}
    
    WS->>Audio: generate_audio_from_text(text, language, ultra_fast=True)
    Audio->>Sarvam: generate_audio_ultra_fast()
    Sarvam->>Audio: audio_buffer
    Audio->>WS: audio_buffer
    
    WS->>Client: {"type": "audio_chunk", "audio_data": "base64...", "size": "..."}
    WS->>Client: {"type": "audio_stream_complete"}
    
    Note over Client,Sarvam: Start Class Flow
    
    Client->>WS: {"type": "start_class", "course_id": "...", "module_index": 0, "sub_topic_index": 0}
    WS->>Client: {"type": "class_starting"}
    
    WS->>WS: Load course content from JSON
    WS->>Client: {"type": "course_info", "module_title": "...", "sub_topic_title": "..."}
    
    WS->>Teaching: generate_teaching_content()
    Teaching->>Teaching: Create teaching prompt + LLM generation
    Teaching->>WS: teaching_content
    
    WS->>Client: {"type": "teaching_content", "content": "..."}
    WS->>Client: {"type": "audio_stream_start"}
    
    WS->>Audio: generate_audio_from_text(teaching_content)
    Audio->>Sarvam: TTS processing
    Sarvam->>Audio: audio_buffer
    Audio->>WS: audio_buffer
    
    WS->>Client: {"type": "audio_chunk", "audio_data": "..."}
    WS->>Client: {"type": "class_complete"}
```

## 4. Service Layer Architecture

```mermaid
graph TB
    subgraph "ChatService Dependencies"
        CS[ChatService]
        CS --> LLM1[LLMService]
        CS --> SARVAM1[SarvamService]
        CS --> DOC1[DocumentProcessor]
        CS --> RAG1[RAGService]
        
        RAG1 --> GROQ1[Groq API]
        RAG1 --> CHROMA1[ChromaDB]
        
        LLM1 --> OPENAI1[OpenAI API]
        SARVAM1 --> SARVAM_API1[Sarvam AI API]
        
        DOC1 --> CHROMA2[ChromaDB]
        DOC1 --> EMBED1[OpenAI Embeddings]
    end
    
    subgraph "DocumentService Dependencies"
        DS[DocumentService]
        DS --> DP[DocumentProcessor]
        DS --> CG[CourseGenerator]
        DS --> PE[PDFExtractor]
        DS --> TC[TextChunker]
        DS --> VZ[Vectorizer]
        
        CG --> OPENAI2[OpenAI API]
        CG --> CHROMA3[ChromaDB]
        
        VZ --> EMBED2[OpenAI Embeddings]
        VZ --> CHROMA4[ChromaDB]
    end
    
    subgraph "AudioService Dependencies"
        AS[AudioService]
        AS --> SARVAM2[SarvamService]
        
        SARVAM2 --> SARVAM_API2[Sarvam AI API]
        SARVAM2 --> TTS[Text-to-Speech]
        SARVAM2 --> STT[Speech-to-Text]
        SARVAM2 --> TRANS[Translation]
    end
    
    subgraph "TeachingService Dependencies"
        TS[TeachingService]
        TS --> LLM2[LLMService]
        
        LLM2 --> OPENAI3[OpenAI API]
        LLM2 --> STREAM[Streaming Support]
    end
```

## 5. Frontend to API Mapping

```mermaid
graph LR
    subgraph "index.html - Main Dashboard"
        IDX[index.html]
        IDX --> |"Load modules"| API1["GET /api/courses"]
        IDX --> |"Get course details"| API2["GET /api/course/{id}"]
        IDX --> |"Chat with audio"| API3["POST /api/chat-with-audio"]
        IDX --> |"Voice transcription"| API4["POST /api/transcribe"]
        IDX --> |"Start class"| API5["POST /api/start-class"]
        IDX --> |"Real-time audio"| WS1["WS /ws/audio-stream"]
    end
    
    subgraph "chat.html - Chat Interface"
        CHAT[chat.html]
        CHAT --> |"Text-only chat"| API6["POST /api/chat"]
        CHAT --> |"Voice transcription"| API7["POST /api/transcribe"]
    end
    
    subgraph "upload.html - PDF Upload"
        UPLOAD[upload.html]
        UPLOAD --> |"Upload PDFs"| API8["POST /api/upload-pdfs"]
    end
    
    subgraph "course.html - Course Viewer"
        COURSE[course.html]
        COURSE --> |"Get course content"| API9["GET /api/course/{id}"]
    end
    
    subgraph "courses.html - Course List"
        COURSES[courses.html]
        COURSES --> |"List all courses"| API10["GET /api/courses"]
    end
    
    subgraph "stream-test.html - WebSocket Test"
        STREAM[stream-test.html]
        STREAM --> |"Test services"| API11["GET /test-services"]
        STREAM --> |"Simple WS test"| WS2["WS /ws/test"]
        STREAM --> |"Audio streaming"| WS3["WS /ws/audio-stream"]
    end
    
    subgraph "websocket-status.html - WS Status"
        STATUS[websocket-status.html]
        STATUS --> |"WS endpoint info"| API12["GET /websocket-info"]
        STATUS --> |"Connection test"| WS4["WS /ws/test"]
        STATUS --> |"Audio WS test"| WS5["WS /ws/audio-stream"]
    end
```

## 6. Data Flow Architecture

```mermaid
flowchart TD
    subgraph "PDF Processing Flow"
        PDF1[PDF Upload] --> EXTRACT[Text Extraction]
        EXTRACT --> CHUNK[Text Chunking]
        CHUNK --> EMBED[Embedding Generation]
        EMBED --> VECTOR[Vector Storage]
        VECTOR --> COURSE_GEN[Course Generation]
        COURSE_GEN --> JSON[JSON Storage]
    end
    
    subgraph "Chat Flow"
        QUERY[User Query] --> TRANSLATE[Translation if needed]
        TRANSLATE --> RAG[RAG Retrieval]
        RAG --> VECTOR_DB[Vector Database]
        VECTOR_DB --> CONTEXT[Context Retrieval]
        CONTEXT --> LLM_PROC[LLM Processing]
        LLM_PROC --> RESPONSE[Text Response]
        RESPONSE --> TTS[Text-to-Speech]
        TTS --> AUDIO_OUT[Audio Output]
    end
    
    subgraph "Teaching Flow"
        CLASS_REQ[Class Request] --> LOAD_CONTENT[Load Course Content]
        LOAD_CONTENT --> JSON_READ[Read JSON File]
        JSON_READ --> TEACHING_PROMPT[Generate Teaching Prompt]
        TEACHING_PROMPT --> LLM_TEACH[LLM Teaching Generation]
        LLM_TEACH --> TEACHING_CONTENT[Teaching Content]
        TEACHING_CONTENT --> TTS_TEACH[Text-to-Speech]
        TTS_TEACH --> CLASS_AUDIO[Class Audio]
    end
    
    subgraph "WebSocket Flow"
        WS_CONNECT[WebSocket Connection] --> MSG_RECEIVE[Receive Message]
        MSG_RECEIVE --> MSG_ROUTE[Route by Type]
        MSG_ROUTE --> CHAT_HANDLER[Chat Handler]
        MSG_ROUTE --> CLASS_HANDLER[Class Handler]
        MSG_ROUTE --> AUDIO_HANDLER[Audio Handler]
        
        CHAT_HANDLER --> STREAM_TEXT[Stream Text Response]
        CHAT_HANDLER --> STREAM_AUDIO[Stream Audio Response]
        
        CLASS_HANDLER --> STREAM_CONTENT[Stream Teaching Content]
        CLASS_HANDLER --> STREAM_CLASS_AUDIO[Stream Class Audio]
        
        AUDIO_HANDLER --> STREAM_TTS[Stream TTS Audio]
    end
```

## 7. External API Integration

```mermaid
graph TB
    subgraph "OpenAI Integration"
        OPENAI_API[OpenAI API]
        
        LLM_SERVICE[LLMService] --> |"Chat Completions"| OPENAI_API
        LLM_SERVICE --> |"Streaming"| OPENAI_API
        
        EMBEDDINGS[Embeddings] --> |"text-embedding-3-large"| OPENAI_API
        
        COURSE_GEN[CourseGenerator] --> |"gpt-4o-mini"| OPENAI_API
        TEACHING_SVC[TeachingService] --> |"gpt-4o-mini"| OPENAI_API
    end
    
    subgraph "Sarvam AI Integration"
        SARVAM_API[Sarvam AI API]
        
        SARVAM_SVC[SarvamService] --> |"Translation"| SARVAM_API
        SARVAM_SVC --> |"Text-to-Speech"| SARVAM_API
        SARVAM_SVC --> |"Speech-to-Text"| SARVAM_API
        
        TTS_MODELS[TTS Models] --> |"bulbul:v2"| SARVAM_API
        TRANSLATE_MODELS[Translation Models] --> |"sarvam-translate:v1"| SARVAM_API
    end
    
    subgraph "Groq Integration"
        GROQ_API[Groq API]
        
        RAG_SERVICE[RAGService] --> |"llama-3.1-8b-instant"| GROQ_API
    end
    
    subgraph "ChromaDB Integration"
        CHROMA_DB[ChromaDB]
        
        VECTORIZER[Vectorizer] --> |"Store Embeddings"| CHROMA_DB
        RAG_SERVICE --> |"Retrieve Context"| CHROMA_DB
        CHAT_SERVICE[ChatService] --> |"Query Vectors"| CHROMA_DB
    end
```

## 8. Configuration and Settings

```mermaid
graph LR
    subgraph "Configuration Management"
        CONFIG[config.py]
        ENV[.env file]
        
        ENV --> |"API Keys"| CONFIG
        ENV --> |"Server Settings"| CONFIG
        
        CONFIG --> |"OPENAI_API_KEY"| OPENAI_SERVICES[OpenAI Services]
        CONFIG --> |"SARVAM_API_KEY"| SARVAM_SERVICES[Sarvam Services]
        CONFIG --> |"GROQ_API_KEY"| GROQ_SERVICES[Groq Services]
        
        CONFIG --> |"Model Names"| MODEL_CONFIG[Model Configuration]
        CONFIG --> |"File Paths"| PATH_CONFIG[Path Configuration]
        CONFIG --> |"Language Support"| LANG_CONFIG[Language Configuration]
        CONFIG --> |"Chunk Settings"| CHUNK_CONFIG[Chunking Configuration]
        
        MODEL_CONFIG --> |"LLM_MODEL_NAME: gpt-4o-mini"| LLM_SVC[LLM Service]
        MODEL_CONFIG --> |"EMBEDDING_MODEL_NAME: text-embedding-3-large"| EMBED_SVC[Embedding Service]
        
        PATH_CONFIG --> |"DOCUMENTS_DIR"| FILE_SYS[File System]
        PATH_CONFIG --> |"VECTORSTORE_DIR"| VECTOR_SYS[Vector Store]
        PATH_CONFIG --> |"COURSES_DIR"| COURSE_SYS[Course Storage]
        
        LANG_CONFIG --> |"SUPPORTED_LANGUAGES"| MULTI_LANG[Multilingual Support]
        
        CHUNK_CONFIG --> |"CHUNK_SIZE: 500"| TEXT_PROC[Text Processing]
        CHUNK_CONFIG --> |"CHUNK_OVERLAP: 100"| TEXT_PROC
    end
```

## 9. Error Handling and Logging

```mermaid
graph TB
    subgraph "Error Handling Flow"
        REQUEST[API Request] --> VALIDATION[Input Validation]
        VALIDATION --> |"Valid"| PROCESSING[Service Processing]
        VALIDATION --> |"Invalid"| ERROR1[HTTP 400 Error]
        
        PROCESSING --> |"Success"| RESPONSE[Success Response]
        PROCESSING --> |"Service Error"| ERROR2[HTTP 500 Error]
        PROCESSING --> |"Service Unavailable"| ERROR3[HTTP 503 Error]
        
        ERROR1 --> LOG1[Error Logging]
        ERROR2 --> LOG2[Error Logging]
        ERROR3 --> LOG3[Error Logging]
        
        LOG1 --> CLIENT_ERROR[Client Error Response]
        LOG2 --> SERVER_ERROR[Server Error Response]
        LOG3 --> SERVICE_ERROR[Service Error Response]
    end
    
    subgraph "WebSocket Error Handling"
        WS_MSG[WebSocket Message] --> WS_VALIDATION[Message Validation]
        WS_VALIDATION --> |"Valid"| WS_PROCESSING[Message Processing]
        WS_VALIDATION --> |"Invalid"| WS_ERROR1[Error Message]
        
        WS_PROCESSING --> |"Success"| WS_RESPONSE[Success Response]
        WS_PROCESSING --> |"Error"| WS_ERROR2[Error Message]
        
        WS_ERROR1 --> WS_LOG[WebSocket Logging]
        WS_ERROR2 --> WS_LOG
        
        WS_LOG --> WS_CLIENT[Client Error Notification]
    end
    
    subgraph "Service Health Monitoring"
        HEALTH_CHECK[Health Check] --> SERVICE_STATUS[Check Service Status]
        SERVICE_STATUS --> |"All OK"| HEALTHY[Healthy Response]
        SERVICE_STATUS --> |"Issues"| UNHEALTHY[Unhealthy Response]
        
        UNHEALTHY --> ALERT[Service Alert]
        ALERT --> RECOVERY[Recovery Actions]
    end
```

## Summary

This architecture documentation provides a comprehensive view of the ProfAI system:

1. **Overall System Architecture**: Shows the complete system with all layers and connections
2. **API Endpoint Details**: Detailed view of all REST endpoints and their service connections
3. **WebSocket Architecture**: Real-time communication flow and message handling
4. **Service Layer Architecture**: Internal service dependencies and connections
5. **Frontend to API Mapping**: How each frontend component connects to backend APIs
6. **Data Flow Architecture**: How data moves through the system for different operations
7. **External API Integration**: Third-party service integrations (OpenAI, Sarvam AI, Groq)
8. **Configuration Management**: How settings and configurations are managed
9. **Error Handling and Logging**: Error handling patterns and logging strategies

The system follows a clean layered architecture with clear separation of concerns:
- **Frontend Layer**: Multiple HTML interfaces for different use cases
- **API Layer**: FastAPI with both REST and WebSocket endpoints
- **Service Layer**: Business logic services with specific responsibilities
- **Core Layer**: Course generation and vectorization logic
- **Processor Layer**: Document and text processing utilities
- **External APIs**: Third-party AI service integrations
- **Data Storage**: Vector database and file system storage

This architecture supports both traditional request-response patterns and real-time streaming for optimal user experience.