# 🗄️ Database Schema Design - Microservice-Ready

## Design Principles

1. **Simple but Scalable** - Start simple, grow later
2. **Microservice-Ready** - Each table can be split into separate service
3. **Normalized** - Avoid data duplication
4. **Indexed** - Fast queries
5. **Versioned** - Track changes over time

---

## Schema Overview

```
┌─────────────────┐
│     users       │  ← User Management Microservice (Future)
└────────┬────────┘
         │
         ├──────────────────────────────────────────┐
         │                                          │
┌────────▼────────┐  ┌──────────────┐  ┌───────────▼───────┐
│    courses      │  │  job_queue   │  │  user_progress    │
│  (Main Entity)  │  │ (Job Tracking)│  │  (Learning Data)  │
└────────┬────────┘  └──────────────┘  └───────────────────┘
         │
         ├──────────────┬──────────────┬──────────────┐
         │              │              │              │
┌────────▼────────┐┌───▼──────┐┌─────▼──────┐┌──────▼──────┐
│    modules      ││  quizzes  ││ embeddings ││   files     │
│ (Course Content)││           ││ (Vectors)  ││ (Documents) │
└────────┬────────┘└───┬──────┘└────────────┘└─────────────┘
         │              │
    ┌────▼────┐    ┌───▼──────────┐
    │ topics  │    │quiz_questions│
    │(Content)│    │              │
    └─────────┘    └───┬──────────┘
                       │
                  ┌────▼─────────┐
                  │quiz_responses│
                  │(User Answers)│
                  └──────────────┘
```

---

## Core Tables (Phase 1 - NOW)

### 1. `users` - User Management
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,  -- External ID (Firebase, Auth0, etc.)
    email VARCHAR(255) UNIQUE,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'student',  -- student, teacher, admin
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB  -- Flexible field for extra data
);

CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

**Microservice Split:** User Service (handles auth, profiles)

---

### 2. `courses` - Main Course Entity
```sql
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    course_id INTEGER UNIQUE NOT NULL,  -- For backward compatibility
    title VARCHAR(500) NOT NULL,
    description TEXT,
    created_by VARCHAR(100),  -- Teacher user_id
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active',  -- active, archived, draft
    metadata JSONB,  -- Flexible for course settings
    
    -- Foreign Keys
    CONSTRAINT fk_created_by FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_courses_course_id ON courses(course_id);
CREATE INDEX idx_courses_created_by ON courses(created_by);
CREATE INDEX idx_courses_status ON courses(status);
CREATE INDEX idx_courses_created_at ON courses(created_at DESC);
```

**Microservice Split:** Course Service (manages course metadata)

---

### 3. `modules` - Course Modules (Weeks)
```sql
CREATE TABLE modules (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    week INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    learning_objectives TEXT[],  -- Array of objectives
    order_index INTEGER,  -- For custom ordering
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Foreign Keys
    CONSTRAINT fk_module_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    
    -- Unique constraint: one module per week per course
    CONSTRAINT unique_course_week UNIQUE (course_id, week)
);

CREATE INDEX idx_modules_course_id ON modules(course_id);
CREATE INDEX idx_modules_week ON modules(week);
```

**Microservice Split:** Content Service

---

### 4. `topics` - Module Topics (Sub-topics)
```sql
CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    module_id INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,  -- Main content (Markdown/HTML)
    order_index INTEGER,
    estimated_time INTEGER,  -- Minutes to complete
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Foreign Keys
    CONSTRAINT fk_topic_module FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
);

CREATE INDEX idx_topics_module_id ON topics(module_id);
CREATE INDEX idx_topics_order ON topics(order_index);
```

**Microservice Split:** Content Service

---

### 5. `quizzes` - Quiz Metadata
```sql
CREATE TABLE quizzes (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) UNIQUE NOT NULL,
    course_id INTEGER NOT NULL,
    module_id INTEGER,  -- NULL for course-wide quizzes
    title VARCHAR(500) NOT NULL,
    description TEXT,
    quiz_type VARCHAR(50) DEFAULT 'module',  -- module, course, practice
    passing_score INTEGER DEFAULT 70,  -- Percentage
    time_limit INTEGER,  -- Minutes (NULL = no limit)
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Foreign Keys
    CONSTRAINT fk_quiz_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_quiz_module FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
);

CREATE INDEX idx_quizzes_quiz_id ON quizzes(quiz_id);
CREATE INDEX idx_quizzes_course_id ON quizzes(course_id);
CREATE INDEX idx_quizzes_module_id ON quizzes(module_id);
```

**Microservice Split:** Assessment Service

---

### 6. `quiz_questions` - Individual Questions
```sql
CREATE TABLE quiz_questions (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) NOT NULL,
    question_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL,  -- {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_answer CHAR(1) NOT NULL,  -- A, B, C, or D
    explanation TEXT,  -- Why this answer is correct
    difficulty VARCHAR(20),  -- easy, medium, hard
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Foreign Keys
    CONSTRAINT fk_question_quiz FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
    
    -- Unique constraint
    CONSTRAINT unique_quiz_question UNIQUE (quiz_id, question_number)
);

CREATE INDEX idx_quiz_questions_quiz_id ON quiz_questions(quiz_id);
```

