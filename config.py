# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHROMA_CLOUD_API_KEY = os.getenv("CHROMA_CLOUD_API_KEY")

# --- Audio Provider API Keys ---
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")  # Optional fallback

# --- Project Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DOCUMENTS_DIR = os.path.join(DATA_DIR, "documents")
VECTORSTORE_DIR = os.path.join(DATA_DIR, "vectorstore")
COURSES_DIR = os.path.join(DATA_DIR, "courses")

# --- Database Settings ---
# Toggle between local FAISS and ChromaDB Cloud
USE_CHROMA_CLOUD = os.getenv("USE_CHROMA_CLOUD", "True").lower() == 'true'

# Local Vectorstore paths
CHROMA_DB_PATH = os.path.join(VECTORSTORE_DIR, "chroma")
FAISS_DB_PATH = os.path.join(VECTORSTORE_DIR, "faiss")

# ChromaDB Cloud Settings (for vector storage)
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "profai_documents")
CHROMA_CLOUD_TENANT = os.getenv("CHROMA_CLOUD_TENANT")
CHROMA_CLOUD_DATABASE = os.getenv("CHROMA_CLOUD_DATABASE")

# --- Redis Settings (Celery Message Broker) ---
# For Redis Labs Cloud (recommended):
# REDIS_URL=rediss://default:PASSWORD@redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10925
REDIS_URL = os.getenv("REDIS_URL", None)

# Fallback to individual components if REDIS_URL not provided
REDIS_HOST = os.getenv("REDIS_HOST", "redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com")
REDIS_PORT = os.getenv("REDIS_PORT", "10925")
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_USE_SSL = os.getenv("REDIS_USE_SSL", "true").lower() == 'true'

# --- PostgreSQL Database Settings (Neon) ---
# Enable when ready to use Neon PostgreSQL instead of JSON files
# Instructions:
# 1. Create account at https://neon.tech
# 2. Create project and database
# 3. Copy connection string
# 4. Add to .env: DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
# 5. Set USE_DATABASE=True in .env
# 6. Run migration: python migrate_json_to_db.py

USE_DATABASE = os.getenv("USE_DATABASE", "False").lower() == 'true'
DATABASE_URL = os.getenv("DATABASE_URL", None)

# Example DATABASE_URL format:
# postgresql://username:password@ep-xxx-xxx.us-east-2.aws.neon.tech/profai?sslmode=require

# --- LLM & RAG Settings ---
# General chat uses GPT-4o-mini, RAG uses Groq for speed
LLM_MODEL_NAME = "gpt-4o-mini"  # For general chat and fallback
RAG_MODEL_NAME = "llama-3.1-8b-instant"  # Groq model for RAG (fast, low latency) - updated from deprecated llama3-8b-8192
EMBEDDING_MODEL_NAME = "text-embedding-3-large"  # 1536 dimensions
CURRICULUM_GENERATION_MODEL = "gpt-4o"  # For structured course generation
CONTENT_GENERATION_MODEL = "gpt-4o-mini"  # For content generation (cost-effective)

# --- Text Processing ---
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
MAX_CHUNK_SIZE = 800
RETRIEVAL_K = 3  # Final number of chunks to use in RAG (reduced for speed)
RETRIEVAL_SEARCH_TYPE = "similarity"

# --- Hybrid RAG Settings ---
# Number of documents to retrieve before reranking
HYBRID_RETRIEVAL_K = 5  # Reduced from 10 for faster retrieval
# Weight for RRF (Reciprocal Rank Fusion): 0.5 = equal weight to vector and BM25
# Higher = more weight to vector search, Lower = more weight to BM25
HYBRID_ALPHA = 0.6  # 60% vector, 40% BM25
# Cross-encoder model for reranking
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# --- File Paths ---
OUTPUT_JSON_PATH = os.path.join(COURSES_DIR, "course_output.json")
COURSES_JSON_FILE = os.path.join(BASE_DIR, "courses_week_topics.json")

# --- Audio Settings ---
# Sarvam AI Settings
SARVAM_TTS_SPEAKER = "anushka"

# ElevenLabs Settings
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Default: Rachel
ELEVENLABS_MODEL = "eleven_flash_v2_5"  # Fast, low-latency model

