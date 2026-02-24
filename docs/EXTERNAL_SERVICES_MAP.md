# 🌐 Complete External Services & Models Map

**Analysis Date:** January 6, 2026  
**Traced From:** `config.py` + All Service Files

---

## ⚠️ **CRITICAL: MODEL CONFIGURATION ERROR DETECTED**

### **Current Config (config.py:68-71):**

```python
LLM_MODEL_NAME = "gpt-5-mini"                    # ❌ DOES NOT EXIST!
CURRICULUM_GENERATION_MODEL = "gpt-5"            # ❌ DOES NOT EXIST!
CONTENT_GENERATION_MODEL = "gpt-5"               # ❌ DOES NOT EXIST!
EMBEDDING_MODEL_NAME = "text-embedding-3-large"  # ✅ Valid
```

### **🚨 PROBLEM:**
**"gpt-5-mini" and "gpt-5" are NOT valid OpenAI models!**

These models don't exist yet. You're likely getting errors or falling back to default models.

### **✅ CORRECT Configuration Should Be:**

```python
LLM_MODEL_NAME = "gpt-4o-mini"                   # ✅ Fast, cheap ($0.15/1M input)
# OR
LLM_MODEL_NAME = "gpt-4o"                        # ✅ More capable ($2.50/1M input)

CURRICULUM_GENERATION_MODEL = "gpt-4o"           # ✅ For structured output
CONTENT_GENERATION_MODEL = "gpt-4o"              # ✅ For content generation
EMBEDDING_MODEL_NAME = "text-embedding-3-large"  # ✅ Already correct
```

---

## 📊 **All External Services/APIs You're Using**

### **1. OpenAI APIs** 🤖

**Provider:** OpenAI  
**API Key:** `OPENAI_API_KEY`

#### **Services Used:**

| Service | Model | Usage | Location |
|---------|-------|-------|----------|
| **Chat Completion** | `gpt-5-mini` ❌ (should be `gpt-4o-mini`) | General chat, RAG, Quiz, Teaching | `services/llm_service.py:70` |
| **Chat Completion** | `gpt-5` ❌ (should be `gpt-4o`) | Course curriculum generation | `core/course_generator.py:19` |
| **Chat Completion** | `gpt-5` ❌ (should be `gpt-4o`) | Course content generation | `core/course_generator.py:24` |
| **Embeddings** | `text-embedding-3-large` ✅ | Vector embeddings for RAG | `services/document_service.py:551` |
| **Whisper API** | `whisper-1` ✅ | Audio transcription (file-based) | `services/transcription_service.py:73` |

**Cost Structure:**
- `gpt-4o-mini`: $0.15/1M input, $0.60/1M output
- `gpt-4o`: $2.50/1M input, $10/1M output
- `text-embedding-3-large`: $0.13/1M tokens
- `whisper-1`: $0.006/minute

---

### **2. ElevenLabs (Text-to-Speech)** 🔊

**Provider:** ElevenLabs  
**API Key:** `ELEVENLABS_API_KEY`  
**Status:** ✅ **PRIMARY TTS PROVIDER**

#### **Configuration (`config.py:97-104`):**

```python
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Voice: Rachel (default)
ELEVENLABS_MODEL = "eleven_flash_v2_5"        # Fast, low-latency model
AUDIO_TTS_PROVIDER = "elevenlabs"             # Primary provider
```

#### **Where It's Used:**

| Feature | File | Line | Purpose |
|---------|------|------|---------|
| **TTS Service** | `services/elevenlabs_service.py` | 20-44 | Core TTS implementation |
| **Audio Generation** | `services/audio_service.py` | 40-53 | Primary TTS provider |
| **WebSocket Streaming** | `services/elevenlabs_service.py` | 42-116 | Real-time audio streaming |
| **REST TTS Fallback** | `services/elevenlabs_service.py` | 118-175 | Non-streaming TTS |

#### **Features:**
- ✅ WebSocket streaming for real-time audio
- ✅ Ultra-low latency (11-flash v2.5 model)
- ✅ High-quality voice synthesis
- ✅ Automatic fallback to Sarvam if API key missing

#### **Endpoints:**
- WebSocket: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/multi-stream-input`
- REST: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream`

---

### **3. Sarvam AI (Indian Languages)** 🇮🇳

