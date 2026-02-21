-- ============================================================================
-- ASSESSMENT SYSTEM TABLES FOR UPLOADED NOTES
-- User uploads notes → System generates assessments → User takes assessments
-- ============================================================================

-- ============================================================================
-- 1. UPLOADED_NOTES TABLE (Store user-uploaded note content)
-- ============================================================================
CREATE TABLE uploaded_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES user_sessions(id) ON DELETE SET NULL,
    
    -- File information
    file_name TEXT NOT NULL,
    file_type TEXT,  -- e.g., 'pdf', 'docx', 'txt', 'image'
    file_size INTEGER,  -- in bytes
    file_url TEXT,  -- S3/storage URL if applicable
    
    -- Extracted content
    content TEXT NOT NULL,  -- Extracted text content from the file
    content_summary TEXT,  -- AI-generated summary of the content
    
    -- Metadata
    metadata JSONB DEFAULT '{}'::jsonb,  -- Additional file metadata
    processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,  -- If processing failed
    
    -- Timestamps
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_uploaded_notes_user_id ON uploaded_notes(user_id);
CREATE INDEX idx_uploaded_notes_session_id ON uploaded_notes(session_id);
CREATE INDEX idx_uploaded_notes_status ON uploaded_notes(processing_status);
CREATE INDEX idx_uploaded_notes_uploaded_at ON uploaded_notes(uploaded_at DESC);

COMMENT ON TABLE uploaded_notes IS 'Stores user-uploaded notes and extracted content for assessment generation';

-- ============================================================================
-- 2. ASSESSMENTS TABLE (Generated assessments from uploaded notes)
-- ============================================================================
CREATE TABLE assessments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES user_sessions(id) ON DELETE SET NULL,
    uploaded_note_id INTEGER NOT NULL REFERENCES uploaded_notes(id) ON DELETE CASCADE,
    
    -- Assessment details
    title TEXT NOT NULL,
    description TEXT,
    difficulty_level TEXT DEFAULT 'medium' CHECK (difficulty_level IN ('easy', 'medium', 'hard')),
    
    -- Assessment configuration
    total_questions INTEGER NOT NULL DEFAULT 0,
    passing_score INTEGER DEFAULT 70,  -- Percentage
    time_limit INTEGER,  -- in minutes
    
    -- Assessment metadata
    topics_covered TEXT[],  -- Array of topics/keywords from the note
    generation_prompt TEXT,  -- The prompt used to generate this assessment
    
    -- Status
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    
    -- Timestamps
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_assessments_user_id ON assessments(user_id);
CREATE INDEX idx_assessments_session_id ON assessments(session_id);
CREATE INDEX idx_assessments_note_id ON assessments(uploaded_note_id);
CREATE INDEX idx_assessments_status ON assessments(status);
CREATE INDEX idx_assessments_generated_at ON assessments(generated_at DESC);

COMMENT ON TABLE assessments IS 'AI-generated assessments based on uploaded notes';

-- ============================================================================
-- 3. ASSESSMENT_QUESTIONS TABLE (Questions for each assessment)
-- ============================================================================
CREATE TABLE assessment_questions (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    
    -- Question details
    question_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_type TEXT DEFAULT 'multiple_choice' CHECK (question_type IN ('multiple_choice', 'true_false', 'short_answer', 'essay')),
    
    -- For multiple choice questions
    options JSONB,  -- e.g., {"A": "Option 1", "B": "Option 2", "C": "Option 3", "D": "Option 4"}
    correct_answer TEXT NOT NULL,  -- e.g., "A" for MCQ, "true"/"false" for T/F, or text for short answer
    
    -- Additional information
    explanation TEXT,  -- Explanation of the correct answer
    difficulty TEXT CHECK (difficulty IN ('easy', 'medium', 'hard')),
    points INTEGER DEFAULT 1,  -- Points awarded for correct answer
    
    -- Context from note
    source_snippet TEXT,  -- The relevant snippet from the uploaded note
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_assessment_question UNIQUE(assessment_id, question_number)
);