# Audio Provider Selection
# Options: "deepgram" (recommended), "sarvam" (fallback)
AUDIO_STT_PROVIDER = os.getenv("AUDIO_STT_PROVIDER", "deepgram")
# Options: "elevenlabs" (recommended), "sarvam" (fallback)
AUDIO_TTS_PROVIDER = os.getenv("AUDIO_TTS_PROVIDER", "elevenlabs")

# --- Server Configuration ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5003))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# --- Supported Languages ---
SUPPORTED_LANGUAGES = [
    {"code": "en-IN", "name": "English"},
    {"code": "hi-IN", "name": "Hindi"},
    {"code": "bn-IN", "name": "Bengali"},
    {"code": "mr-IN", "name": "Marathi"},
    {"code": "ta-IN", "name": "Tamil"},
    {"code": "te-IN", "name": "Telugu"},
    {"code": "kn-IN", "name": "Kannada"},
    {"code": "ml-IN", "name": "Malayalam"},
    {"code": "gu-IN", "name": "Gujarati"},
    {"code": "pa-IN", "name": "Punjabi"},
    {"code": "ur-IN", "name": "Urdu"}
]

# --- Prompt Template ---
QA_PROMPT_TEMPLATE = """
**Role:**You are ProfessorAI, a highly intelligent AI teacher. Your response will be converted to SPEECH using text-to-speech technology.

🎓 ANSWERING STRATEGY:
- If the answer IS in the provided context: Answer based on the course content
- If the answer is NOT in the provided context: Use your general knowledge to answer the question
- Always provide helpful, accurate answers whether from context or general knowledge
- Questions about "the course", "current course", "this course", "my course" should use the Selected Course Details provided below

CRITICAL - RESPONSE LENGTH:
- Keep responses CONCISE and focused (aim for 2-4 sentences for simple questions)
- Students prefer SHORT, clear answers over long explanations
- Only provide detailed explanations when specifically asked
- Get straight to the point

CRITICAL - COURSE QUERIES:
- Questions about "current course", "this course", "my course" are NORMAL educational questions
- Answer all course-related questions naturally without any content warnings
- Use the Selected Course Details and context to answer about the course
- Only refuse truly harmful content (violence, explicit material, hate speech)
- Educational questions are ALWAYS appropriate

CRITICAL TTS PRONUNCIATION RULES:
1. NEVER use abbreviations or acronyms - Always spell them out:
   - Write "Artificial Intelligence" NOT "A.I" or "AI"
   - Write "Machine Learning" NOT "ML"  
   - Write "Natural Language Processing" NOT "NLP"
   - Write "Application Programming Interface" NOT "API"
   - Write "et cetera" NOT "etc"
   - Write "for example" NOT "e.g."
   - Write "that is" NOT "i.e."
2. Write numbers as words when possible:
   - Write "twenty twenty-four" NOT "2024"
3. Avoid special characters:
   - Write "at" NOT "@"
   - Write "and" NOT "&"
   - Write "percent" NOT "%"

TEACHING GUIDELINES:
- Explain concepts clearly like a teacher in a classroom
- Use conversational, engaging tone
- Give examples when helpful
- Break down complex ideas into simple terms
- Make the student feel you're talking directly to them


RESPONSE RULES:
- If the answer IS in the context: Provide a clear, well-explained answer
- If the answer is NOT in the context: Say "I cannot find the answer to your question in the provided documents."
- If the query is related conversational history then answer by understanding previous conversation history *ONLY*
- Respond in {response_language}
- Format your response to sound natural when spoken aloud
- Use conversation history to understand context and references (like "my last question")

Selected Course Details:
{selected_course_details}

For queires that are related to 'previous context', answer by understanding previous conversaiton. 
CONVERSATION HISTORY:
{conversation_history}

Context:
{context}

Question: {question}

Answer (ready for text-to-speech):"""

# Create directories if they don't exist
os.makedirs(DOCUMENTS_DIR, exist_ok=True)
os.makedirs(VECTORSTORE_DIR, exist_ok=True)
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
os.makedirs(FAISS_DB_PATH, exist_ok=True)
os.makedirs(COURSES_DIR, exist_ok=True)
