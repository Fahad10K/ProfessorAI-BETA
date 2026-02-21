-- Fix user_sessions table to add session_id column
-- This column is needed to store UUID session identifiers

-- Add session_id column (UUID stored as TEXT)
ALTER TABLE user_sessions 
ADD COLUMN IF NOT EXISTS session_id TEXT UNIQUE;

-- Create index on session_id for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);

-- Update existing rows to generate UUIDs if they don't have them
UPDATE user_sessions 
SET session_id = gen_random_uuid()::text 
WHERE session_id IS NULL;

-- Make session_id NOT NULL after populating existing rows
ALTER TABLE user_sessions 
ALTER COLUMN session_id SET NOT NULL;

-- Verify the change
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'user_sessions' AND column_name = 'session_id';
