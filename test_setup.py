"""
Test Setup - Verify Redis + Database Connection
Run this to ensure everything is configured correctly

Usage:
    python test_setup.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("="*60)
print("🧪 Testing ProfessorAI Setup")
print("="*60)

# ============================================================
# TEST 1: Environment Variables
# ============================================================

print("\n📋 Step 1: Checking Environment Variables...")

required_vars = {
    'REDIS_URL': os.getenv('REDIS_URL'),
    'DATABASE_URL': os.getenv('DATABASE_URL'),
    'USE_DATABASE': os.getenv('USE_DATABASE'),
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'GROQ_API_KEY': os.getenv('GROQ_API_KEY'),
}

all_present = True
for var, value in required_vars.items():
    if value:
        # Mask sensitive values
        if 'KEY' in var or 'URL' in var:
            display_value = value[:20] + "..." if len(value) > 20 else value
        else:
            display_value = value
        print(f"  ✅ {var}: {display_value}")
    else:
        print(f"  ❌ {var}: NOT SET")
        all_present = False

if not all_present:
    print("\n❌ ERROR: Missing required environment variables")
    print("Please set them in your .env file")
    sys.exit(1)

# ============================================================
# TEST 2: Redis Connection
# ============================================================

print("\n📦 Step 2: Testing Redis Connection...")

try:
    import redis
    
    redis_url = os.getenv('REDIS_URL')
    r = redis.Redis.from_url(redis_url)
    
    # Test ping
    if r.ping():
        print("  ✅ Redis connection successful!")
        
        # Test set/get
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        if value == b'test_value':
            print("  ✅ Redis read/write working!")
        r.delete('test_key')
    else:
        print("  ❌ Redis ping failed")
        sys.exit(1)
        
except Exception as e:
    print(f"  ❌ Redis connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check your REDIS_URL in .env")
    print("2. Ensure Upstash Redis is active")
    print("3. Check your internet connection")
    sys.exit(1)

# ============================================================
# TEST 3: Database Connection
# ============================================================

print("\n🗄️  Step 3: Testing PostgreSQL Connection...")

try:
    import psycopg2
    
    database_url = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    
    # Test query
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"  ✅ PostgreSQL connected!")
    print(f"  📌 Version: {version[:50]}...")
    
    # Check tables
    cursor.execute("""
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename;
    """)
    tables = cursor.fetchall()
    
    expected_tables = [
        'courses', 'job_queue', 'modules', 'quiz_questions', 
        'quiz_responses', 'quizzes', 'source_files', 'topics', 
        'user_progress', 'users'
    ]
    
    found_tables = [t[0] for t in tables]
    
    print(f"  📊 Found {len(found_tables)} tables:")
    for table in found_tables:
        status = "✅" if table in expected_tables else "⚠️"
        print(f"    {status} {table}")
    
    missing_tables = set(expected_tables) - set(found_tables)
    if missing_tables:
        print(f"\n  ⚠️  Missing tables: {', '.join(missing_tables)}")
        print("  Run: psql YOUR_DATABASE_URL < migrations/001_initial_schema.sql")
    else:
        print(f"\n  ✅ All tables present!")
    
    # Check for data
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    print(f"  👥 Users: {user_count}")
    
    cursor.execute("SELECT COUNT(*) FROM courses;")
    course_count = cursor.fetchone()[0]
    print(f"  📚 Courses: {course_count}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"  ❌ Database connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check your DATABASE_URL in .env")
    print("2. Ensure Neon PostgreSQL is active")
    print("3. Run migration: psql YOUR_URL < migrations/001_initial_schema.sql")
    sys.exit(1)

# ============================================================
# TEST 4: Celery Configuration
# ============================================================

print("\n🔧 Step 4: Testing Celery Configuration...")

try:
    from celery_app import celery_app, BROKER_URL, BACKEND_URL
    
    print(f"  ✅ Celery app imported successfully")
    print(f"  📌 Broker: {BROKER_URL[:30]}...")
    print(f"  📌 Backend: {BACKEND_URL[:30]}...")
    
except Exception as e:
    print(f"  ❌ Celery configuration error: {e}")
    sys.exit(1)

# ============================================================
# TEST 5: Database Service
# ============================================================

print("\n🔌 Step 5: Testing Database Service...")

try:
    from services.database_service_new import get_database_service
    
    db = get_database_service()
    if db:
        print("  ✅ Database service initialized")
        
        # Test query
        courses = db.list_courses()
        print(f"  📚 Found {len(courses)} courses in database")
        
    else:
        print("  ⚠️  Database service not enabled (USE_DATABASE=False)")
    
except Exception as e:
    print(f"  ❌ Database service error: {e}")
    print("\nThis is okay for now, you can still test Redis/Celery")

# ============================================================
# SUMMARY
# ============================================================

print("\n" + "="*60)
print("🎉 Setup Test Complete!")
print("="*60)

print("\n✅ What's Working:")
print("  • Environment variables loaded")
print("  • Redis connection established")
print("  • PostgreSQL connection established")
print("  • Celery configuration loaded")

print("\n⏭️  Next Steps:")
print("  1. Start Celery worker:")
print("     python worker.py")
print("")
print("  2. Start API server (in new terminal):")
print("     python run_profai_websocket_celery.py")
print("")
print("  3. Test upload:")
print("     curl -X POST http://localhost:5001/api/upload-pdfs \\")
print("       -F 'files=@test.pdf' \\")
print("       -F 'course_title=Test Course'")

print("\n" + "="*60)