**Microservice Split:** Assessment Service

---

### 7. `quiz_responses` - User Quiz Submissions
```sql
CREATE TABLE quiz_responses (
    id SERIAL PRIMARY KEY,
    quiz_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    answers JSONB NOT NULL,  -- {"1": "A", "2": "B", ...}
    score INTEGER,  -- Percentage
    total_questions INTEGER,
    correct_answers INTEGER,
    submitted_at TIMESTAMP DEFAULT NOW(),
    time_taken INTEGER,  -- Seconds
    
    -- Foreign Keys
    CONSTRAINT fk_response_quiz FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
    CONSTRAINT fk_response_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_quiz_responses_quiz_id ON quiz_responses(quiz_id);
CREATE INDEX idx_quiz_responses_user_id ON quiz_responses(user_id);
CREATE INDEX idx_quiz_responses_submitted_at ON quiz_responses(submitted_at DESC);
```

**Microservice Split:** Assessment Service

---

### 8. `job_queue` - Background Job Tracking
```sql
CREATE TABLE job_queue (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) UNIQUE NOT NULL,
    task_id VARCHAR(100),  -- Celery task ID
    job_type VARCHAR(50) NOT NULL,  -- pdf_processing, quiz_generation
    status VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,  -- 0-100
    message TEXT,
    result JSONB,  -- Job result data
    error TEXT,  -- Error message if failed
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Foreign Keys
    CONSTRAINT fk_job_user FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_job_queue_job_id ON job_queue(job_id);
CREATE INDEX idx_job_queue_task_id ON job_queue(task_id);
CREATE INDEX idx_job_queue_status ON job_queue(status);
CREATE INDEX idx_job_queue_created_by ON job_queue(created_by);
CREATE INDEX idx_job_queue_created_at ON job_queue(created_at DESC);
```

**Microservice Split:** Job Service (handles background tasks)

---

### 9. `source_files` - Uploaded Documents
```sql
CREATE TABLE source_files (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(100) UNIQUE NOT NULL,
    course_id INTEGER NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000),  -- S3 path or local path
    file_size BIGINT,  -- Bytes
    file_type VARCHAR(50),  -- pdf, docx, txt
    upload_date TIMESTAMP DEFAULT NOW(),
    uploaded_by VARCHAR(100),
    checksum VARCHAR(64),  -- SHA-256 hash
    
    -- Foreign Keys
    CONSTRAINT fk_file_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_file_user FOREIGN KEY (uploaded_by) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_source_files_file_id ON source_files(file_id);
CREATE INDEX idx_source_files_course_id ON source_files(course_id);
CREATE INDEX idx_source_files_uploaded_by ON source_files(uploaded_by);
```

**Microservice Split:** File Service (handles uploads, storage)

---

### 10. `user_progress` - Learning Progress Tracking
```sql
CREATE TABLE user_progress (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    course_id INTEGER NOT NULL,
    module_id INTEGER,
    topic_id INTEGER,
    status VARCHAR(50) DEFAULT 'not_started',  -- not_started, in_progress, completed
    progress_percentage INTEGER DEFAULT 0,  -- 0-100
    last_accessed TIMESTAMP DEFAULT NOW(),
    completion_date TIMESTAMP,
    
    -- Foreign Keys
    CONSTRAINT fk_progress_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_progress_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
    CONSTRAINT fk_progress_module FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
    CONSTRAINT fk_progress_topic FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
    
    -- Unique constraint: one progress record per user-course-module-topic
    CONSTRAINT unique_user_progress UNIQUE (user_id, course_id, module_id, topic_id)
);

CREATE INDEX idx_user_progress_user_id ON user_progress(user_id);
CREATE INDEX idx_user_progress_course_id ON user_progress(course_id);
CREATE INDEX idx_user_progress_status ON user_progress(status);
```

**Microservice Split:** Analytics Service

---

## Advanced Tables (Phase 2 - LATER)

### 11. `chat_history` - Student-AI Conversations
```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    course_id INTEGER,
    session_id VARCHAR(100) NOT NULL,
    message_type VARCHAR(20) NOT NULL,  -- user, assistant
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB,  -- Context, sources, etc.
    
    CONSTRAINT fk_chat_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX idx_chat_history_session_id ON chat_history(session_id);
CREATE INDEX idx_chat_history_timestamp ON chat_history(timestamp DESC);
```

**Microservice Split:** Chat Service

---

### 12. `embeddings` - Vector Embeddings (Optional - ChromaDB is better)
```sql
-- Only use if NOT using ChromaDB Cloud
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    chunk_id VARCHAR(100) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Requires pgvector extension
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_embedding_course FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- Vector similarity index (requires pgvector)
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops);
```

**Note:** We're using **ChromaDB Cloud** so we DON'T need this table!