CREATE INDEX idx_assessment_questions_assessment_id ON assessment_questions(assessment_id);
CREATE INDEX idx_assessment_questions_difficulty ON assessment_questions(difficulty);
CREATE INDEX idx_assessment_questions_type ON assessment_questions(question_type);

COMMENT ON TABLE assessment_questions IS 'Questions generated for each assessment';

-- ============================================================================
-- 4. USER_ASSESSMENT_RESPONSES TABLE (User attempts and responses)
-- ============================================================================
CREATE TABLE user_assessment_responses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES user_sessions(id) ON DELETE SET NULL,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    
    -- Attempt information
    attempt_number INTEGER NOT NULL DEFAULT 1,
    
    -- Responses
    answers JSONB NOT NULL,  -- e.g., {"1": "A", "2": "B", "3": "C", ...} or {"1": "user's text answer", ...}
    
    -- Scoring
    score INTEGER,  -- Points earned
    percentage NUMERIC(5, 2),  -- Percentage score
    total_questions INTEGER,
    correct_answers INTEGER,
    incorrect_answers INTEGER,
    unanswered INTEGER,
    
    -- Time tracking
    time_taken INTEGER,  -- in seconds
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    submitted_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    status TEXT DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'submitted', 'graded')),
    
    -- Feedback
    feedback TEXT,  -- Overall feedback on the assessment
    ai_feedback JSONB,  -- Detailed AI-generated feedback per question
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_assessment_responses_user_id ON user_assessment_responses(user_id);
CREATE INDEX idx_user_assessment_responses_session_id ON user_assessment_responses(session_id);
CREATE INDEX idx_user_assessment_responses_assessment_id ON user_assessment_responses(assessment_id);
CREATE INDEX idx_user_assessment_responses_status ON user_assessment_responses(status);
CREATE INDEX idx_user_assessment_responses_submitted_at ON user_assessment_responses(submitted_at DESC);
CREATE INDEX idx_user_assessment_responses_user_assessment ON user_assessment_responses(user_id, assessment_id);

COMMENT ON TABLE user_assessment_responses IS 'User attempts and responses to assessments';

-- ============================================================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
-- ============================================================================

CREATE TRIGGER update_uploaded_notes_updated_at BEFORE UPDATE ON uploaded_notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assessments_updated_at BEFORE UPDATE ON assessments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_assessment_responses_updated_at BEFORE UPDATE ON user_assessment_responses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- TRIGGER TO UPDATE ASSESSMENT TOTAL_QUESTIONS COUNT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_assessment_question_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE assessments 
    SET total_questions = (
        SELECT COUNT(*) 
        FROM assessment_questions 
        WHERE assessment_id = NEW.assessment_id
    )
    WHERE id = NEW.assessment_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_assessment_question_count_trigger 
AFTER INSERT ON assessment_questions
    FOR EACH ROW EXECUTE FUNCTION update_assessment_question_count();

-- ============================================================================
-- SAMPLE QUERIES FOR COMMON OPERATIONS
-- ============================================================================

-- Get all notes uploaded by a user with their assessments
-- SELECT un.*, COUNT(a.id) as assessment_count
-- FROM uploaded_notes un
-- LEFT JOIN assessments a ON a.uploaded_note_id = un.id
-- WHERE un.user_id = 1
-- GROUP BY un.id
-- ORDER BY un.uploaded_at DESC;

-- Get all assessments for a specific note
-- SELECT * FROM assessments WHERE uploaded_note_id = 5 ORDER BY generated_at DESC;

-- Get all questions for an assessment
-- SELECT * FROM assessment_questions WHERE assessment_id = 10 ORDER BY question_number ASC;

-- Get user's assessment attempts with scores
-- SELECT uar.*, a.title, a.passing_score
-- FROM user_assessment_responses uar
-- JOIN assessments a ON a.id = uar.assessment_id
-- WHERE uar.user_id = 1
-- ORDER BY uar.submitted_at DESC;

-- Get user's performance on a specific assessment
-- SELECT * FROM user_assessment_responses 
-- WHERE user_id = 1 AND assessment_id = 5 
-- ORDER BY attempt_number DESC;

-- ============================================================================
-- END OF ASSESSMENT SYSTEM SCHEMA
-- ============================================================================