**Provider:** Sarvam AI  
**API Key:** `SARVAM_API_KEY`  
**Status:** ✅ **FALLBACK TTS/STT + PRIMARY TRANSLATION**

#### **Configuration (`config.py:94`):**

```python
SARVAM_TTS_SPEAKER = "anushka"  # Female Indian voice
```

#### **Where It's Used:**

| Feature | File | Purpose |
|---------|------|---------|
| **Translation Service** | `services/sarvam_service.py:60-102` | Translate to/from Indian languages |
| **TTS Fallback** | `services/sarvam_service.py:104-127` | Text-to-speech (fallback if ElevenLabs fails) |
| **STT Fallback** | `services/transcription_service.py:110-131` | Speech-to-text (not fully implemented) |
| **Chat Translation** | `services/chat_service.py:19` | Used by ChatService for multilingual support |
| **Audio Service** | `services/audio_service.py:23` | Always initialized as fallback |

#### **Features:**
- ✅ Indian language translation (11 languages)
- ✅ TTS with Indian accents
- ✅ Fallback provider for reliability
- ⚠️ STT not fully implemented

#### **Supported Languages:**
- English, Hindi, Bengali, Marathi, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, Urdu

---

### **4. Deepgram (Speech-to-Text)** 🎤

**Provider:** Deepgram  
**API Key:** `DEEPGRAM_API_KEY`  
**Status:** ✅ **PRIMARY STT PROVIDER (Streaming)**

#### **Configuration (`config.py:102`):**

```python
AUDIO_STT_PROVIDER = "deepgram"  # Primary STT provider
```

#### **Where It's Used:**

| Feature | File | Purpose |
|---------|------|---------|
| **Real-time STT** | `services/deepgram_stt_service.py` | Streaming speech recognition |
| **Audio Service** | `services/audio_service.py:25-38` | Primary STT initialization |
| **WebSocket Streaming** | `services/deepgram_stt_service.py:44-100` | Real-time audio processing |

#### **Features:**
- ✅ WebSocket streaming (ultra-low latency)
- ✅ Built-in Voice Activity Detection (VAD)
- ✅ Deepgram Nova-3 model
- ✅ Automatic fallback to Sarvam if missing

#### **Endpoints:**
- WebSocket: `wss://api.deepgram.com/v2/listen`

#### **Note:**
- Deepgram is for **real-time streaming** only
- File-based transcription still uses **OpenAI Whisper** (more accurate)
- See: `services/audio_service.py:72-77`

---

### **5. ChromaDB Cloud (Vector Database)** 📊

**Provider:** ChromaDB Cloud  
**API Key:** `CHROMA_CLOUD_API_KEY`  
**Status:** ✅ **PRIMARY VECTOR STORE** (if USE_CHROMA_CLOUD=True)

#### **Configuration (`config.py:27-36`):**

```python
USE_CHROMA_CLOUD = True  # Toggle for cloud vs local
CHROMA_COLLECTION_NAME = "profai_documents"
CHROMA_CLOUD_TENANT = os.getenv("CHROMA_CLOUD_TENANT")
CHROMA_CLOUD_DATABASE = os.getenv("CHROMA_CLOUD_DATABASE")
```

#### **Where It's Used:**

| Feature | File | Purpose |
|---------|------|---------|
| **Vector Store** | `services/rag_service.py:21-24` | Primary vector storage for RAG |
| **Cloud Vectorizer** | `core/cloud_vectorizer.py` | ChromaDB Cloud client wrapper |
| **Document Upload** | `services/document_service.py:112-115` | Store document embeddings |
| **Course Generation** | `services/document_service.py:249-252` | Vector store for content |
| **BM25 Loading** | `services/rag_service.py:148-163` | Load docs from ChromaDB for hybrid search |

#### **Features:**
- ✅ Cloud-hosted vector database
- ✅ Automatic scaling
- ✅ No local storage issues
- ✅ Fallback to local FAISS if disabled

#### **Local Fallback:**
- If `USE_CHROMA_CLOUD=False`, uses local FAISS store
- Path: `data/vectorstore/faiss`

---

### **6. Redis Labs Cloud (Message Broker)** 🔄

**Provider:** Redis Labs Cloud  
**URL:** `REDIS_URL`  
**Status:** ✅ **CELERY MESSAGE BROKER**

