# 🤖 Complete LLM Usage Map - ProfAI Application

**Analysis Date:** January 6, 2026  
**Traced From:** `app_celery.py` → All Services

---

## 📊 **LLM Usage Summary**

### **Total LLM Call Points:** 15+
### **LLM Services Used:**
- OpenAI GPT-4o (primary)
- OpenAI Whisper (audio transcription)

### **Usage Breakdown by Function:**
1. **Course Generation** - 2 LLM calls (curriculum + content)
2. **Quiz Generation** - 2-3 LLM calls per quiz
3. **Chat/RAG** - 1-2 LLM calls per query
4. **Teaching Content** - 1 LLM call per topic
5. **Translation** - 1 LLM call when needed
6. **Audio Transcription** - 1 Whisper API call

---

## 🗺️ **API Endpoint → LLM Call Mapping**

### **1. `/api/upload-pdfs` (Course Generation)**

**Flow:**
```
POST /api/upload-pdfs
  → Celery Task: process_pdf_and_generate_course
    → DocumentService.process_uploaded_pdfs()
      → CourseGenerator.generate_course()
        → LLM CALL #1: _generate_curriculum()
          📍 Location: core/course_generator.py:111
          🤖 Model: ChatOpenAI (CURRICULUM_GENERATION_MODEL)
          🎯 Purpose: Generate course structure with modules
          📝 Input: Full PDF context (up to 200K chars)
          📤 Output: JSON course structure (CourseLMS)
          ⚙️ Temperature: 0.2
          
        → LLM CALL #2: _generate_content() [per sub-topic]
          📍 Location: core/course_generator.py:189
          🤖 Model: ChatOpenAI (CONTENT_GENERATION_MODEL)
          🎯 Purpose: Generate detailed lecture content for each topic
          📝 Input: Retrieved context from RAG + topic name
          📤 Output: Detailed content string
          ⚙️ Temperature: 0.5
          🔁 Iterations: N topics (typically 30-50+ calls)
```

**Total LLM Calls:** 1 + N (where N = number of sub-topics, typically 30-50)

---

### **2. `/api/quiz/generate-module` (Module Quiz)**

**Flow:**
```
POST /api/quiz/generate-module
  → QuizService.generate_module_quiz()
    → LLM CALL #1: Generate 20 questions
      📍 Location: services/quiz_service.py:62
      🤖 Model: LLMService → OpenAI (LLM_MODEL_NAME)
      🎯 Purpose: Generate 20 MCQ questions for module
      📝 Input: Module content + quiz prompt
      📤 Output: 20 questions in structured format
      ⚙️ Temperature: 1.0
      
    → LLM CALL #2 (if needed): Generate additional questions
      📍 Location: services/quiz_service.py:71
      🤖 Model: LLMService → OpenAI (LLM_MODEL_NAME)
      🎯 Purpose: Fill gap if <20 questions generated
      📝 Input: Module content + additional questions prompt
      📤 Output: Additional questions
      ⚙️ Temperature: 1.0
```

**Total LLM Calls:** 1-2 per module quiz

---

### **3. `/api/quiz/generate-course` (Course Quiz)**

**Flow:**
```
POST /api/quiz/generate-course
  → QuizService.generate_course_quiz()
    → LLM CALL #1: Generate first 20 questions
      📍 Location: services/quiz_service.py:111
      🤖 Model: LLMService → OpenAI (LLM_MODEL_NAME)
      🎯 Purpose: Generate part 1 of 40 questions
      📝 Input: Full course content + part 1 prompt
      📤 Output: 20 questions
      ⚙️ Temperature: 1.0
      
    → LLM CALL #2: Generate second 20 questions
      📍 Location: services/quiz_service.py:118
      🤖 Model: LLMService → OpenAI (LLM_MODEL_NAME)
      🎯 Purpose: Generate part 2 of 40 questions
      📝 Input: Full course content + part 2 prompt
      📤 Output: 20 questions
      ⚙️ Temperature: 1.0
```

**Total LLM Calls:** 2 per course quiz (always)

---

### **4. `/api/chat` (Text Chat)**

