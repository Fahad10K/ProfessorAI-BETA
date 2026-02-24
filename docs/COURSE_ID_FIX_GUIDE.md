# 🔧 COURSE ID MAPPING FIX

Complete solution for UUID course_id to integer course_number mapping.

---

## 🎯 **PROBLEM**

**Current State:**
- Database has UUID course IDs: `"3e06c6aa-3f26-4622-aef3-161165dd47d0"`
- JSON fallback uses integers: `1, 2, 3, 4...`
- Hard to map and reference courses
- Quiz generation fails with FK violations

**Required State:**
- Keep UUID for database integrity (can't change due to FKs)
- Add simple integer `course_number` for easy reference
- Support both in API endpoints

---

## ✅ **SOLUTION: ADD `course_number` COLUMN**

### **Database Schema:**
```sql
courses table:
  - id (TEXT, PRIMARY KEY)        → "3e06c6aa-3f26-4622-aef3-161165dd47d0"
  - course_number (INTEGER, UNIQUE) → 1, 2, 3, 4...
  - title, description, etc.
```

---

## 📝 **WHAT WAS CHANGED**

### **1. Database Model** ✅
`services/database_service_actual.py`

```python
class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_number = Column(Integer, unique=True, nullable=False)  # NEW!
    title = Column(Text, nullable=False)
    # ... other fields
```

---

### **2. Auto-Assign Course Numbers** ✅
When creating new courses:

```python
def create_course(self, course_data, teacher_id=None):
    # Auto-assign next course_number
    result = session.execute(text(
        "SELECT COALESCE(MAX(course_number), 0) + 1 FROM courses"
    ))
    next_course_number = result.scalar()
    
    course = Course(
        id=str(uuid.uuid4()),
        course_number=next_course_number,  # Auto-incremented
        title=course_data.get('course_title'),
        # ...
    )
```

---

### **3. New Query Method** ✅
Query by simple integer:

```python
def get_course_by_number(self, course_number: int):
    """Get course by integer course_number"""
    course = session.query(Course).filter(
        Course.course_number == course_number
    ).first()
    
    if not course:
        return None
    
    return self.get_course(course.id)  # Returns full course structure
```

---

### **4. Include Both IDs in Response** ✅
```python
course_dict = {
    'course_id': course.id,              # UUID for DB operations
    'course_number': course.course_number,  # Integer for human use
    'course_title': course.title,
    'modules': [...]
}
```

---

### **5. Quiz Temperature Fix** ✅
`services/quiz_service.py`

Changed from:
```python
quiz_response = await self.llm_service.generate_response(
    quiz_prompt, 
    temperature=0.7  # ❌ Not supported by gpt-5
)
```

To:
```python
quiz_response = await self.llm_service.generate_response(
    quiz_prompt, 
    temperature=1.0  # ✅ Supported by gpt-5
)
```

---

## 🚀 **DEPLOYMENT STEPS**

### **Step 1: Run Migration**

```bash
# On local or EC2
python add_course_number_migration.py
```

**What it does:**
1. Adds `course_number` column to `courses` table
2. Assigns sequential numbers (1, 2, 3...) to existing courses based on creation date
3. Adds UNIQUE constraint
4. Sets NOT NULL constraint

**Example output:**
```
🔄 Starting migration: Add course_number column
📝 Step 1: Adding course_number column...
   ✅ Column added
📝 Step 2: Fetching existing courses...
   Found 5 courses
📝 Step 3: Assigning course numbers...
   1. Artificial Intelligence Basic - 1 -> course_number = 1
   2. Machine Learning Fundamentals -> course_number = 2
   3. Deep Learning Course -> course_number = 3
   4. NLP Basics -> course_number = 4
   5. Computer Vision 101 -> course_number = 5
   ✅ Course numbers assigned
✅ Migration completed successfully!
```

---

### **Step 2: Update Database Service**

Already done! The changes are in:
- `services/database_service_actual.py`

Upload to EC2:
```powershell
scp -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem `
  services/database_service_actual.py `
  add_course_number_migration.py `
  ubuntu@51.20.109.241:~/profai/
```

---

### **Step 3: Run Migration on EC2**

```bash
ssh -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem ubuntu@51.20.109.241

cd ~/profai
python add_course_number_migration.py
```

---

### **Step 4: Update Quiz Service**

Upload fixed quiz service:
```powershell
scp -i C:\Users\Lenovo\Downloads\my-ai-app-key.pem `
  services/quiz_service.py `
  ubuntu@51.20.109.241:~/profai/services/
```

---

### **Step 5: Restart API**

```bash
docker restart profai-api
docker logs -f profai-api
```

---

## 📊 **API USAGE**

### **Option 1: Use course_number (Recommended)**

```bash
# Generate quiz using course_number
curl -X POST http://localhost:5001/api/quiz/generate-course \
  -H 'Content-Type: application/json' \
  -d '{"course_number": 1, "module_week": 1}'
```

---

### **Option 2: Use course_id (UUID)**

```bash
# Generate quiz using course_id
curl -X POST http://localhost:5001/api/quiz/generate-course \
  -H 'Content-Type: application/json' \
  -d '{"course_id": "3e06c6aa-3f26-4622-aef3-161165dd47d0", "module_week": 1}'
```

---

## 🔍 **VERIFY MIGRATION**

After migration, check the database:

```sql
-- See all courses with both IDs
SELECT id, course_number, title, created_at 
FROM courses 
ORDER BY course_number;
```

**Expected:**
```
id                                    | course_number | title                        | created_at
--------------------------------------|---------------|------------------------------|------------
3e06c6aa-3f26-4622-aef3-161165dd47d0 | 1             | AI Basics                    | 2024-11-15
7d92e1bb-4c37-5733-b4f4-272276ee58e1 | 2             | Machine Learning             | 2024-11-20
9f13f2cc-5d48-6844-c5g5-383387ff69f2 | 3             | Deep Learning                | 2024-12-01
```

---

## 📖 **COURSE RESPONSE FORMAT**

### **Before:**
```json
{
  "course_id": "3e06c6aa-3f26-4622-aef3-161165dd47d0",
  "course_title": "AI Basics",
  "modules": [...]
}
```

### **After:**
```json
{
  "course_id": "3e06c6aa-3f26-4622-aef3-161165dd47d0",
  "course_number": 1,
  "course_title": "AI Basics",
  "modules": [...]
}
```

---

## 🧪 **TESTING**

### **Test 1: Create New Course**

New courses auto-get next number:

```python
course_id = db_service.create_course({
    "course_title": "New Course",
    "modules": [...]
}, teacher_id="teacher123")

# Check the course
course = db_service.get_course(course_id)
print(course['course_number'])  # Should be 6 (next after 5)
```

---

### **Test 2: Query by Number**

```python
# Easy query by integer
course = db_service.get_course_by_number(1)
print(course['course_title'])  # "AI Basics"
print(course['course_id'])     # "3e06c6aa-3f26..."
```

---

### **Test 3: Quiz Generation**

```bash
# Should work now!
curl -X POST http://localhost:5001/api/quiz/generate-course \
  -H 'Content-Type: application/json' \
  -d '{"course_number": 1}'
```

**Check logs:**
```
✅ Retrieved course by course_number: 1
INFO: Generating 40-question course quiz
INFO: Parsed 20 questions from part 1
INFO: Parsed 20 questions from part 2
✅ Quiz course_XXX saved to database
Generated course quiz with 40 questions
```

---

## 🔧 **JSON FALLBACK**

For JSON-based courses (no database):

`course_output.json`:
```json
{
  "course_id": 3,
  "course_number": 3,
  "course_title": "Artificial Intelligence Basic - 1",
  "modules": [...]
}
```

Both `course_id` and `course_number` can be the same integer in JSON mode.

---

## 🎯 **BENEFITS**

### **Before:**
- ❌ Hard to remember: `"3e06c6aa-3f26-4622-aef3-161165dd47d0"`
- ❌ API calls messy: `?course_id=3e06c6aa-3f26-4622-aef3-161165dd47d0`
- ❌ Confusing for users

### **After:**
- ✅ Easy to remember: `1, 2, 3, 4...`
- ✅ Clean API calls: `?course_number=1`
- ✅ Still uses UUID internally for data integrity
- ✅ No breaking changes to existing FK relationships

---

## 📋 **MIGRATION CHECKLIST**

- [ ] Upload `add_course_number_migration.py` to EC2
- [ ] Upload updated `database_service_actual.py` to EC2
- [ ] Run migration script
- [ ] Verify course numbers assigned correctly
- [ ] Upload updated `quiz_service.py` (temperature fix)
- [ ] Restart API
- [ ] Test quiz generation with course_number
- [ ] Update frontend to use course_number

---

## 🚨 **TROUBLESHOOTING**

### **Issue: Migration fails with "column already exists"**

Safe to ignore if column already exists. Or drop and re-run:

```sql
ALTER TABLE courses DROP COLUMN IF EXISTS course_number;
```

Then re-run migration.

---

### **Issue: Quiz still fails with FK violation**

Check if course exists:

```sql
SELECT id, course_number, title FROM courses WHERE course_number = 1;
```

If empty, course doesn't exist in database (only in JSON).

---

### **Issue: course_number is NULL**

Re-run migration Step 3 to assign numbers:

```sql
UPDATE courses 
SET course_number = (
    SELECT COUNT(*) + 1 
    FROM courses c2 
    WHERE c2.created_at < courses.created_at
)
WHERE course_number IS NULL;
```

---

## ✅ **SUMMARY**

1. **Added `course_number` column** - Simple integer 1, 2, 3...
2. **Auto-assigns on creation** - No manual work needed
3. **Both IDs in responses** - UUID for DB, integer for humans
4. **New query method** - `get_course_by_number(1)`
5. **Fixed quiz temperature** - Changed 0.7 to 1.0 for gpt-5
6. **Migration script ready** - Easy deployment

**Result:** Clean integer course references while maintaining database integrity! 🎉
