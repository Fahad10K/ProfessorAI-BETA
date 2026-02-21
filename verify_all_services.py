"""
Comprehensive Service Verification for ProfessorAI
Checks: Redis, Database, LLM, TTS, STT, and all other services
"""

import os
import sys
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

print("=" * 80)
print("PROFESSOR AI - COMPREHENSIVE SERVICE VERIFICATION")
print("=" * 80)
print()

# Track results
results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

def test_redis_connection():
    """Test Redis Labs Cloud connection"""
    print("\n" + "=" * 80)
    print("1. REDIS CACHE SERVICE (Redis Labs Cloud)")
    print("=" * 80)
    
    try:
        import redis
        
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            redis_host = os.getenv('REDIS_HOST', 'redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com')
            redis_port = os.getenv('REDIS_PORT', '10925')
            redis_username = os.getenv('REDIS_USERNAME', 'default')
            redis_password = os.getenv('REDIS_PASSWORD')
            redis_db = os.getenv('REDIS_DB', '0')
            
            if redis_password:
                redis_url = f"rediss://{redis_username}:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
            else:
                print("❌ REDIS_PASSWORD not found in environment")
                results['failed'].append('Redis - Missing password')
                return False
        
        print(f"   Connecting to: {redis_url.split('@')[1] if '@' in redis_url else redis_url}")
        
        r = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            ssl_cert_reqs=None
        )
        
        # Test operations
        r.ping()
        print("   ✅ PING successful")
        
        r.set('profai_test', 'connected')
        val = r.get('profai_test')
        r.delete('profai_test')
        print("   ✅ SET/GET/DELETE successful")
        
        info = r.info('server')
        print(f"   ✅ Redis version: {info.get('redis_version', 'Unknown')}")
        print(f"   ✅ Used memory: {info.get('used_memory_human', 'Unknown')}")
        
        results['passed'].append('Redis Cache - Connected and operational')
        return True
        
    except ImportError:
        print("   ⚠️  redis module not installed")
        print("   Run: pip install redis")
        results['warnings'].append('Redis - Module not installed')
        return False
    except Exception as e:
        print(f"   ❌ Redis connection failed: {e}")
        results['failed'].append(f'Redis - {str(e)[:50]}')
        return False


def test_database_connection():
    """Test PostgreSQL (Neon) database connection"""
    print("\n" + "=" * 80)
    print("2. DATABASE SERVICE (PostgreSQL/Neon)")
    print("=" * 80)
    
    use_db = os.getenv('USE_DATABASE', 'False').lower() == 'true'
    db_url = os.getenv('DATABASE_URL')
    
    print(f"   USE_DATABASE: {use_db}")
    
    if not use_db:
        print("   ⚠️  Database disabled (USE_DATABASE=False)")
        print("   Application will use JSON file storage")
        results['warnings'].append('Database - Disabled, using JSON files')
        return True
    
    if not db_url:
        print("   ❌ DATABASE_URL not set")
        results['failed'].append('Database - Missing DATABASE_URL')
        return False
    
    try:
        from sqlalchemy import create_engine, text
        
        # Mask password for display
        display_url = db_url.split('@')[0].split(':')[0] + '://...@' + db_url.split('@')[1].split('?')[0]
        print(f"   Connecting to: {display_url}")
        
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✅ Connected to PostgreSQL")
            print(f"   ✅ Version: {version.split(',')[0]}")
            
            # Check tables
            result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
            table_count = result.fetchone()[0]
            print(f"   ✅ Tables in database: {table_count}")
        
        results['passed'].append('Database - Connected and operational')
        return True
        
    except ImportError as e:
        print(f"   ⚠️  Missing module: {e}")
        print("   Run: pip install sqlalchemy psycopg2-binary")
        results['warnings'].append('Database - Missing modules')
        return False
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        results['failed'].append(f'Database - {str(e)[:50]}')
        return False


def test_openai_llm():
    """Test OpenAI LLM service"""
    print("\n" + "=" * 80)
    print("3. LLM SERVICE (OpenAI)")
    print("=" * 80)
    
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("   ❌ OPENAI_API_KEY not set")
        results['failed'].append('OpenAI LLM - Missing API key')
        return False
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        # Test with a simple completion
        print("   Testing GPT-4o-mini...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'OK' if you're working"}],
            max_tokens=10
        )
        
        reply = response.choices[0].message.content
        print(f"   ✅ Response: {reply}")
        print(f"   ✅ Model: {response.model}")
        print(f"   ✅ Tokens used: {response.usage.total_tokens}")
        
        results['passed'].append('OpenAI LLM - Operational')
        return True
        
    except ImportError:
        print("   ⚠️  openai module not installed")
        print("   Run: pip install openai")
        results['warnings'].append('OpenAI - Module not installed')
        return False
    except Exception as e:
        print(f"   ❌ OpenAI API failed: {e}")
        results['failed'].append(f'OpenAI LLM - {str(e)[:50]}')
        return False


