# 🔍 NEON DB COMPATIBILITY ANALYSIS & FIXES

**Date:** December 8, 2025  
**Issue:** Course APIs and Document Services not properly updated for Neon DB

---

## 📋 **CURRENT ISSUES IDENTIFIED**

### **1. API Endpoints (`app.py`) - NOT USING DATABASE**

#### **Problem:** Lines 187-243
```python
@app.get("/api/courses")
async def get_courses():
    """Get list of available courses."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):  # ❌ READING FROM FILE!
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
```

**Issue:** API reads from JSON file instead of Neon database.

#### **Problem:** Lines 214-243
```python
@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    """Get specific course content."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):  # ❌ READING FROM FILE!
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
```

**Issue:** Course retrieval reads from JSON file instead of querying Neon database.

---

### **2. Document Service - Partial Database Usage**

#### **Problem:** Lines 150-170, 280-290
```python
# Try database first (if enabled)
if self.db_service:
    try:
        course_id = self.db_service.create_course(course_dict, teacher_id='system')
        course_dict['course_id'] = course_id  # TEXT UUID from database
        logging.info(f"✓ Course saved to database! Course ID: {course_id}")
        return course_dict
    except Exception as e:
        # Falls back to JSON file ❌
```

**Issue:** Creates course in database but APIs don't read from it.

---

### **3. Schema Compatibility**

#### **Neon DB Schema (ACTUAL):**
```sql
Table: courses
  id                  TEXT (UUID)      PRIMARY KEY
  title               TEXT             NOT NULL
  description         TEXT             
  level               TEXT             DEFAULT 'Beginner'
  teacher_id          TEXT             NOT NULL
  is_free             BOOLEAN          DEFAULT false
  price               NUMERIC          DEFAULT 0
  currency            TEXT             DEFAULT 'INR'
  course_order        INTEGER          
  file_metadata       JSONB            
  created_at          TIMESTAMP        DEFAULT now()
  updated_at          TIMESTAMP        DEFAULT now()
  created_by          VARCHAR          

Table: modules
  id                  INTEGER          PRIMARY KEY AUTO
  course_id           TEXT             FK -> courses.id
  week                INTEGER          NOT NULL
  title               VARCHAR          NOT NULL
  description         TEXT             
  learning_objectives TEXT[]           
  order_index         INTEGER          
  created_at          TIMESTAMP        DEFAULT now()

Table: topics
  id                  INTEGER          PRIMARY KEY AUTO
  module_id           INTEGER          FK -> modules.id
  title               VARCHAR          NOT NULL
  content             TEXT             NOT NULL
  order_index         INTEGER          
  estimated_time      INTEGER          
  created_at          TIMESTAMP        DEFAULT now()
```

#### **Current Model (`database_service_actual.py`):** ✅ CORRECT
```python
class Course(Base):
    __tablename__ = 'courses'
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    description = Column(Text)
    level = Column(Text, default='Beginner')
    teacher_id = Column(Text, nullable=False)
    is_free = Column(Boolean, default=False, nullable=False)
    price = Column(Numeric, default=0)
    currency = Column(Text, default='INR')
    course_order = Column(Integer)
    file_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(String)
```

**Status:** Database models are correct! ✅

---

## ✅ **FIXES REQUIRED**

### **Fix 1: Update `/api/courses` Endpoint**

**File:** `app.py` (Lines 187-213)

**Current (WRONG):**
```python
@app.get("/api/courses")
async def get_courses():
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):  # ❌ File-based
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
```

**Should Be:**
```python
@app.get("/api/courses")
async def get_courses():
    """Get list of available courses from Neon database."""
    try:
        # Try database first
        if database_service:
            courses = database_service.get_all_courses()
            if courses:
                return courses
        
        # Fallback to JSON file if database fails
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        ...
```

---

### **Fix 2: Update `/api/course/{course_id}` Endpoint**

**File:** `app.py` (Lines 214-243)

**Current (WRONG):**
```python
@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):  # ❌ File-based
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
```

**Should Be:**
```python
@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    """Get specific course content from Neon database."""
    try:
        # Try database first
        if database_service:
            course = database_service.get_course(course_id)
            if course:
                return course
            else:
                raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
        
        # Fallback to JSON file if database fails
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        ...
```