**Flow:**
```
POST /api/chat
  → ChatService.ask_question()
    → Path A: RAG Active
      → RAGService.get_answer()
        → LLM CALL #1: RAG with OpenAI
          📍 Location: services/rag_service.py:96
          🤖 Model: ChatOpenAI (LLM_MODEL_NAME)
          🎯 Purpose: Answer using RAG context
          📝 Input: Question + retrieved docs + conversation history
          📤 Output: Answer based on course content
          ⚙️ Temperature: 1.0
          
      → If garbage detected or "cannot find answer":
        → LLM CALL #2: Fallback to general knowledge
          📍 Location: services/chat_service.py:205, 220
          🤖 Model: LLMService → OpenAI (LLM_MODEL_NAME)
          🎯 Purpose: General knowledge response
          📝 Input: Query + conversation context
          📤 Output: General answer
          ⚙️ Temperature: 1.0
    
    → Path B: RAG Inactive (or fallback)
      → LLM CALL: General knowledge only
        📍 Location: services/chat_service.py:236
        🤖 Model: LLMService.get_general_response()
        🎯 Purpose: Answer without RAG
        📝 Input: Query + conversation history
        📤 Output: General answer
        ⚙️ Temperature: 1.0
```

**Total LLM Calls:** 1-2 per chat message (1 for RAG success, 2 for RAG failure)

---

### **5. `/api/chat-with-audio` (Chat + Audio)**

**Flow:**
```
POST /api/chat-with-audio
  → ChatService.ask_question() [same as above]
    → 1-2 LLM calls (same as /api/chat)
  → AudioService.generate_audio_from_text()
    → NO LLM CALL (uses Sarvam AI or ElevenLabs TTS)
```

**Total LLM Calls:** 1-2 per request (same as chat)

---

### **6. `/api/transcribe` (Audio Transcription)**

**Flow:**
```
POST /api/transcribe
  → AudioService.transcribe_audio()
    → WHISPER API CALL
      📍 Location: services/transcription_service.py:73
      🤖 Model: OpenAI Whisper (whisper-1)
      🎯 Purpose: Transcribe audio to text
      📝 Input: Audio file (webm/wav)
      📤 Output: Transcribed text
      ⚙️ Settings: Default
```

**Total LLM Calls:** 1 Whisper call per audio file

---

### **7. `/api/start-class` (Teaching Content + Audio)**

**Flow:**
```
POST /api/start-class
  → TeachingService.generate_teaching_content()
    → LLM CALL: Generate teaching content
      📍 Location: services/teaching_service.py:88
      🤖 Model: LLMService → OpenAI (LLM_MODEL_NAME)
      🎯 Purpose: Convert course content to teaching format
      📝 Input: Module title + topic + raw content
      📤 Output: Teaching-friendly content
      ⚙️ Temperature: 1.0
      ⏱️ Timeout: 60 seconds (updated)
      
  → AudioService.generate_audio_from_text()
    → NO LLM CALL (uses TTS service)
```

**Total LLM Calls:** 1 per teaching session

---

## 📋 **Detailed Service Breakdown**

### **services/llm_service.py** (Core LLM Service)

**Purpose:** Central OpenAI API wrapper  
**LLM Provider:** OpenAI  
**Model:** `config.LLM_MODEL_NAME` (default: gpt-4o)

#### **Methods:**

1. **`get_general_response(query, target_language, conversation_context)`**
   - **Line:** 19-78
   - **Purpose:** General knowledge responses with conversation context
   - **Temperature:** 1.0
   - **Features:** Content safety, TTS pronunciation rules, teaching style
   - **Used By:** ChatService (fallback)

2. **`translate_text(text, target_language)`**
   - **Line:** 80-102
   - **Purpose:** Translate text to target language
   - **Temperature:** 0.0 (deterministic)
   - **Used By:** ChatService (multilingual support)

3. **`generate_response(prompt, temperature)`**
   - **Line:** 104-119
   - **Purpose:** Generic prompt → response
   - **Temperature:** Configurable (default 0.7)
   - **Used By:** QuizService, TeachingService

4. **`generate_response_stream(prompt, temperature)`**
   - **Line:** 121-141
   - **Purpose:** Streaming response generation
   - **Temperature:** Configurable (default 0.7)
   - **Used By:** TeachingService (streaming mode)

---

### **services/rag_service.py** (RAG with LangChain)

**Purpose:** Retrieval-Augmented Generation for course content  
**LLM Provider:** OpenAI via LangChain  
**Model:** `config.LLM_MODEL_NAME`

#### **LLM Usage:**

1. **`ChatOpenAI` initialization**
   - **Line:** 43-47
   - **Purpose:** RAG chain LLM
   - **Temperature:** 1.0
   - **Integration:** LangChain LCEL chain

2. **`rag_chain` execution**
   - **Line:** 88-98
   - **Purpose:** Question → Context → Answer pipeline
   - **Input:** Question + conversation history + response language
   - **Output:** Contextualized answer
   - **Features:** Hybrid retrieval (Vector + BM25 + Flashrank reranking)

