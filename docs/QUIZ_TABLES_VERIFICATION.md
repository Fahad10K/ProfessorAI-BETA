# Quiz Tables Verification Report

## 📊 SCHEMA VS IMPLEMENTATION ANALYSIS

---

## ✅ TABLE 1: `quizzes` - PROPERLY IMPLEMENTED

### Schema Definition (from DATABASE_SCHEMA.md):
```sql
CREATE TABLE quizzes (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) UNIQUE NOT NULL,
    course_id INTEGER NOT NULL,
    module_id INTEGER,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    quiz_type VARCHAR(50) DEFAULT 'module',
    passing_score INTEGER DEFAULT 70,
    time_limit INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_quiz_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_quiz_module FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
);
```

### SQLAlchemy Model (database_service_actual.py):
```python
class Quiz(Base):
    __tablename__ = 'quizzes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, unique=True, nullable=False)
    course_id = Column(Text, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)  # TEXT UUID
    module_id = Column(Integer, ForeignKey('modules.id', ondelete='SET NULL'))
    title = Column(String, nullable=False)
    description = Column(Text)
    quiz_type = Column(String, default='module')
    passing_score = Column(Integer, default=70)
    time_limit = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
```

### ✅ Implementation Status:
- **PROPERLY STORED** via `database_service.create_quiz()`
- Used in: `quiz_service.py` → `_store_quiz()` → `db_service.create_quiz()`
- Falls back to JSON if database fails

---

## ✅ TABLE 2: `quiz_questions` - PROPERLY IMPLEMENTED (JUST FIXED)

### Schema Definition:
```sql
CREATE TABLE quiz_questions (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) NOT NULL,
    question_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_answer CHAR(1) NOT NULL,
    explanation TEXT,
    difficulty VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_question_quiz FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
    CONSTRAINT unique_quiz_question UNIQUE (quiz_id, question_number)
);
```

### SQLAlchemy Model:
```python
class QuizQuestion(Base):
    __tablename__ = 'quiz_questions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, ForeignKey('quizzes.quiz_id', ondelete='CASCADE'), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=False)
    correct_answer = Column(String(1), nullable=False)
    explanation = Column(Text)
    difficulty = Column(String)
    created_at = Column(DateTime, default=datetime.now)
```

### ✅ Implementation Status:
- **PROPERLY STORED** via `database_service.create_quiz()`
- Questions stored in loop with sequential `question_number` (1, 2, 3...20)
- **FIXED** unique constraint issue today

---

## ❌ TABLE 3: `quiz_responses` - **NOT BEING USED!**

### Schema Definition:
```sql
CREATE TABLE quiz_responses (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    answers JSONB NOT NULL,
    score INTEGER,
    total_questions INTEGER,
    correct_answers INTEGER,
    submitted_at TIMESTAMP DEFAULT NOW(),
    time_taken INTEGER,
    
    CONSTRAINT fk_response_quiz FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
    CONSTRAINT fk_response_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

### SQLAlchemy Model EXISTS:
```python
class QuizResponse(Base):
    __tablename__ = 'quiz_responses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, ForeignKey('quizzes.quiz_id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Text, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    answers = Column(JSONB, nullable=False)
    score = Column(Integer)
    total_questions = Column(Integer)
    correct_answers = Column(Integer)
    submitted_at = Column(DateTime, default=datetime.now)
    time_taken = Column(Integer)