---

### **Fix 3: Add `get_all_courses()` Method to Database Service**

**File:** `services/database_service_actual.py`

**Add this method:**
```python
def get_all_courses(self) -> List[Dict[str, Any]]:
    """Get all courses with summary information"""
    with self.get_session() as session:
        courses = session.query(Course).all()
        
        result = []
        for course in courses:
            # Count modules
            module_count = len(course.modules)
            
            result.append({
                'course_id': course.id,  # TEXT UUID
                'course_title': course.title,
                'description': course.description,
                'level': course.level,
                'is_free': course.is_free,
                'price': float(course.price) if course.price else 0,
                'currency': course.currency,
                'modules': module_count,
                'created_at': course.created_at.isoformat() if course.created_at else None
            })
        
        return result
```

---

### **Fix 4: Update Quiz Endpoints to Use Database**

**File:** `app.py` (Lines 247-279)

**Current Issue:**
```python
# Load course content
if not os.path.exists(config.OUTPUT_JSON_PATH):  # ❌ File-based
    raise HTTPException(status_code=404, detail="Course content not found")

with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
```

**Should Be:**
```python
# Load course content from database
if database_service:
    course_content = database_service.get_course(str(request.course_id))
    if not course_content:
        raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
else:
    # Fallback to JSON file
    if not os.path.exists(config.OUTPUT_JSON_PATH):
        raise HTTPException(status_code=404, detail="Course content not found")
    
    with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
```

---

## 🎯 **IMPLEMENTATION PRIORITY**

### **Priority 1: Critical (Must Fix Now)**
1. ✅ Add `get_all_courses()` method to database service
2. ✅ Update `/api/courses` endpoint
3. ✅ Update `/api/course/{course_id}` endpoint

### **Priority 2: High (Fix Soon)**
4. ✅ Update quiz endpoints to use database
5. ✅ Update course generation quiz endpoint

### **Priority 3: Medium (Optimize)**
6. Remove JSON file fallback after testing
7. Add caching for frequently accessed courses
8. Add pagination for course lists

---

## 📊 **DATA FLOW COMPARISON**

### **Current (BROKEN):**
```
User Request → API Endpoint → JSON File → Response
                  ↓
             Database Service (creates but never reads!)
```

### **Fixed (CORRECT):**
```
User Request → API Endpoint → Database Service → Neon DB → Response
                                    ↓ (fallback)
                               JSON File
```

---

## 🧪 **TESTING CHECKLIST**

After applying fixes:

- [ ] Test `GET /api/courses` returns courses from database
- [ ] Test `GET /api/course/{course_id}` with valid UUID
- [ ] Test `GET /api/course/{invalid_id}` returns 404
- [ ] Test course creation saves to database
- [ ] Test quiz generation with database course
- [ ] Test with `USE_DATABASE=False` (should use JSON files)
- [ ] Test with `USE_DATABASE=True` (should use Neon DB)

---

## 📝 **ENVIRONMENT VARIABLES**

Ensure these are set in `.env`:
```bash
# Database
USE_DATABASE=True
DATABASE_URL=postgresql://neondb_owner:...@ep-...neon.tech/neondb?sslmode=require

# Redis (Non-SSL after fix)
REDIS_USE_SSL=False
REDIS_URL=redis://default:...@redis-10925.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10925

# API Keys
OPENAI_API_KEY=...
GROQ_API_KEY=...
SARVAM_API_KEY=...
```

---

## ⚠️ **BREAKING CHANGES**

1. **Course IDs changed from INTEGER to TEXT (UUID)**
   - Old: `course_id=1, 2, 3`
   - New: `course_id="550e8400-e29b-41d4-a716-446655440000"`
   - Impact: Frontend must handle UUID strings

2. **API Response Format**
   - `course_id` now returns UUID string instead of integer
   - Database returns proper timestamp formats

---

## 🚀 **NEXT STEPS**

1. Apply fixes to `app.py`
2. Add `get_all_courses()` to `database_service_actual.py`
3. Test all endpoints
4. Update frontend to handle UUID course IDs
5. Deploy to EC2 with updated code

---

**Status:** Ready to implement fixes ✅