---

## Migration Script

### Complete Migration SQL

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "pgvector";  -- Only if using embeddings table

-- Create all tables in order (respecting foreign keys)

-- 1. Users (independent)
CREATE TABLE users (...);

-- 2. Courses (depends on users)
CREATE TABLE courses (...);

-- 3. Modules (depends on courses)
CREATE TABLE modules (...);

-- 4. Topics (depends on modules)
CREATE TABLE topics (...);

-- 5. Quizzes (depends on courses, modules)
CREATE TABLE quizzes (...);

-- 6. Quiz Questions (depends on quizzes)
CREATE TABLE quiz_questions (...);

-- 7. Quiz Responses (depends on quizzes, users)
CREATE TABLE quiz_responses (...);

-- 8. Job Queue (depends on users)
CREATE TABLE job_queue (...);

-- 9. Source Files (depends on courses, users)
CREATE TABLE source_files (...);

-- 10. User Progress (depends on users, courses, modules, topics)
CREATE TABLE user_progress (...);

-- 11. Chat History (depends on users)
-- CREATE TABLE chat_history (...);  -- Phase 2
```

---

## Microservice Boundaries (Future)

### Service 1: User Service
- Tables: `users`
- Responsibility: Authentication, user profiles
- API: `/api/users/*`

### Service 2: Course Service
- Tables: `courses`, `modules`, `topics`
- Responsibility: Course CRUD, content management
- API: `/api/courses/*`, `/api/modules/*`

### Service 3: Assessment Service
- Tables: `quizzes`, `quiz_questions`, `quiz_responses`
- Responsibility: Quiz generation, grading
- API: `/api/quizzes/*`, `/api/assessments/*`

### Service 4: Job Service
- Tables: `job_queue`
- Responsibility: Background job management
- API: `/api/jobs/*`

### Service 5: File Service
- Tables: `source_files`
- Responsibility: File uploads, S3 storage
- API: `/api/files/*`

### Service 6: Analytics Service
- Tables: `user_progress`, aggregation tables
- Responsibility: Learning analytics, reports
- API: `/api/analytics/*`

### Service 7: Chat Service
- Tables: `chat_history`
- Responsibility: AI chat, RAG
- API: `/api/chat/*`

---

## Data Flow Example

### Uploading PDF & Generating Course

```
1. Teacher uploads PDF
   → POST /api/upload-pdfs
   → Creates job in job_queue (status: pending)
   → Saves file to source_files
   → Returns job_id

2. Celery worker picks up job
   → Updates job_queue (status: processing)
   → Processes PDF
   → Generates content

3. Worker saves results
   → Creates course in courses table
   → Creates modules in modules table
   → Creates topics in topics table
   → Saves embeddings to ChromaDB Cloud
   → Updates job_queue (status: completed)

4. Teacher checks status
   → GET /api/jobs/{job_id}
   → Returns course_id

5. Students access course
   → GET /api/courses/{course_id}
   → Joins courses + modules + topics
   → Returns full course structure
```

---

## Query Optimization

### Common Queries

```sql
-- Get all courses for a teacher
SELECT * FROM courses 
WHERE created_by = 'teacher_123' 
ORDER BY created_at DESC;

-- Get full course with modules and topics
SELECT 
    c.*,
    json_agg(
        json_build_object(
            'id', m.id,
            'week', m.week,
            'title', m.title,
            'topics', (
                SELECT json_agg(
                    json_build_object(
                        'id', t.id,
                        'title', t.title,
                        'content', t.content
                    )
                )
                FROM topics t
                WHERE t.module_id = m.id
                ORDER BY t.order_index
            )
        )
        ORDER BY m.week
    ) as modules
FROM courses c
LEFT JOIN modules m ON c.course_id = m.course_id
WHERE c.course_id = 1
GROUP BY c.id;

-- Get student progress for a course
SELECT 
    c.title as course_title,
    COUNT(DISTINCT m.id) as total_modules,
    COUNT(DISTINCT CASE WHEN up.status = 'completed' THEN m.id END) as completed_modules,
    ROUND(AVG(up.progress_percentage), 2) as overall_progress
FROM courses c
LEFT JOIN modules m ON c.course_id = m.course_id
LEFT JOIN user_progress up ON up.module_id = m.id AND up.user_id = 'student_456'
WHERE c.course_id = 1
GROUP BY c.id;
```

---

## Summary

**Core Tables (Phase 1):** 10 tables
- users, courses, modules, topics
- quizzes, quiz_questions, quiz_responses
- job_queue, source_files, user_progress

**Future Tables (Phase 2):** 2+ tables
- chat_history
- analytics tables
- notifications, etc.

**Microservice-Ready:**
- Each table group can become a separate service
- Foreign keys can be replaced with API calls
- JSONB fields allow flexibility

**Simple but Powerful:**
- Normalized structure
- Indexed for performance
- JSONB for flexibility
- Easy to query, easy to scale

---

## Next Step

Create migration script → `migrations/001_initial_schema.sql`