```

### ❌ Implementation Status:
- **MODEL EXISTS BUT NOT USED!**
- Current implementation: `quiz_service._store_submission_result()` saves to **JSON files**
- Location: `storage/quiz_answers/{quiz_id}_{user_id}_submission.json`
- **NO DATABASE METHOD EXISTS** to save quiz submissions

---

## 🔴 CRITICAL ISSUES FOUND

### Issue 1: Quiz Submissions Not Saved to Database
**Problem:**
```python
# quiz_service.py line 509-530
def _store_submission_result(self, submission: QuizSubmission, result: QuizResult):
    """Store quiz submission and result."""
    try:
        submission_data = {
            "submission": submission.dict(),
            "result": result.dict(),
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        # ❌ SAVING TO JSON FILE INSTEAD OF DATABASE!
        submission_file = os.path.join(
            self.answers_storage_dir, 
            f"{submission.quiz_id}_{submission.user_id}_submission.json"
        )
        
        with open(submission_file, 'w', encoding='utf-8') as f:
            json.dump(submission_data, f, indent=2, ensure_ascii=False)
```

**Impact:**
- ✅ Quizzes are created in database
- ✅ Questions are created in database
- ❌ **User submissions are NOT in database** (only JSON files)
- ❌ Cannot query user quiz history from database
- ❌ Cannot run analytics on quiz performance
- ❌ `quiz_responses` table remains empty

---

## ✅ FIXES NEEDED

### 1. Add Database Method for Quiz Submissions

**File:** `services/database_service_actual.py`

Add this method after `get_quiz()`:

```python
def save_quiz_response(self, response_data: Dict[str, Any]) -> int:
    """Save user quiz submission to database"""
    with self.get_session() as session:
        response = QuizResponse(
            quiz_id=response_data['quiz_id'],
            user_id=response_data['user_id'],
            answers=response_data['answers'],  # JSONB
            score=response_data.get('score'),
            total_questions=response_data.get('total_questions'),
            correct_answers=response_data.get('correct_answers'),
            time_taken=response_data.get('time_taken')
        )
        session.add(response)
        session.commit()
        logger.info(f"✅ Saved quiz response: {response.quiz_id} for user {response.user_id}")
        return response.id

def get_user_quiz_responses(self, user_id: str, quiz_id: str = None) -> List[Dict[str, Any]]:
    """Get user's quiz submission history"""
    with self.get_session() as session:
        query = session.query(QuizResponse).filter(QuizResponse.user_id == user_id)
        
        if quiz_id:
            query = query.filter(QuizResponse.quiz_id == quiz_id)
        
        responses = query.order_by(QuizResponse.submitted_at.desc()).all()
        
        return [{
            'id': r.id,
            'quiz_id': r.quiz_id,
            'user_id': r.user_id,
            'answers': r.answers,
            'score': r.score,
            'total_questions': r.total_questions,
            'correct_answers': r.correct_answers,
            'submitted_at': r.submitted_at.isoformat() if r.submitted_at else None,
            'time_taken': r.time_taken
        } for r in responses]
```

### 2. Update Quiz Service to Use Database

**File:** `services/quiz_service.py`

Update `_store_submission_result()`:

```python
def _store_submission_result(self, submission: QuizSubmission, result: QuizResult):
    """Store quiz submission and result."""
    try:
        # Try database first
        if self.db_service:
            try:
                response_data = {
                    'quiz_id': submission.quiz_id,
                    'user_id': submission.user_id,
                    'answers': submission.answers,  # Dict to JSONB
                    'score': result.score,
                    'total_questions': result.total_questions,
                    'correct_answers': result.score,  # Same as score
                    'time_taken': None  # Can add later
                }
                self.db_service.save_quiz_response(response_data)
                logging.info(f"✅ Quiz response saved to database for user {submission.user_id}")
                return  # Success - exit early
            except Exception as e:
                logging.warning(f"Failed to save quiz response to database, using JSON fallback: {e}")
        
        # Fallback to JSON files (original logic)
        submission_data = {
            "submission": submission.dict(),
            "result": result.dict(),
            "submitted_at": datetime.utcnow().isoformat()
        }
        
        submission_file = os.path.join(
            self.answers_storage_dir, 
            f"{submission.quiz_id}_{submission.user_id}_submission.json"
        )
        
        with open(submission_file, 'w', encoding='utf-8') as f:
            json.dump(submission_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Stored submission result to JSON for user {submission.user_id}")
        
    except Exception as e:
        logging.error(f"Error storing submission result: {e}")
```

---

## 📊 SUMMARY

| Table | Schema | Model | Create Method | Read Method | Status |
|-------|--------|-------|---------------|-------------|--------|
| `quizzes` | ✅ | ✅ | ✅ `create_quiz()` | ✅ `get_quiz()` | **WORKING** |
| `quiz_questions` | ✅ | ✅ | ✅ (in `create_quiz()`) | ✅ (in `get_quiz()`) | **WORKING** |
| `quiz_responses` | ✅ | ✅ | ❌ **MISSING** | ❌ **MISSING** | **NOT USED** |

---

## 🚀 ACTION ITEMS

1. **Add `save_quiz_response()` method** to `database_service_actual.py`
2. **Add `get_user_quiz_responses()` method** to `database_service_actual.py`
3. **Update `_store_submission_result()`** in `quiz_service.py` to use database
4. **Test quiz submission** to verify data goes to database
5. **Optional:** Create API endpoint to retrieve user quiz history

---

## 🧪 TESTING

After fixes, test:

```python
# Submit a quiz
submission = {
    "quiz_id": "module_1_xxxxx",
    "user_id": "test_user_123",
    "answers": {
        "module_1_xxxxx_q1": "A",
        "module_1_xxxxx_q2": "B",
        # ... all 20 answers
    }
}

# Should save to quiz_responses table
# Verify in database:
SELECT * FROM quiz_responses WHERE user_id = 'test_user_123';
```

**Expected:**
- ✅ Quiz submission saved to `quiz_responses` table
- ✅ Answers stored as JSONB
- ✅ Score calculated and saved
- ✅ Timestamp recorded

---

## 🎯 CURRENT STATE

**What's Working:**
- ✅ Quiz creation (quizzes table)
- ✅ Question storage (quiz_questions table) with sequential numbering
- ✅ Quiz generation with LLM
- ✅ Quiz retrieval for display

**What's Missing:**
- ❌ Quiz submission storage in database
- ❌ User quiz history tracking
- ❌ Analytics on quiz performance
- ❌ `quiz_responses` table is empty/unused

**Fix Priority:** 🔴 **HIGH** - This breaks the learning analytics and user progress tracking.
