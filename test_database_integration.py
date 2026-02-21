"""
Test Database Integration
Verify that courses and quizzes can be saved to and retrieved from the database
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_connection():
    """Test 1: Verify database connection"""
    print("\n" + "="*60)
    print("TEST 1: Database Connection")
    print("="*60)
    
    try:
        from services.database_service_actual import get_database_service
        
        db = get_database_service()
        if db:
            print("✅ Database service initialized successfully")
            print(f"✅ Connected to: {os.getenv('DATABASE_URL', 'N/A')[:50]}...")
            return db
        else:
            print("❌ Database service not available")
            print("   Check: USE_DATABASE=True in .env")
            return None
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None


def test_list_courses(db):
    """Test 2: List existing courses"""
    print("\n" + "="*60)
    print("TEST 2: List Existing Courses")
    print("="*60)
    
    if not db:
        print("⏭️  Skipped (no database connection)")
        return
    
    try:
        courses = db.list_courses()
        print(f"✅ Found {len(courses)} courses in database:")
        for i, course in enumerate(courses[:5], 1):  # Show first 5
            course_id = course['course_id']
            title = course['course_title']
            modules = course.get('modules', 0)
            print(f"   {i}. [{course_id[:8]}...] {title} ({modules} modules)")
        
        if len(courses) > 5:
            print(f"   ... and {len(courses) - 5} more courses")
        
        return courses
    except Exception as e:
        print(f"❌ Error listing courses: {e}")
        return []


def test_create_course(db):
    """Test 3: Create a test course"""
    print("\n" + "="*60)
    print("TEST 3: Create Test Course")
    print("="*60)
    
    if not db:
        print("⏭️  Skipped (no database connection)")
        return None
    
    try:
        test_course = {
            'course_title': 'Database Integration Test Course',
            'description': 'This is a test course to verify database integration',
            'modules': [
                {
                    'week': 1,
                    'title': 'Test Module 1',
                    'description': 'First test module',
                    'learning_objectives': ['Understand database integration', 'Test course creation'],
                    'sub_topics': [
                        {
                            'title': 'Introduction to Testing',
                            'content': 'This is test content for the first topic.'
                        },
                        {
                            'title': 'Database Verification',
                            'content': 'This topic covers how to verify database operations.'
                        }
                    ]
                },
                {
                    'week': 2,
                    'title': 'Test Module 2',
                    'description': 'Second test module',
                    'learning_objectives': ['Advanced testing concepts'],
                    'sub_topics': [
                        {
                            'title': 'Quiz Integration',
                            'content': 'Testing quiz creation and storage.'
                        }
                    ]
                }
            ]
        }
        
        course_id = db.create_course(test_course, teacher_id='test_user')
        print(f"✅ Course created successfully!")
        print(f"   Course ID: {course_id}")
        print(f"   Title: {test_course['course_title']}")
        print(f"   Modules: {len(test_course['modules'])}")
        
        return course_id
    except Exception as e:
        print(f"❌ Error creating course: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_retrieve_course(db, course_id):
    """Test 4: Retrieve the created course"""
    print("\n" + "="*60)
    print("TEST 4: Retrieve Course")
    print("="*60)
    
    if not db or not course_id:
        print("⏭️  Skipped (no database connection or course_id)")
        return None
    
    try:
        course = db.get_course(course_id)
        if course:
            print(f"✅ Course retrieved successfully!")
            print(f"   Course ID: {course['course_id']}")
            print(f"   Title: {course['course_title']}")
            print(f"   Modules: {len(course['modules'])}")
            
            for i, module in enumerate(course['modules'], 1):
                topics_count = len(module.get('sub_topics', []))
                print(f"   Module {i}: {module['title']} ({topics_count} topics)")
            
            return course
        else:
            print(f"❌ Course not found with ID: {course_id}")
            return None
    except Exception as e:
        print(f"❌ Error retrieving course: {e}")
        return None


def test_create_quiz(db, course_id):
    """Test 5: Create a quiz for the course"""
    print("\n" + "="*60)
    print("TEST 5: Create Quiz")
    print("="*60)
    
    if not db or not course_id:
        print("⏭️  Skipped (no database connection or course_id)")
        return None
    
    try:
        quiz_data = {
            'quiz_id': 'test_quiz_db_integration',
            'title': 'Database Integration Quiz',
            'description': 'Test quiz for database integration',
            'quiz_type': 'module',
            'module_week': 1,
            'questions': [
                {
                    'question_number': 1,
                    'question': 'What is the purpose of this test?',
                    'options': {
                        'A': 'To test database integration',
                        'B': 'To break the system',
                        'C': 'Random testing',
                        'D': 'None of the above'
                    },
                    'correct_answer': 'A',
                    'explanation': 'This test verifies database integration works correctly.'
                },
                {
                    'question_number': 2,
                    'question': 'Which database are we using?',
                    'options': {
                        'A': 'MySQL',
                        'B': 'PostgreSQL (Neon)',
                        'C': 'MongoDB',
                        'D': 'SQLite'
                    },
                    'correct_answer': 'B',
                    'explanation': 'We are using PostgreSQL via Neon cloud service.'
                }
            ]
        }
        
        quiz_id = db.create_quiz(quiz_data, course_id)
        print(f"✅ Quiz created successfully!")
        print(f"   Quiz ID: {quiz_id}")
        print(f"   Title: {quiz_data['title']}")
        print(f"   Questions: {len(quiz_data['questions'])}")
        
        return quiz_id
    except Exception as e:
        print(f"❌ Error creating quiz: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_retrieve_quiz(db, quiz_id):
    """Test 6: Retrieve the created quiz"""
    print("\n" + "="*60)
    print("TEST 6: Retrieve Quiz")
    print("="*60)
    
    if not db or not quiz_id:
        print("⏭️  Skipped (no database connection or quiz_id)")
        return None
    
    try:
        quiz = db.get_quiz(quiz_id)
        if quiz:
            print(f"✅ Quiz retrieved successfully!")
            print(f"   Quiz ID: {quiz['quiz_id']}")
            print(f"   Title: {quiz['title']}")
            print(f"   Course ID: {quiz['course_id']}")
            print(f"   Questions: {len(quiz['questions'])}")
            
            for i, q in enumerate(quiz['questions'], 1):
                print(f"   Q{i}: {q['question'][:50]}...")
            
            return quiz
        else:
            print(f"❌ Quiz not found with ID: {quiz_id}")
            return None
    except Exception as e:
        print(f"❌ Error retrieving quiz: {e}")
        return None


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("DATABASE INTEGRATION TEST SUITE")
    print("="*60)
    print(f"Database URL: {os.getenv('DATABASE_URL', 'NOT SET')[:50]}...")
    print(f"USE_DATABASE: {os.getenv('USE_DATABASE', 'NOT SET')}")
    
    # Test 1: Connection
    db = test_database_connection()
    
    # Test 2: List courses
    existing_courses = test_list_courses(db)
    
    # Test 3: Create course
    course_id = test_create_course(db)
    
    # Test 4: Retrieve course
    course = test_retrieve_course(db, course_id)
    
    # Test 5: Create quiz
    quiz_id = test_create_quiz(db, course_id)
    
    # Test 6: Retrieve quiz
    quiz = test_retrieve_quiz(db, quiz_id)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    if db:
        print("✅ Database Connection: PASSED")
    else:
        print("❌ Database Connection: FAILED")
    
    if existing_courses is not None:
        print(f"✅ List Courses: PASSED ({len(existing_courses)} courses found)")
    else:
        print("❌ List Courses: FAILED")
    
    if course_id:
        print(f"✅ Create Course: PASSED (ID: {course_id[:8]}...)")
    else:
        print("❌ Create Course: FAILED")
    
    if course:
        print("✅ Retrieve Course: PASSED")
    else:
        print("❌ Retrieve Course: FAILED")
    
    if quiz_id:
        print(f"✅ Create Quiz: PASSED (ID: {quiz_id})")
    else:
        print("❌ Create Quiz: FAILED")
    
    if quiz:
        print("✅ Retrieve Quiz: PASSED")
    else:
        print("❌ Retrieve Quiz: FAILED")
    
    print("\n" + "="*60)
    if db and course_id and quiz_id:
        print("🎉 ALL TESTS PASSED! Database integration is working!")
    elif not db:
        print("⚠️  Database not enabled. Set USE_DATABASE=True in .env")
    else:
        print("⚠️  Some tests failed. Check errors above.")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