---

### **services/quiz_service.py** (Quiz Generation)

**Purpose:** MCQ quiz generation and evaluation  
**LLM Provider:** OpenAI via LLMService  
**Model:** `config.LLM_MODEL_NAME`

#### **LLM Calls:**

1. **Module Quiz Generation** (Line 62)
   - **Input:** Module content + structured prompt
   - **Output:** 20 MCQ questions
   - **Temperature:** 1.0
   - **Retry Logic:** Generates additional if <20 questions

2. **Course Quiz Generation** (Lines 111, 118)
   - **Part 1:** First 20 questions
   - **Part 2:** Second 20 questions
   - **Temperature:** 1.0
   - **Total:** Always 2 LLM calls for 40 questions

---

### **services/teaching_service.py** (Teaching Content)

**Purpose:** Convert raw content to teaching-friendly format  
**LLM Provider:** OpenAI via LLMService  
**Model:** `config.LLM_MODEL_NAME`

#### **LLM Calls:**

1. **Teaching Content Generation** (Line 88)
   - **Input:** Module + topic + raw content
   - **Output:** Engaging teaching content
   - **Temperature:** 1.0
   - **Timeout:** 60 seconds (updated from 5s)
   - **Features:** TTS-optimized, pronunciation fixes

2. **Streaming Mode** (Line 44) - Currently unused
   - **Purpose:** Real-time content generation
   - **Method:** `generate_response_stream()`

---

### **services/chat_service.py** (Chat Orchestrator)

**Purpose:** Coordinates RAG, translation, and LLM services  
**LLM Provider:** Uses RAGService + LLMService

#### **LLM Flow:**

1. **Primary Path:** RAGService (1 LLM call)
2. **Fallback Path:** LLMService.get_general_response() (1 LLM call)
3. **Total:** 1-2 LLM calls per chat message

**Fallback Triggers:**
- Garbage response detection (repeated characters)
- "I cannot find the answer" in RAG response
- RAG service error

---

### **core/course_generator.py** (Course Creation)

**Purpose:** Generate course curriculum and content from PDFs  
**LLM Provider:** OpenAI via LangChain  
**Models:** 
- Curriculum: `config.CURRICULUM_GENERATION_MODEL`
- Content: `config.CONTENT_GENERATION_MODEL`

#### **LLM Calls:**

1. **Curriculum Generation** (Line 111)
   - **Model:** ChatOpenAI (curriculum model)
   - **Temperature:** 0.2 (structured output)
   - **Input:** Full PDF context (max 200K chars)
   - **Output:** JSON course structure
   - **Count:** 1 call per course

2. **Content Generation** (Line 189)
   - **Model:** ChatOpenAI (content model)
   - **Temperature:** 0.5
   - **Input:** Retrieved context + topic
   - **Output:** Detailed lecture content
   - **Count:** N calls (1 per sub-topic, typically 30-50)

---

### **services/transcription_service.py** (Audio Transcription)

**Purpose:** Audio to text using Whisper  
**LLM Provider:** OpenAI Whisper API

#### **Whisper Usage:**

1. **Audio Transcription** (Line 73)
   - **Model:** whisper-1
   - **Input:** Audio file (wav format)
   - **Output:** Transcribed text
   - **Language:** Configurable
   - **Used By:** AudioService

---

## 💰 **Cost Analysis**

### **Estimated Token Usage per Operation**

| Operation | Input Tokens | Output Tokens | LLM Calls | Cost Estimate |
|-----------|--------------|---------------|-----------|---------------|
| **Course Generation** | 50K-200K | 20K-100K | 30-50 | $15-50 |
| **Module Quiz (20Q)** | 5K-10K | 3K-5K | 1-2 | $0.10-0.30 |
| **Course Quiz (40Q)** | 10K-20K | 6K-10K | 2 | $0.30-0.60 |
| **Chat (RAG)** | 2K-5K | 300-800 | 1 | $0.01-0.03 |
| **Chat (Fallback)** | 2K-5K | 300-800 | 2 | $0.02-0.06 |
| **Teaching Content** | 3K-8K | 500-1K | 1 | $0.02-0.05 |
| **Audio Transcription** | N/A | N/A | 1 | $0.006/min |

**Note:** Costs based on GPT-4o pricing (input: $2.50/1M tokens, output: $10/1M tokens)

---

## 🔧 **LLM Configuration**

