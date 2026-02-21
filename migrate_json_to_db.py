"""
Migrate Existing JSON Data to PostgreSQL
Converts data/courses/course_output.json to database tables

Usage:
    python migrate_json_to_db.py
"""

import os
import sys
import json
import shutil
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class JSONToDBMigrator:
    """Migrates JSON course data to PostgreSQL"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(self.database_url)
            self.cursor = self.conn.cursor()
            logging.info("✅ Connected to PostgreSQL database")
        except Exception as e:
            logging.error(f"❌ Failed to connect to database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logging.info("Database connection closed")
    
    def backup_json_files(self):
        """Create backup of JSON files"""
        backup_dir = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            os.makedirs(backup_dir, exist_ok=True)
            
            # Backup courses
            if os.path.exists("data/courses"):
                shutil.copytree("data/courses", f"{backup_dir}/courses")
                logging.info(f"✅ Backed up courses to {backup_dir}/courses")
            
            # Backup quizzes
            if os.path.exists("data/quizzes"):
                shutil.copytree("data/quizzes", f"{backup_dir}/quizzes")
                logging.info(f"✅ Backed up quizzes to {backup_dir}/quizzes")
            
            # Backup quiz answers
            if os.path.exists("data/quiz_answers"):
                shutil.copytree("data/quiz_answers", f"{backup_dir}/quiz_answers")
                logging.info(f"✅ Backed up quiz answers to {backup_dir}/quiz_answers")
            
            return backup_dir
            
        except Exception as e:
            logging.error(f"❌ Failed to create backup: {e}")
            raise
    
    def load_json_data(self, filepath: str) -> Any:
        """Load JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logging.info(f"✅ Loaded {filepath}")
            return data
        except Exception as e:
            logging.error(f"❌ Failed to load {filepath}: {e}")
            return None
    
    def create_system_user(self) -> str:
        """Create a system user if it doesn't exist and return the user ID"""
        try:
            # Check if system user exists
            self.cursor.execute("""
                SELECT user_id FROM users WHERE user_id = 'system' LIMIT 1
            """)
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
                
            # Create system user if not exists
            import hashlib
            password_hash = hashlib.sha256('insecure_password'.encode()).hexdigest()
            
            self.cursor.execute("""
                INSERT INTO users (
                    user_id, email, full_name, role, 
                    created_at, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id
            """, (
                'system',
                'system@professorai.local',
                'System User',
                'teacher',
                datetime.now(),
                True
            ))
            
            user_id = self.cursor.fetchone()[0]
            self.conn.commit()
            logging.info(f"✅ Created system user with ID: {user_id}")
            return user_id
            
        except Exception as e:
            logging.error(f"❌ Failed to create system user: {e}")
            self.conn.rollback()
            raise
    
    def migrate_course(self, course_data: Dict) -> int:
        """
        Migrate a single course to database
        Returns the course_id of the inserted course
        """
        try:
            # Get or create system user for teacher_id
            teacher_id = "277f2d34-8307-4759-9f23-618d7b96e8b5"
            
            # Extract course metadata
            title = course_data.get('course_title', 'Untitled Course')
            description = course_data.get('description', '')
            json_course_id = course_data.get('id', 1)
            created_at = datetime.now()
            updated_at = datetime.now()
            json_course_id = str(uuid.uuid4())
            # Insert course with course_id
            self.cursor.execute("""
                INSERT INTO courses (
                    id, title, description, teacher_id, 
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    updated_at = EXCLUDED.updated_at
                RETURNING id;
            """, (
                json_course_id,
                title,
                description,
                teacher_id,  # Use the system user's ID as created_by
                
                created_at,
                updated_at
            ))
            
            course_id = self.cursor.fetchone()[0]
            self.conn.commit()
            
            logging.info(f"✅ Migrated course: {title} (ID: {course_id})")
            return course_id
            
        except Exception as e:
            logging.error(f"❌ Failed to migrate course: {e}")
            self.conn.rollback()
            raise
    
    def migrate_modules(self, course_id: str, modules: List[Dict]):
        """Migrate course modules"""
        try:
            for module in modules:
                week = module.get('week', 1)
                title = module.get('title', f'Week {week}')
                description = module.get('description', '')
                objectives = module.get('learning_objectives', [])
                
                # Insert module
                self.cursor.execute("""
                    INSERT INTO modules (
                        course_id, week, title, description, 
                        learning_objectives, order_index, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        learning_objectives = EXCLUDED.learning_objectives
                    RETURNING id
                """, (
                    course_id,
                    week,
                    title,
                    description,
                    objectives if objectives else [],
                    week,
                    datetime.now()
                ))
                
                module_id = self.cursor.fetchone()[0]
                
                # Migrate topics for this module
                sub_topics = module.get('sub_topics', [])
                self.migrate_topics(module_id, sub_topics)
                
                # Migrate quizzes for this module if they exist
                if 'quizzes' in module:
                    for quiz in module['quizzes']:
                        self.migrate_quiz(course_id, module_id, quiz)
                
                logging.info(f"  ✅ Migrated module: Week {week} - {title}")
            
            self.conn.commit()
            
        except Exception as e:
            logging.error(f"❌ Failed to migrate modules: {e}")
            self.conn.rollback()
            raise
    
    def migrate_topics(self, module_id: int, topics: List[Dict]):
        """Migrate module topics"""
        try:
            for idx, topic in enumerate(topics):
                title = topic.get('title', f'Topic {idx + 1}')
                content = topic.get('content', '')
                order_index = topic.get('order_index', idx + 1)
                estimated_time = topic.get('estimated_time')
                
                # Insert topic
                self.cursor.execute("""
                    INSERT INTO topics (
                        module_id, title, content, 
                        order_index, estimated_time, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    module_id,
                    title,
                    content,
                    order_index,
                    estimated_time,
                    datetime.now()
                ))
                
                topic_id = self.cursor.fetchone()[0]
                logging.debug(f"    ✅ Migrated topic: {title}")
                
            self.conn.commit()
            
        except Exception as e:
            logging.error(f"❌ Failed to migrate topics: {e}")
            self.conn.rollback()
            raise
            
    def get_or_create_course_id(self, course_title: str) -> int:
        """Get existing course ID or create a new course if it doesn't exist"""
        try:
            # Try to find an existing course
            self.cursor.execute(
                "SELECT id FROM courses WHERE title = %s LIMIT 1",
                (course_title,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            
            # Generate next course_id
            self.cursor.execute("SELECT MAX(id) FROM courses")
            max_id = self.cursor.fetchone()[0]
            next_course_id = (max_id + 1) if max_id else 1
                
            # Create a new course if not found
            self.cursor.execute("""
                INSERT INTO courses (
                    id, title, description, created_by, status
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                next_course_id,
                course_title,
                f"Auto-generated course for quiz: {course_title}",
                self.create_system_user(),
                'active'
            ))
            
            course_id = self.cursor.fetchone()[0]
            self.conn.commit()
            logging.info(f"✅ Created new course for quiz: {course_title} (ID: {course_id})")
            return course_id
            
        except Exception as e:
            self.conn.rollback()
            logging.error(f"❌ Failed to get or create course: {e}")
            raise

    def migrate_quiz(self, course_id: int, module_id: int, quiz_data: Dict):
        """Migrate a quiz and its questions"""
        try:
            # Start a transaction
            self.conn.rollback()  # Ensure we start fresh
            
            quiz_id = quiz_data.get('quiz_id', str(uuid.uuid4()))
            title = quiz_data.get('title', 'Untitled Quiz')
            description = quiz_data.get('description', '')
            quiz_type = quiz_data.get('type', 'module')
            
            # Convert passing_score to int, default to 70 if not provided or invalid
            try:
                passing_score = int(quiz_data.get('passing_score', 70))
            except (ValueError, TypeError):
                passing_score = 70
                
            # Convert time_limit to int, default to None if not provided or invalid
            try:
                time_limit = int(quiz_data.get('time_limit', 0)) if quiz_data.get('time_limit') else None
            except (ValueError, TypeError):
                time_limit = None
            
            # First, insert the quiz
            self.cursor.execute("""
                INSERT INTO quizzes (
                    quiz_id, course_id, module_id, title, 
                    description, quiz_type, passing_score, 
                    time_limit, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, quiz_id
            """, (
                quiz_id,
                course_id,
                module_id,
                title,
                description,
                quiz_type,
                passing_score,
                time_limit,
                datetime.now()
            ))
            
            # Get the database ID of the inserted quiz
            result = self.cursor.fetchone()
            if not result:
                raise Exception("Failed to insert quiz")
                
            quiz_db_id, inserted_quiz_id = result
            
            # Commit the quiz insertion first
            self.conn.commit()
            
            # Now migrate the questions
            questions = quiz_data.get('questions', [])
            if questions:
                self.migrate_quiz_questions(inserted_quiz_id, questions)
            
            logging.info(f"  ✅ Migrated quiz: {title} (ID: {inserted_quiz_id})")
            return inserted_quiz_id
            
        except Exception as e:
            logging.error(f"❌ Failed to migrate quiz '{title}': {e}")
            self.conn.rollback()
            raise

    def migrate_quiz_questions(self, quiz_db_id: str, questions: List[Dict]):
        """Migrate quiz questions for a quiz"""
        for question_data in questions:
            try:
                question_text = question_data.get('question', '')
                options = question_data.get('options', [])
                correct_answer = question_data.get('correct_answer', '')
                explanation = question_data.get('explanation', '')
                difficulty = question_data.get('difficulty', 'medium')
                question_number = question_data.get('question_number', 1)
                
                # Make sure options is a JSON object with A, B, C, D keys if it's a list
                options_dict = {}
                if isinstance(options, list):
                    for i, option in enumerate(options):
                        options_dict[chr(65 + i)] = str(option)  # Convert to A, B, C, D keys
                else:
                    options_dict = options or {}
                
                # Ensure correct_answer is a single character (A, B, C, D)
                if isinstance(correct_answer, int) and 0 <= correct_answer < len(options):
                    correct_answer = chr(65 + correct_answer)  # Convert index to A, B, C, D
                elif isinstance(correct_answer, str) and correct_answer.isdigit():
                    idx = int(correct_answer)
                    if 0 <= idx < len(options):
                        correct_answer = chr(65 + idx)
                
                # Convert correct_answer to uppercase and ensure it's a single character
                if correct_answer:
                    correct_answer = str(correct_answer).upper()[0]
                
                # Insert the question
                self.cursor.execute("""
                    INSERT INTO quiz_questions (
                        quiz_id, question_number, question_text, 
                        options, correct_answer, 
                        explanation, difficulty, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    quiz_db_id,  # Using the database ID of the quiz
                    question_number,
                    question_text,
                    json.dumps(options_dict) if options_dict else '{}',
                    correct_answer,
                    explanation,
                    difficulty,
                    datetime.now()
                ))
                
                logging.debug(f"  ➕ Migrated question: {question_text[:50]}...")
                
            except Exception as e:
                logging.error(f"❌ Failed to migrate question: {e}")
                self.conn.rollback()
                raise

    def run_migration(self):
        """Run complete migration"""
        try:
            # Step 1: Creating backup...
            logging.info("\n📦 Step 1: Creating backup...")
            self.backup_json_files()
            
            # Step 2: Connecting to database...
            logging.info("\n🔌 Step 2: Connecting to database...")
            self.connect()
            
            # Step 3: Create system user if not exists
            # logging.info("\n👤 Step 3: Creating system user...")
            # system_user_id = self.create_system_user()
            
            
            # Step 4: Migrating courses... (Commented out as already completed)
            logging.info("\n📚 Step 4: Migrating courses...")
            courses_data = self.load_json_data(r"C:\Users\Lenovo\OneDrive\Documents\profainew\ProfessorAI_0.2_AWS_Ready\Prof_AI\course_output.json")
            if courses_data:
                for course_data in courses_data:
                    course_id = self.migrate_course(course_data)
                    
                    # Migrate modules for the course
                    modules = course_data.get('modules', [])
                    if modules:
                        self.migrate_modules(course_id, modules)
                logging.info(f"✅ Migrated {len(courses_data)} course(s)")
            else:
                logging.warning("⚠️  No course data found in data/courses/course_output.json")
            """
            
            # Step 5: Migrating quizzes...
            logging.info("\n📝 Step 5: Migrating quizzes...")
            quizzes_dir = "data/quizzes"
            
            if os.path.exists(quizzes_dir):
                quiz_files = [f for f in os.listdir(quizzes_dir) if f.endswith('.json')]
                migrated_count = 0
                
                for quiz_file in quiz_files:
                    try:
                        quiz_path = os.path.join(quizzes_dir, quiz_file)
                        quiz_data = self.load_json_data(quiz_path)
                        
                        if not quiz_data:
                            logging.warning(f"⚠️  Empty or invalid quiz data in {quiz_file}")
                            continue
                            
                        quiz_id = quiz_file.replace('.json', '')
                        quiz_data['quiz_id'] = quiz_id
                        
                        # Extract course title from filename or use default
                        course_title = quiz_data.get('course_title', 
                                                  os.path.splitext(quiz_file)[0].replace('_', ' ').title())
                        quiz_data['course_title'] = course_title
                        
                        # Get or create course
                        course_id = self.get_or_create_course_id(course_title)
                        
                        # Get module_id if exists, or use None for standalone quizzes
                        module_id = quiz_data.get('module_id')
                        
                        logging.info(f"Processing quiz: {quiz_id} for course: {course_title}")
                        
                        # Migrate the quiz
                        self.migrate_quiz(course_id, module_id, quiz_data)
                        migrated_count += 1
                        
                    except Exception as e:
                        logging.error(f"❌ Failed to process {quiz_file}: {e}")
                        self.conn.rollback()
                        continue
                
                logging.info(f"✅ Migrated {migrated_count}/{len(quiz_files)} quiz(zes)")
            else:
                logging.warning(f"⚠️  No quizzes directory found at {quizzes_dir}")
            
            """
            # Step 6: Verify migration (Commented out as not needed for now)
            logging.info("\n✅ Step 6: Verifying migration...")
            self.verify_migration()
        
            
            self.conn.commit()
            logging.info("\n"+"="*60)
            logging.info("✅ Migration completed successfully!")
            logging.info("="*60)
            
        except Exception as e:
            logging.error(f"\n❌ Migration failed: {e}")
            self.conn.rollback()
            raise
        finally:
            self.close()
    
    def verify_migration(self):
        """Verify data was migrated correctly"""
        try:
            # Count courses
            self.cursor.execute("SELECT COUNT(*) FROM courses")
            course_count = self.cursor.fetchone()[0]
            logging.info(f"  📚 Courses: {course_count}")
            
            # Count modules
            self.cursor.execute("SELECT COUNT(*) FROM modules")
            module_count = self.cursor.fetchone()[0]
            logging.info(f"  📖 Modules: {module_count}")
            
            # Count topics
            self.cursor.execute("SELECT COUNT(*) FROM topics")
            topic_count = self.cursor.fetchone()[0]
            logging.info(f"  📄 Topics: {topic_count}")
            
            # Count quizzes
            self.cursor.execute("SELECT COUNT(*) FROM quizzes")
            quiz_count = self.cursor.fetchone()[0]
            logging.info(f"  📝 Quizzes: {quiz_count}")
            
            # Count quiz questions
            self.cursor.execute("SELECT COUNT(*) FROM quiz_questions")
            question_count = self.cursor.fetchone()[0]
            logging.info(f"  ❓ Quiz Questions: {question_count}")
            
            # Show sample course
            self.cursor.execute("""
                SELECT id, title 
                FROM courses 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            result = self.cursor.fetchone()
            if result:
                logging.info(f"  📌 Latest course: {result[1]} (ID: {result[0]})")
            
        except Exception as e:
            logging.error(f"❌ Verification failed: {e}")


def main():
    """Main entry point"""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not set in .env file")
        print("\nPlease add to .env:")
        print("DATABASE_URL=postgresql://user:pass@host/db?sslmode=require")
        sys.exit(1)
    
    print("\n🚀 JSON to PostgreSQL Migration")
    print("="*60)
    print(f"Database: {database_url.split('@')[1].split('/')[0]}")
    print("="*60)
    
    confirm = input("\n⚠️  This will migrate JSON data to database. Continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("❌ Migration cancelled")
        sys.exit(0)
    
    # Run migration
    migrator = JSONToDBMigrator(database_url)
    migrator.run_migration()


if __name__ == "__main__":
    main()