#### **Configuration (`config.py:38-49`):**

```python
REDIS_URL = os.getenv("REDIS_URL")  # Format: rediss://user:pass@host:port/db
REDIS_HOST = "redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com"
REDIS_PORT = "10925"
REDIS_USERNAME = "default"
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_USE_SSL = True
```

#### **Where It's Used:**

| Feature | File | Purpose |
|---------|------|---------|
| **Celery Broker** | `celery_app.py:19-24` | Task queue message broker |
| **Task Distribution** | `tasks/pdf_processing.py` | Distribute PDF processing tasks |
| **Worker Communication** | `worker.py` | Worker-to-broker connection |

#### **Features:**
- ✅ Distributed task queue
- ✅ SSL/TLS encryption
- ✅ High availability
- ✅ Used by Celery for async processing

#### **Queues:**
- `pdf_processing` - PDF upload and course generation
- `quiz_generation` - Quiz creation (if enabled)

---

### **7. Neon PostgreSQL (Database)** 🗄️

**Provider:** Neon  
**URL:** `DATABASE_URL`  
**Status:** ⚠️ **OPTIONAL** (if USE_DATABASE=True)

#### **Configuration (`config.py:61-65`):**

```python
USE_DATABASE = False  # Toggle database vs JSON files
DATABASE_URL = os.getenv("DATABASE_URL")
# Format: postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/profai?sslmode=require
```

#### **Where It's Used:**

| Feature | File | Purpose |
|---------|------|---------|
| **Database Service** | `services/database_service_actual.py` | Main DB operations |
| **Course Storage** | `services/database_service_actual.py:251-301` | Store/retrieve courses |
| **Quiz Storage** | `services/database_service_actual.py:376-438` | Store/retrieve quizzes |
| **User Sessions** | `services/database_service_actual.py:440-524` | Conversation history |
| **App Initialization** | `app_celery.py:79-87` | Database service init |

#### **Tables:**
- `courses` - Course content and metadata
- `modules` - Course modules/weeks
- `topics` - Module topics/subtopics
- `quizzes` - Quiz data
- `quiz_questions` - Quiz questions
- `user_sessions` - Conversation sessions
- `session_messages` - Chat history

#### **Fallback:**
- If `USE_DATABASE=False`, uses JSON files in `data/courses/`

---

## 📋 **Service Priority & Fallback Chain**

### **Text-to-Speech (TTS):**
```
1️⃣ ElevenLabs (Primary) ✅
   ↓ (if fails)
2️⃣ Sarvam AI (Fallback) ✅
```

### **Speech-to-Text (STT):**

**File Transcription:**
```
1️⃣ OpenAI Whisper (Primary) ✅
   ↓ (if fails)
2️⃣ Sarvam AI (Fallback) ⚠️ (not implemented)
   ↓ (if fails)
3️⃣ Google Speech Recognition (Last resort)
```

**Real-time Streaming:**
```
1️⃣ Deepgram (Primary) ✅
   ↓ (if fails)
2️⃣ Sarvam AI (Fallback) ⚠️
```

### **Translation:**
```
1️⃣ Sarvam AI (Primary for Indian languages) ✅
```

### **Vector Storage:**
```
1️⃣ ChromaDB Cloud (if USE_CHROMA_CLOUD=True) ✅
   ↓ (if disabled)
2️⃣ Local FAISS (Fallback)
```

### **Course Storage:**
```
1️⃣ Neon PostgreSQL (if USE_DATABASE=True) ⚠️
   ↓ (if disabled)
2️⃣ JSON Files (Fallback) ✅
```

---

## 💰 **Monthly Cost Estimates**

### **Assuming Moderate Usage:**
- 1,000 chat messages/day
- 100 teaching sessions/day
- 10 course generations/day
- 50 quiz generations/day

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| **OpenAI (LLM)** | $150-300 | Depends on gpt-4o vs gpt-4o-mini |
| **OpenAI (Embeddings)** | $10-20 | text-embedding-3-large |
| **OpenAI (Whisper)** | $5-15 | Audio transcription |
| **ElevenLabs** | $50-100 | TTS generation |
| **Sarvam AI** | $20-50 | Translation + fallback TTS |
| **Deepgram** | $30-60 | Real-time STT |
| **ChromaDB Cloud** | $0-20 | Free tier available |
| **Redis Labs** | $0-10 | Free tier available |
| **Neon PostgreSQL** | $0-20 | Free tier available |
| **Total** | **$265-595/month** | Mid-range estimate |

