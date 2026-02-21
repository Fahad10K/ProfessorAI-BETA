"""
Test database connection and check if courses exist
"""
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("DATABASE CONNECTION TEST")
print("=" * 60)

# Check environment variables
print("\n1. Environment Variables:")
print(f"   USE_DATABASE: {os.getenv('USE_DATABASE')}")
print(f"   DATABASE_URL: {os.getenv('DATABASE_URL')[:50]}..." if os.getenv('DATABASE_URL') else "   DATABASE_URL: Not set")

# Try to import and initialize database service
print("\n2. Importing Database Service...")
try:
    from services.database_service_actual import get_database_service
    print("   ✅ Import successful")
except Exception as e:
    print(f"   ❌ Import failed: {e}")
    exit(1)

# Initialize database service
print("\n3. Initializing Database Service...")
try:
    db_service = get_database_service()
    if db_service:
        print("   ✅ Database service initialized")
    else:
        print("   ❌ Database service returned None")
        print("   Reason: USE_DATABASE might be False")
        exit(1)
except Exception as e:
    print(f"   ❌ Initialization failed: {e}")
    exit(1)

# Test get_all_courses method
print("\n4. Testing get_all_courses()...")
try:
    courses = db_service.get_all_courses()
    print(f"   ✅ Method executed successfully")
    print(f"   Found {len(courses)} courses in database")
    
    if len(courses) > 0:
        print("\n5. Sample Courses from Database:")
        for i, course in enumerate(courses[:3], 1):
            print(f"\n   Course {i}:")
            print(f"      ID: {course.get('course_id')}")
            print(f"      Title: {course.get('course_title')}")
            print(f"      Modules: {course.get('modules')}")
            print(f"      Type: {type(course.get('course_id'))}")
    else:
        print("\n   ⚠️ Database is empty - no courses found")
        print("   This is why the API falls back to JSON files!")
        
except Exception as e:
    print(f"   ❌ get_all_courses() failed: {e}")
    import traceback
    traceback.print_exc()

# Test get_course method with a sample ID
print("\n6. Testing get_course() with sample UUID...")
try:
    # Try to get first course if available
    if len(courses) > 0:
        test_id = courses[0].get('course_id')
        print(f"   Testing with ID: {test_id}")
        course = db_service.get_course(test_id)
        if course:
            print(f"   ✅ Successfully retrieved course: {course.get('course_title')}")
        else:
            print(f"   ❌ Course not found")
except Exception as e:
    print(f"   ❌ get_course() failed: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
