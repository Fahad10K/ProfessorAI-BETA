# 🔧 Database Logic Issues - Analysis & Fixes

## Summary

After analyzing your database files, I found **7 critical issues** that need to be fixed before running the migration.

---

## ❌ CRITICAL ISSUES FOUND

### Issue #1: Schema Mismatch in `users` Table

**Problem:**
- **DATABASE_SCHEMA.md** defines: `user_id VARCHAR(100)` (no `username` column)
- **migrate_json_to_db.py** line 99 checks: `username = 'system'`

**Impact:** Migration will fail when creating system user

**Fix in `migrate_json_to_db.py`:**
```python
# WRONG (line 99-100):
self.cursor.execute("""
    SELECT id FROM users WHERE username = 'system' LIMIT 1
""")

# CORRECT:
self.cursor.execute("""
    SELECT id FROM users WHERE user_id = 'system' LIMIT 1
""")
```

---

### Issue #2: Schema Mismatch in `courses` Table

**Problem:**
- **DATABASE_SCHEMA.md** defines columns: `id, course_id, title, description, created_by, created_at, updated_at, status, metadata`
- **migrate_json_to_db.py** line 286-300 tries to insert: `title, description, level, teacher_id, is_free, price, currency`
- Missing columns: `level`, `is_free`, `price`, `currency`, `teacher_id`
- Wrong column name: uses `teacher_id` instead of `created_by`

**Impact:** Migration will fail with "column does not exist" error

**Fix Options:**

**Option A: Update Schema** (Recommended - matches your app logic)
```sql
-- Add to migrations/001_initial_schema.sql
ALTER TABLE courses ADD COLUMN level VARCHAR(50) DEFAULT 'Beginner';
ALTER TABLE courses ADD COLUMN is_free BOOLEAN DEFAULT false;
ALTER TABLE courses ADD COLUMN price NUMERIC(10,2) DEFAULT 0.00;
ALTER TABLE courses ADD COLUMN currency VARCHAR(10) DEFAULT 'INR';
ALTER TABLE courses ADD COLUMN teacher_id VARCHAR(100);
ALTER TABLE courses ADD CONSTRAINT fk_teacher FOREIGN KEY (teacher_id) REFERENCES users(user_id);
```

**Option B: Update Migration Script** (Quick fix)
```python
# Change migrate_json_to_db.py line 285-300:
self.cursor.execute("""
    INSERT INTO courses (
        course_id, title, description, created_by, status
    )
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id
""", (
    1,  # Default course_id
    course_title,
    f"Auto-generated course for quiz: {course_title}",
    self.create_system_user(),  # Use created_by instead of teacher_id
    'active'
))
```

---

### Issue #3: Missing `course_id` in Course Creation

**Problem:**
- Courses table requires `course_id INTEGER UNIQUE NOT NULL`
- Migration script line 285-300 doesn't provide `course_id` when creating courses

**Impact:** Database constraint violation

**Fix in `migrate_json_to_db.py`:**
```python
def get_or_create_course_id(self, course_title: str) -> int:  # Return INTEGER not STRING
    """Get existing course ID or create a new course"""
    try:
        # Try to find existing
        self.cursor.execute(
            "SELECT course_id FROM courses WHERE title = %s LIMIT 1",  # Get course_id, not id
            (course_title,)
        )
        result = self.cursor.fetchone()
        
        if result:
            return result[0]  # Return course_id
        
        # Generate next course_id
        self.cursor.execute("SELECT MAX(course_id) FROM courses")
        max_id = self.cursor.fetchone()[0]
        next_course_id = (max_id + 1) if max_id else 1
        
        # Create new course
        self.cursor.execute("""
            INSERT INTO courses (
                course_id, title, description, created_by, status
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING course_id
        """, (
            next_course_id,
            course_title,
            f"Auto-generated course for quiz: {course_title}",
            self.create_system_user(),
            'active'
        ))
        
        course_id = self.cursor.fetchone()[0]
        self.conn.commit()
        return course_id
```

---

### Issue #4: Type Mismatch in `migrate_quiz` Method

**Problem:**
- Method signature: `migrate_quiz(self, course_id: str, module_id: int, quiz_data: Dict)`
- But `course_id` should be `int` (references `courses.course_id INTEGER`)

**Impact:** Foreign key type mismatch

**Fix in `migrate_json_to_db.py`:**
```python
# Change line 312:
def migrate_quiz(self, course_id: int, module_id: int, quiz_data: Dict):  # course_id is int, not str
```

---

### Issue #5: Wrong Table Reference in `database_service_new.py`

**Problem:**
- **Models use mixed primary keys:**
  - `Course.course_id` vs `Course.id`
  - `Module.id` (correct)
  - `Quiz.quiz_id` vs `Quiz.id`

**Impact:** Confusing relationships, potential bugs

**Current Code (database_service_new.py line 77):**
```python
course_id = Column(Integer, ForeignKey('courses.course_id', ondelete='CASCADE'), nullable=False)
```

**This is CORRECT** - modules reference `courses.course_id` (not `courses.id`)

---

### Issue #6: Missing Password Hash for System User

**Problem:**
- Migration creates system user with plain text password: `'insecure_password_should_be_changed'`
- No password hashing

**Impact:** Security issue