---

## 🔧 **Required Environment Variables**

### **Critical (Required):**
```bash
OPENAI_API_KEY=sk-...
```

### **Audio Services:**
```bash
ELEVENLABS_API_KEY=...        # Primary TTS
DEEPGRAM_API_KEY=...          # Primary STT (streaming)
SARVAM_API_KEY=...            # Fallback + Translation
```

### **Storage:**
```bash
# Vector Store
USE_CHROMA_CLOUD=True
CHROMA_CLOUD_API_KEY=...
CHROMA_CLOUD_TENANT=...
CHROMA_CLOUD_DATABASE=...

# Database
USE_DATABASE=False
DATABASE_URL=postgresql://...
```

### **Task Queue:**
```bash
REDIS_URL=rediss://default:PASSWORD@redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10925
```

---

## 🚨 **IMMEDIATE ACTIONS NEEDED**

### **1. Fix Model Names in config.py:**

**BEFORE (WRONG):**
```python
LLM_MODEL_NAME = "gpt-5-mini"
CURRICULUM_GENERATION_MODEL = "gpt-5"
CONTENT_GENERATION_MODEL = "gpt-5"
```

**AFTER (CORRECT):**
```python
LLM_MODEL_NAME = "gpt-4o-mini"  # or "gpt-4o"
CURRICULUM_GENERATION_MODEL = "gpt-4o"
CONTENT_GENERATION_MODEL = "gpt-4o"
```

### **2. Test Configuration:**
```bash
cd Prof_AI

# Test all services
python verify_all_services.py

# Check environment
python test_env.py
```

### **3. Update .env File:**
Ensure all API keys are present:
```bash
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
DEEPGRAM_API_KEY=...
SARVAM_API_KEY=...
CHROMA_CLOUD_API_KEY=...
REDIS_URL=rediss://...
```

---

## 📊 **Service Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────┐
│                      ProfAI Application                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┴─────────────────────┐
        ↓                                           ↓
┌───────────────┐                          ┌───────────────┐
│   FastAPI     │                          │   WebSocket   │
│   (REST API)  │                          │    Server     │
└───────┬───────┘                          └───────┬───────┘
        │                                           │
        └───────────────────┬───────────────────────┘
                            ↓
        ┌──────────────────────────────────────────┐
        │         Service Layer                     │
        │  • ChatService                            │
        │  • RAGService                             │
        │  • QuizService                            │
        │  • TeachingService                        │
        │  • AudioService                           │
        └─────────────────┬────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │        External Services          │
        └───────────────────────────────────┘
                          ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   OpenAI     │  ElevenLabs  │   Sarvam     │  Deepgram    │
│  • gpt-4o    │  • TTS       │  • TTS       │  • STT       │
│  • Whisper   │  • Streaming │  • Translate │  • Streaming │
│  • Embeddings│              │              │              │
└──────────────┴──────────────┴──────────────┴──────────────┘
                          ↓
┌──────────────┬──────────────┬──────────────┬──────────────┐
│  ChromaDB    │    Redis     │     Neon     │   Celery     │
│  • Vectors   │  • Broker    │  • Postgres  │  • Tasks     │
│  • Cloud     │  • Cache     │  • Database  │  • Workers   │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

---

## 📝 **Summary**

### **You're Currently Using:**

1. **OpenAI** - LLM (WRONG MODEL NAMES!), Embeddings, Whisper
2. **ElevenLabs** - Primary TTS (high quality)
3. **Sarvam AI** - Translation + Fallback TTS
4. **Deepgram** - Primary STT (streaming)
5. **ChromaDB Cloud** - Vector storage
6. **Redis Labs Cloud** - Celery message broker
7. **Neon PostgreSQL** - Database (optional)

### **Total External Services:** 7 providers + 12+ API endpoints

### **Critical Issue:** ⚠️ **Fix model names immediately!**
- Change `gpt-5-mini` → `gpt-4o-mini`
- Change `gpt-5` → `gpt-4o`

---

**End of External Services Map**
