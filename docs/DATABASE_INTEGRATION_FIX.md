# 🔧 Database Integration Fixes - ACTUAL Schema

## Critical Finding

Your **actual database schema** uses **TEXT UUIDs** for primary keys, NOT integers:

```
courses.id = TEXT (UUID) ← NOT INTEGER  
users.id = TEXT (UUID) ← Has username, email, password
modules.course_id = TEXT ← References courses.id
quizzes.course_id = TEXT ← References courses.id
```

## Current Problems

### Problem #1: Application Uses JSON Files, Not Database
- `document_service.py` → Saves courses to `data/courses/course_output.json` with INTEGER course_id
- `quiz_service.py` → Saves quizzes to `data/quizzes/*.json` with INTEGER course_id
- **Database exists but is NOT being used by the application!**

### Problem #2: Schema Mismatch
- JSON files: `course_id: 1, 2, 3` (integers)
- Database: `id: "a1b2c3d4-..."` (TEXT UUIDs)
- **Incompatible!**

### Problem #3: Wrong Database Service File
- `database_service_new.py` → Assumes INTEGER course_id (WRONG!)
- Need: `database_service_actual.py` → Uses TEXT UUID (CORRECT!)

---

## ✅ Fixes Applied

### Fix #1: Created `database_service_actual.py`
**File:** `services/database_service_actual.py` ✅ CREATED

**Key Features:**
- Matches ACTUAL Neon schema exactly
- `Course.id = TEXT` (UUID)
- `User.id = TEXT` with username/email/password
- `Module.course_id = TEXT` (references courses.id)
- `Quiz.course_id = TEXT` (references courses.id)
- All foreign keys correct

### Fix #2: Updated Model Definitions
**Actual Schema:**
```python
class Course(Base):
    id = Column(Text, primary_key=True)  # UUID
    title = Column(Text)
    teacher_id = Column(Text)  # References users.id
    is_free = Column(Boolean, default=False)
    price = Column(Numeric)
    # No course_id column!

class Module(Base):
    id = Column(Integer, primary_key=True)
    course_id = Column(Text, ForeignKey('courses.id'))  # TEXT!
    week = Column(Integer)
```

---

## 🔄 Required Changes

### Change #1: Enable Database in .env
```env
# In your .env file:
USE_DATABASE=True
DATABASE_URL=postgresql://...@neon.tech/profai?sslmode=require
```

### Change #2: Update Services to Use Database

#### A. Import Correct Database Service
**IN:** `services/quiz_service.py`, `services/document_service.py`, `tasks/pdf_processing.py`

```python
# ADD AT TOP:
from services.database_service_actual import get_database_service

# IN __init__:
self.db_service = get_database_service()  # Returns None if USE_DATABASE=False
```

#### B. Modify Quiz Storage to Use DB
**File:** `services/quiz_service.py`

```python
def _store_quiz(self, quiz: Quiz, course_id: str = None):
    """Store quiz - use database if enabled, else JSON"""
    
    # Try database first
    if self.db_service and course_id:
        try:
            quiz_data = {
                'quiz_id': quiz.quiz_id,
                'title': quiz.title,
                'quiz_type': quiz.quiz_type,
                'module_week': quiz.module_week,
                'questions': [q.dict() for q in quiz.questions]
            }
            self.db_service.create_quiz(quiz_data, course_id)  # TEXT UUID
            logging.info(f"✅ Quiz {quiz.quiz_id} saved to database")
            return
        except Exception as e:
            logging.warning(f"Failed to save quiz to DB, using JSON: {e}")
    
    # Fallback to JSON files
    quiz_data = quiz.dict()
    if course_id:
        quiz_data['course_id'] = str(course_id)
    
    quiz_file = os.path.join(self.quiz_storage_dir, f"{quiz.quiz_id}.json")
    with open(quiz_file, 'w', encoding='utf-8') as f:
        json.dump(quiz_data, f, indent=2)
    logging.info(f"✅ Quiz {quiz.quiz_id} saved to JSON")
```

#### C. Modify Course Storage to Use DB
**File:** `services/document_service.py`

```python
def save_course(self, course_dict: dict) -> dict:
    """Save course - use database if enabled, else JSON"""
    
    # Try database first
    if self.db_service:
        try:
            course_id = self.db_service.create_course(
                course_dict, 
                teacher_id='system'
            )
            # Return course with TEXT UUID
            course_dict['course_id'] = course_id
            logging.info(f"✅ Course saved to database: {course_id}")
            return course_dict
        except Exception as e:
            logging.warning(f"Failed to save course to DB, using JSON: {e}")
    
    # Fallback to JSON files (existing logic)
    existing_courses = self._load_existing_courses()
    next_course_id = self._get_next_course_id(existing_courses)
    course_dict['course_id'] = next_course_id  # INTEGER for JSON
    existing_courses.append(course_dict)
    self._save_courses_to_file(existing_courses)
    logging.info(f"✅ Course saved to JSON: {next_course_id}")
    return course_dict
```

---

## 🧪 Testing Plan