### **Environment Variables**

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Model Selection
LLM_MODEL_NAME=gpt-4o                    # Chat, Quiz, Teaching
CURRICULUM_GENERATION_MODEL=gpt-4o       # Course curriculum
CONTENT_GENERATION_MODEL=gpt-4o          # Course content
EMBEDDING_MODEL_NAME=text-embedding-3-small  # Vector embeddings
```

### **Config Settings** (`config.py`)

```python
# LLM Settings
LLM_MODEL_NAME = "gpt-4o"
CURRICULUM_GENERATION_MODEL = "gpt-4o"
CONTENT_GENERATION_MODEL = "gpt-4o"
EMBEDDING_MODEL_NAME = "text-embedding-3-small"

# Timeouts
LLM_TIMEOUT = 60.0  # seconds

# Temperature Settings
# - 0.0-0.3: Structured/deterministic (curriculum, translation)
# - 0.5-0.7: Balanced (content generation)
# - 1.0: Creative (quiz, chat, teaching)
```

---

## 🎯 **Optimization Opportunities**

### **1. Reduce Course Generation Calls**
**Current:** 1 + N calls (N = sub-topics)  
**Optimization:** Batch content generation  
**Impact:** 50% reduction in calls, 30% cost savings

### **2. Implement Response Caching**
**Target:** RAG responses, teaching content  
**Method:** Redis cache with 5-minute TTL  
**Impact:** 40% reduction in duplicate queries

### **3. Use Streaming for Real-Time Feedback**
**Target:** Chat, teaching content  
**Method:** `generate_response_stream()`  
**Impact:** Better UX, same cost

### **4. Smart Temperature Selection**
**Current:** Mix of 0.0, 0.2, 0.5, 1.0  
**Optimization:** Fine-tune per use case  
**Impact:** Better output quality

### **5. Token Limit Management**
**Current:** Some prompts may exceed limits  
**Optimization:** Dynamic truncation with smart summarization  
**Impact:** Prevent errors, optimize costs

---

## 📝 **Usage Patterns Summary**

### **High-Frequency Calls**
1. **Chat/RAG:** Every user message (1-2 calls)
2. **Teaching Content:** Per class session (1 call)

### **Medium-Frequency Calls**
1. **Quiz Generation:** Per quiz request (1-2 calls)
2. **Audio Transcription:** Per voice input (1 call)

### **Low-Frequency Calls**
1. **Course Generation:** Per PDF upload (30-50 calls)

---

## 🚨 **Critical Dependencies**

### **Services Requiring LLM**
- ✅ Chat (RAG or fallback required)
- ✅ Quiz Generation (requires LLM)
- ✅ Teaching Content (requires LLM)
- ✅ Course Generation (requires LLM)
- ⚠️ Audio Transcription (Whisper API)

### **Fallback Behavior**
- **Chat:** Falls back to general LLM if RAG fails
- **Quiz:** No fallback (returns error)
- **Teaching:** Returns simple content if LLM fails
- **Course Generation:** No fallback (returns error)

---

## 📊 **Performance Metrics**

### **Average Response Times** (with optimizations)

| Service | Before | After | Improvement |
|---------|--------|-------|-------------|
| RAG Chat | 25-40s | 15-25s | **40%** |
| Quiz Generation | 15-25s | 15-25s | - |
| Teaching Content | 8-12s | 8-12s | - |
| Course Generation | 10-20 min | 10-20 min | - |

**Note:** Recent optimizations (Flashrank reranking) reduced RAG response time significantly.

---

## 🔐 **Security Considerations**

### **API Key Management**
- ✅ Stored in environment variables
- ✅ Never exposed in logs
- ✅ Separate keys for production/dev

### **Content Safety**
- ✅ Input validation in LLMService.get_general_response()
- ✅ Blocks explicit, harmful, or discriminatory content
- ⚠️ No content filtering in other LLM calls (quiz, teaching)

### **Rate Limiting**
- ⚠️ No built-in rate limiting
- **Recommendation:** Add rate limiting per user/IP

---

## 📚 **Next Steps for User-Centered Features**

### **Recommended DB Schema Changes**
1. **User Sessions Table**
   - Track conversation history
   - Store session preferences
   - Link to courses and quizzes

2. **User Progress Table**
   - Track completed modules
   - Store quiz scores
   - Calculate progress percentages

3. **LLM Usage Analytics**
   - Log all LLM calls
   - Track tokens and costs per user
   - Monitor response times

### **New APIs to Consider**
1. **User Profile Management**
2. **Progress Tracking**
3. **Personalized Recommendations** (requires LLM)
4. **Study Plan Generation** (requires LLM)
5. **Adaptive Quiz Difficulty** (requires LLM)

---

**End of LLM Usage Map**
