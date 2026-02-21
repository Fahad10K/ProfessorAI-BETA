"""
Quick test to verify .env file is loaded correctly
Run this before starting Celery
"""

import os
from dotenv import load_dotenv

print("="*60)
print("Testing .env File Configuration")
print("="*60)

# Load .env
load_dotenv()

# Check Redis
redis_url = os.getenv('REDIS_URL')
if redis_url:
    # Mask password for security
    if '@' in redis_url:
        parts = redis_url.split('@')
        host_part = parts[-1]
        print(f"✅ REDIS_URL found: ...@{host_part}")
    else:
        print(f"✅ REDIS_URL found: {redis_url[:20]}...")
else:
    print("❌ REDIS_URL not found in .env")

# Check API Keys
openai_key = os.getenv('OPENAI_API_KEY')
if openai_key:
    print(f"✅ OPENAI_API_KEY found: {openai_key[:10]}...")
else:
    print("❌ OPENAI_API_KEY not found")

sarvam_key = os.getenv('SARVAM_API_KEY')
if sarvam_key:
    print(f"✅ SARVAM_API_KEY found: {sarvam_key[:10]}...")
else:
    print("❌ SARVAM_API_KEY not found")

groq_key = os.getenv('GROQ_API_KEY')
if groq_key:
    print(f"✅ GROQ_API_KEY found: {groq_key[:10]}...")
else:
    print("❌ GROQ_API_KEY not found")

# Check Database
db_url = os.getenv('DATABASE_URL')
if db_url:
    print(f"✅ DATABASE_URL found")
else:
    print("❌ DATABASE_URL not found")

use_db = os.getenv('USE_DATABASE')
print(f"   USE_DATABASE: {use_db}")

print("="*60)

# Test Redis connection
print("\nTesting Redis Connection...")
try:
    import redis
    r = redis.Redis.from_url(redis_url)
    if r.ping():
        print("✅ Redis connection successful!")
    else:
        print("❌ Redis ping failed")
except Exception as e:
    print(f"❌ Redis connection error: {e}")

print("="*60)
print("\nIf all checks pass, you can start Celery:")
print("  celery -A celery_app worker --loglevel=info --pool=solo")
print("="*60)