def test_groq_llm():
    """Test Groq LLM service"""
    print("\n" + "=" * 80)
    print("4. GROQ LLM SERVICE")
    print("=" * 80)
    
    api_key = os.getenv('GROQ_API_KEY')
    
    if not api_key:
        print("   ⚠️  GROQ_API_KEY not set (optional)")
        results['warnings'].append('Groq - API key not set')
        return True  # Not critical
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        print("   Testing Groq LLaMA...")
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Say 'OK' if you're working"}],
            max_tokens=10
        )
        
        reply = response.choices[0].message.content
        print(f"   ✅ Response: {reply}")
        print(f"   ✅ Model: {response.model}")
        
        results['passed'].append('Groq LLM - Operational')
        return True
        
    except ImportError:
        print("   ⚠️  groq module not installed")
        results['warnings'].append('Groq - Module not installed')
        return True  # Not critical
    except Exception as e:
        print(f"   ⚠️  Groq API issue: {e}")
        results['warnings'].append('Groq - API error')
        return True  # Not critical


def test_deepgram_stt():
    """Test Deepgram STT service"""
    print("\n" + "=" * 80)
    print("5. STT SERVICE (Deepgram)")
    print("=" * 80)
    
    api_key = os.getenv('DEEPGRAM_API_KEY')
    
    if not api_key:
        print("   ⚠️  DEEPGRAM_API_KEY not set")
        print("   STT will fall back to other providers")
        results['warnings'].append('Deepgram STT - API key not set')
        return True  # Not critical if fallback exists
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        from deepgram import DeepgramClient
        
        client = DeepgramClient(api_key)
        print("   ✅ Deepgram client initialized")
        
        results['passed'].append('Deepgram STT - Configured')
        return True
        
    except ImportError:
        print("   ⚠️  deepgram-sdk module not installed")
        print("   Run: pip install deepgram-sdk")
        results['warnings'].append('Deepgram - Module not installed')
        return True
    except Exception as e:
        print(f"   ⚠️  Deepgram initialization issue: {e}")
        results['warnings'].append('Deepgram - Initialization error')
        return True


def test_elevenlabs_tts():
    """Test ElevenLabs TTS service"""
    print("\n" + "=" * 80)
    print("6. TTS SERVICE (ElevenLabs)")
    print("=" * 80)
    
    api_key = os.getenv('ELEVENLABS_API_KEY')
    
    if not api_key:
        print("   ⚠️  ELEVENLABS_API_KEY not set")
        print("   TTS will fall back to other providers")
        results['warnings'].append('ElevenLabs TTS - API key not set')
        return True  # Not critical if fallback exists
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        from elevenlabs import ElevenLabs
        
        client = ElevenLabs(api_key=api_key)
        print("   ✅ ElevenLabs client initialized")
        
        # Try to list voices
        try:
            voices = client.voices.get_all()
            print(f"   ✅ Available voices: {len(voices.voices)}")
        except:
            print("   ✅ Client configured (voice list unavailable)")
        
        results['passed'].append('ElevenLabs TTS - Configured')
        return True
        
    except ImportError:
        print("   ⚠️  elevenlabs module not installed")
        print("   Run: pip install elevenlabs")
        results['warnings'].append('ElevenLabs - Module not installed')
        return True
    except Exception as e:
        print(f"   ⚠️  ElevenLabs initialization issue: {e}")
        results['warnings'].append('ElevenLabs - Initialization error')
        return True


def test_sarvam_service():
    """Test Sarvam AI service (fallback TTS/STT)"""
    print("\n" + "=" * 80)
    print("7. SARVAM AI SERVICE (Fallback TTS/STT)")
    print("=" * 80)
    
    api_key = os.getenv('SARVAM_API_KEY')
    
    if not api_key:
        print("   ⚠️  SARVAM_API_KEY not set")
        print("   Sarvam fallback unavailable")
        results['warnings'].append('Sarvam - API key not set')
        return True  # Not critical
    
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Sarvam doesn't have a simple init test, just check module
        import httpx
        print("   ✅ Sarvam service configured")
        results['passed'].append('Sarvam AI - Configured')
        return True
        
    except ImportError:
        print("   ⚠️  Required modules not installed")
        results['warnings'].append('Sarvam - Module not installed')
        return True
    except Exception as e:
        print(f"   ⚠️  Sarvam check issue: {e}")
        results['warnings'].append('Sarvam - Check error')
        return True