**Fix in `migrate_json_to_db.py`:**
```python
def create_system_user(self) -> str:
    """Create a system user if it doesn't exist and return the user ID"""
    try:
        # Check if system user exists
        self.cursor.execute("""
            SELECT user_id FROM users WHERE user_id = 'system' LIMIT 1  # FIX: user_id not username
        """)
        result = self.cursor.fetchone()
        
        if result:
            return result[0]
            
        # Create system user
        import hashlib
        password_hash = hashlib.sha256('insecure_password'.encode()).hexdigest()  # Basic hashing
        
        self.cursor.execute("""
            INSERT INTO users (
                user_id, email, full_name, role,   # FIX: user_id not username
                password, created_at                 # ADD: password field
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id                        # FIX: user_id not id
        """, (
            'system',
            'system@professorai.local',
            'System User',
            'teacher',
            password_hash,
            datetime.now()
        ))
        
        user_id = self.cursor.fetchone()[0]
        self.conn.commit()
        return user_id
```

---

### Issue #7: Schema Missing `password` Field in `users`

**Problem:**
- DATABASE_SCHEMA.md doesn't have `password` field
- Your app likely needs authentication

**Fix:** Add to schema:
```sql
ALTER TABLE users ADD COLUMN password VARCHAR(255);
ALTER TABLE users ADD COLUMN username VARCHAR(100) UNIQUE;
```

---

## ✅ RECOMMENDED FIXES (Priority Order)

### Priority 1: Update DATABASE SCHEMA (migrations/001_initial_schema.sql)

Add these columns to make schema match migration logic:

```sql
-- Update users table
ALTER TABLE users ADD COLUMN username VARCHAR(100) UNIQUE;
ALTER TABLE users ADD COLUMN password VARCHAR(255);

-- Update courses table  
ALTER TABLE courses ADD COLUMN level VARCHAR(50) DEFAULT 'Beginner';
ALTER TABLE courses ADD COLUMN teacher_id VARCHAR(100);
ALTER TABLE courses ADD COLUMN is_free BOOLEAN DEFAULT false;
ALTER TABLE courses ADD COLUMN price NUMERIC(10,2) DEFAULT 0.00;
ALTER TABLE courses ADD COLUMN currency VARCHAR(10) DEFAULT 'INR';

-- Add foreign key
ALTER TABLE courses ADD CONSTRAINT fk_teacher 
    FOREIGN KEY (teacher_id) REFERENCES users(user_id) ON DELETE SET NULL;

-- Note: Keep created_by for compatibility or drop it
-- ALTER TABLE courses DROP COLUMN created_by;
```

### Priority 2: Fix `migrate_json_to_db.py`

All fixes listed above, specifically:
1. Line 99-100: Change `username` to `user_id`
2. Line 115-125: Update system user creation (add username, hash password)
3. Line 271-310: Fix `get_or_create_course_id` to generate proper course_id
4. Line 312: Change signature to `course_id: int`
5. Line 336-349: Ensure course_id is int when inserting quizzes

### Priority 3: Update `database_service_new.py` Models

Add missing fields to match updated schema:

```python
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False)
    username = Column(String(100), unique=True)  # ADD
    password = Column(String(255))               # ADD
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    role = Column(String(50), default='student')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB)

class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    level = Column(String(50), default='Beginner')     # ADD
    teacher_id = Column(String(100), ForeignKey('users.user_id', ondelete='SET NULL'))  # ADD
    created_by = Column(String(100), ForeignKey('users.user_id', ondelete='SET NULL'))  # KEEP for compatibility
    is_free = Column(Boolean, default=False)            # ADD
    price = Column(Numeric(10, 2), default=0.00)       # ADD
    currency = Column(String(10), default='INR')        # ADD
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    status = Column(String(50), default='active')
    metadata = Column(JSONB)
```

---

## 📊 Verification Checklist

Before running migration:

- [ ] Updated `migrations/001_initial_schema.sql` with new columns
- [ ] Run schema migration on Neon database
- [ ] Fixed all 7 issues in `migrate_json_to_db.py`
- [ ] Updated `database_service_new.py` models
- [ ] Tested migration script with sample data
- [ ] Verified foreign keys work correctly
- [ ] Checked data types match between JSON and database

---

## 🧪 Testing Plan

1. **Test Schema Changes:**
```sql
-- Verify new columns exist
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'courses';

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'users';
```

2. **Test Migration Script:**
```bash
# Run migration with verbose logging
python migrate_json_to_db.py

# Check what was migrated
SELECT * FROM users WHERE user_id = 'system';
SELECT course_id, title FROM courses;
SELECT quiz_id, title FROM quizzes LIMIT 5;
```

3. **Test API Endpoints:**
```bash
curl http://localhost:5001/api/courses
curl http://localhost:5001/api/course/1
```

---

## 🎯 Summary

**Total Issues:** 7  
**Critical Issues:** 5  
**Medium Issues:** 2  

**Estimated Fix Time:** 30-45 minutes

**Next Steps:**
1. Apply schema changes (5 min)
2. Fix migration script (15 min)
3. Update models (10 min)
4. Test migration (10 min)

**After fixes, your database will:**
✅ Match your application logic  
✅ Support all API endpoints  
✅ Handle authentication properly  
✅ Be production-ready