### Test 1: Verify Database Connection
```python
# Create: test_database.py
from services.database_service_actual import get_database_service

db = get_database_service()
if db:
    print("✅ Database connected!")
    courses = db.list_courses()
    print(f"📊 Found {len(courses)} courses")
    for c in courses:
        print(f"  - {c['course_title']} (ID: {c['course_id'][:8]}...)")
else:
    print("❌ Database not enabled or failed")
```

### Test 2: Create Test Course in DB
```python
# test_create_course.py
from services.database_service_actual import get_database_service

db = get_database_service()
if db:
    test_course = {
        'course_title': 'Test Course via Database',
        'description': 'Testing database integration',
        'modules': [
            {
                'week': 1,
                'title': 'Module 1',
                'description': 'Test module',
                'learning_objectives': ['Learn testing'],
                'sub_topics': [
                    {
                        'title': 'Topic 1',
                        'content': 'Test content for topic 1'
                    }
                ]
            }
        ]
    }
    
    course_id = db.create_course(test_course, teacher_id='test_teacher')
    print(f"✅ Created course: {course_id}")
    
    # Retrieve it
    retrieved = db.get_course(course_id)
    print(f"✅ Retrieved course: {retrieved['course_title']}")
```

### Test 3: Create Quiz in DB
```python
# test_create_quiz.py
from services.database_service_actual import get_database_service

db = get_database_service()
if db:
    # Get first course ID
    courses = db.list_courses()
    if courses:
        course_id = courses[0]['course_id']
        
        quiz_data = {
            'quiz_id': 'test_quiz_001',
            'title': 'Test Quiz',
            'quiz_type': 'module',
            'module_week': 1,
            'questions': [
                {
                    'question_number': 1,
                    'question': 'What is 2+2?',
                    'options': {'A': '3', 'B': '4', 'C': '5', 'D': '6'},
                    'correct_answer': 'B',
                    'explanation': 'Basic arithmetic'
                }
            ]
        }
        
        quiz_id = db.create_quiz(quiz_data, course_id)
        print(f"✅ Created quiz: {quiz_id}")
        
        # Retrieve it
        retrieved = db.get_quiz(quiz_id)
        print(f"✅ Retrieved quiz: {retrieved['title']}")
```

---

## 📋 Action Checklist

### Step 1: Enable Database (2 min)
- [ ] Set `USE_DATABASE=True` in `.env`
- [ ] Verify `DATABASE_URL` is correct
- [ ] Run test: `python test_database.py`

### Step 2: Update Services (10 min)
- [ ] Add `database_service_actual` import to `quiz_service.py`
- [ ] Add `database_service_actual` import to `document_service.py`
- [ ] Update `_store_quiz()` method in quiz_service.py
- [ ] Update `save_course()` method in document_service.py

### Step 3: Test Integration (5 min)
- [ ] Run: `python test_create_course.py`
- [ ] Run: `python test_create_quiz.py`
- [ ] Start API: `python run_profai_websocket_celery.py`
- [ ] Test endpoint: `curl http://localhost:5001/api/courses`

### Step 4: Test Full Flow (10 min)
- [ ] Upload PDF via API
- [ ] Check if course saved to database (not JSON)
- [ ] Generate quiz
- [ ] Check if quiz saved to database (not JSON)
- [ ] Verify data persists (restart app, check again)

---

## 🎯 Expected Outcomes

### After Fixes:
✅ New courses created via API → Saved to database with TEXT UUID  
✅ New quizzes created via API → Saved to database, linked to course  
✅ `GET /api/courses` → Returns courses from database  
✅ `GET /api/quiz/{quiz_id}` → Returns quiz from database  
✅ Existing JSON files still work (backward compatible)  

### Fallback Behavior:
- If `USE_DATABASE=False` → Falls back to JSON files ✓
- If database connection fails → Falls back to JSON files ✓
- Existing JSON courses still accessible ✓

---

## ⚠️ Important Notes

### course_id Compatibility:
- **JSON files:** course_id = 1, 2, 3 (INTEGER)
- **Database:** course_id = "uuid-text" (TEXT UUID)
- **API must handle both!**

```python
# In API endpoints:
course_id = request.get('course_id')  # Could be "1" or "uuid-..."

# Check if database-enabled
if db_service:
    course = db_service.get_course(str(course_id))  # TEXT UUID
else:
    # Load from JSON (INTEGER course_id)
    course = load_from_json(int(course_id))
```

### Migration Status:
- ✅ Database tables exist
- ✅ Some data already migrated
- ❌ Application NOT using database yet
- 🎯 **Next:** Update application to use database

---

## 🚀 Quick Fix Summary

**3 files to modify:**

1. **`services/quiz_service.py`** line 18-20:
```python
from services.database_service_actual import get_database_service
def __init__(self):
    self.db_service = get_database_service()
```

2. **`services/document_service.py`** line ~20:
```python
from services.database_service_actual import get_database_service
def __init__(self):
    self.db_service = get_database_service()
```

3. **`.env`** file:
```env
USE_DATABASE=True
```

**Result:** Application will start using the database! 🎉