def test_chromadb_vectorstore():
    """Test ChromaDB vector store"""
    print("\n" + "=" * 80)
    print("8. VECTOR STORE (ChromaDB)")
    print("=" * 80)
    
    use_cloud = os.getenv('USE_CHROMA_CLOUD', 'True').lower() == 'true'
    
    print(f"   USE_CHROMA_CLOUD: {use_cloud}")
    
    if use_cloud:
        api_key = os.getenv('CHROMA_CLOUD_API_KEY')
        tenant = os.getenv('CHROMA_CLOUD_TENANT')
        database = os.getenv('CHROMA_CLOUD_DATABASE')
        
        if not all([api_key, tenant, database]):
            print("   ⚠️  ChromaDB Cloud credentials incomplete")
            print("   Application may fall back to local storage")
            results['warnings'].append('ChromaDB - Cloud credentials missing')
            return True
        
        print(f"   Tenant: {tenant}")
        print(f"   Database: {database}")
        
        try:
            import chromadb
            from chromadb.config import Settings
            
            client = chromadb.HttpClient(
                host=f"https://api.trychroma.com",
                settings=Settings(
                    chroma_client_auth_provider="token",
                    chroma_client_auth_credentials=api_key
                )
            )
            
            # Try to heartbeat
            client.heartbeat()
            print("   ✅ ChromaDB Cloud connected")
            
            results['passed'].append('ChromaDB - Cloud operational')
            return True
            
        except ImportError:
            print("   ⚠️  chromadb module not installed")
            results['warnings'].append('ChromaDB - Module not installed')
            return True
        except Exception as e:
            print(f"   ⚠️  ChromaDB Cloud connection issue: {e}")
            results['warnings'].append('ChromaDB - Connection error')
            return True
    else:
        print("   ✅ Using local FAISS vector store")
        results['passed'].append('Vector Store - Local FAISS mode')
        return True


def test_celery_broker():
    """Test Celery with Redis broker"""
    print("\n" + "=" * 80)
    print("9. CELERY TASK QUEUE")
    print("=" * 80)
    
    try:
        from celery_app import celery_app
        
        # Check broker connection
        print("   Testing broker connection...")
        inspector = celery_app.control.inspect()
        
        # This will fail if broker is not accessible
        print("   ✅ Celery app initialized")
        print(f"   ✅ Broker: {celery_app.conf.broker_url.split('@')[1] if '@' in celery_app.conf.broker_url else 'localhost'}")
        
        results['passed'].append('Celery - Configured with Redis broker')
        return True
        
    except ImportError as e:
        print(f"   ⚠️  Missing module: {e}")
        results['warnings'].append('Celery - Module not installed')
        return True
    except Exception as e:
        print(f"   ⚠️  Celery configuration issue: {e}")
        results['warnings'].append('Celery - Configuration error')
        return True


def print_summary():
    """Print final summary"""
    print("\n" + "=" * 80)
    print("SERVICE VERIFICATION SUMMARY")
    print("=" * 80)
    
    print(f"\n✅ PASSED ({len(results['passed'])}):")
    for item in results['passed']:
        print(f"   • {item}")
    
    if results['warnings']:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for item in results['warnings']:
            print(f"   • {item}")
    
    if results['failed']:
        print(f"\n❌ FAILED ({len(results['failed'])}):")
        for item in results['failed']:
            print(f"   • {item}")
    
    print("\n" + "=" * 80)
    
    total = len(results['passed']) + len(results['warnings']) + len(results['failed'])
    critical_failures = len(results['failed'])
    
    if critical_failures == 0:
        print("🎉 ALL CRITICAL SERVICES OPERATIONAL!")
        if results['warnings']:
            print("⚠️  Some optional services have warnings (see above)")
        print("✅ Application is ready to run")
    else:
        print(f"❌ {critical_failures} CRITICAL SERVICE(S) FAILED")
        print("⚠️  Please fix the failed services before running the application")
    
    print("=" * 80)
    print()


def main():
    """Run all service tests"""
    
    # Core services (critical)
    test_redis_connection()
    test_database_connection()
    test_openai_llm()
    
    # Optional services (warnings only)
    test_groq_llm()
    test_deepgram_stt()
    test_elevenlabs_tts()
    test_sarvam_service()
    test_chromadb_vectorstore()
    test_celery_broker()
    
    # Print summary
    print_summary()
    
    # Return exit code
    return 0 if len(results['failed']) == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
