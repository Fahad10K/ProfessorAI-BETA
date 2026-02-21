import psycopg2
import psycopg2.extras
import json
import logging
from datetime import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_remaining.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

OLD_DB_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-still-cake-adz101ej-pooler.c-2.us-east-1.aws.neon.tech/prof_AI?sslmode=require&channel_binding=require"
NEW_DB_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

id_mappings = {
    'users': {},
    'courses': {},
    'modules': {},
    'topics': {},
    'enrollments': {},
    'payments': {},
    'quizzes': {}
}

class RemainingTablesMigration:
    def __init__(self):
        self.old_conn = None
        self.new_conn = None
    
    def connect(self):
        """Connect to both databases"""
        try:
            logger.info("Connecting to OLD database...")
            self.old_conn = psycopg2.connect(OLD_DB_URL)
            self.old_conn.autocommit = False
            
            logger.info("Connecting to NEW database...")
            self.new_conn = psycopg2.connect(NEW_DB_URL)
            self.new_conn.autocommit = False
            
            logger.info("[SUCCESS] Connected to both databases")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Connection failed: {e}")
            return False
    
    def close(self):
        """Close database connections"""
        if self.old_conn:
            self.old_conn.close()
        if self.new_conn:
            self.new_conn.close()
        logger.info("Database connections closed")
    
    def check_table_migrated(self, table_name):
        """Check if a table has already been migrated"""
        try:
            cur = self.new_conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            cur.close()
            return count > 0
        except Exception as e:
            logger.warning(f"Could not check {table_name}: {e}")
            return False
    
    def check_constraint_values(self, table_name, column_name):
        """Check what values are allowed by a constraint in the new database"""
        try:
            cur = self.new_conn.cursor()
            cur.execute(f"""
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = '{table_name}'::regclass
                AND contype = 'c'
                AND pg_get_constraintdef(oid) LIKE '%{column_name}%'
            """)
            constraints = cur.fetchall()
            cur.close()
            
            logger.info(f"\n[CONSTRAINT CHECK] {table_name}.{column_name}:")
            for name, definition in constraints:
                logger.info(f"  {name}: {definition}")
            
            return constraints
        except Exception as e:
            logger.error(f"Error checking constraints: {e}")
            return []
    
    def rebuild_id_mappings(self):
        """Rebuild ID mappings from already migrated tables"""
        logger.info("\n" + "="*80)
        logger.info("REBUILDING ID MAPPINGS")
        logger.info("="*80)
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            # Users
            old_cur.execute("SELECT id FROM users ORDER BY created_at ASC")
            old_ids = [row[0] for row in old_cur.fetchall()]
            new_cur.execute("SELECT id FROM users ORDER BY id ASC")
            new_ids = [row[0] for row in new_cur.fetchall()]
            for old_id, new_id in zip(old_ids, new_ids):
                id_mappings['users'][old_id] = new_id
            logger.info(f"  Users: {len(id_mappings['users'])} mappings")
            
            # Courses
            old_cur.execute("SELECT id FROM courses ORDER BY created_at ASC")
            old_ids = [row[0] for row in old_cur.fetchall()]
            new_cur.execute("SELECT id FROM courses ORDER BY id ASC")
            new_ids = [row[0] for row in new_cur.fetchall()]
            for old_id, new_id in zip(old_ids, new_ids):
                id_mappings['courses'][old_id] = new_id
            logger.info(f"  Courses: {len(id_mappings['courses'])} mappings")
            
            # Modules
            old_cur.execute("SELECT id FROM modules ORDER BY created_at ASC")
            old_ids = [row[0] for row in old_cur.fetchall()]
            new_cur.execute("SELECT id FROM modules ORDER BY id ASC")
            new_ids = [row[0] for row in new_cur.fetchall()]
            for old_id, new_id in zip(old_ids, new_ids):
                id_mappings['modules'][old_id] = new_id
            logger.info(f"  Modules: {len(id_mappings['modules'])} mappings")
            
            # Topics
            old_cur.execute("SELECT id FROM topics ORDER BY created_at ASC")
            old_ids = [row[0] for row in old_cur.fetchall()]
            new_cur.execute("SELECT id FROM topics ORDER BY id ASC")
            new_ids = [row[0] for row in new_cur.fetchall()]
            for old_id, new_id in zip(old_ids, new_ids):
                id_mappings['topics'][old_id] = new_id
            logger.info(f"  Topics: {len(id_mappings['topics'])} mappings")
            
        except Exception as e:
            logger.error(f"Failed to rebuild mappings: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def get_table_data(self, table_name):
        """Retrieve all data from a table as list of dictionaries"""
        logger.info(f"\n[RETRIEVING] {table_name}")
        
        old_cur = self.old_conn.cursor()
        try:
            # Get column names
            old_cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """)
            columns = [row[0] for row in old_cur.fetchall()]
            logger.info(f"  Columns: {columns}")
            
            # Get data
            column_list = ', '.join(columns)
            old_cur.execute(f"SELECT {column_list} FROM {table_name}")
            rows = old_cur.fetchall()
            
            # Convert to list of dictionaries
            data = []
            for row in rows:
                record = {}
                for i, col in enumerate(columns):
                    record[col] = row[i]
                data.append(record)
            
            logger.info(f"  Retrieved {len(data)} records")
            return data, columns
        except Exception as e:
            logger.error(f"Error retrieving {table_name}: {e}")
            return [], []
        finally:
            old_cur.close()
    
    def migrate_payment_transactions(self):
        """Migrate payment_transactions with proper status mapping"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING PAYMENT TRANSACTIONS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('payment_transactions'):
            logger.info("[SKIP] Payment transactions already migrated")
            return
        
        # Check constraints first
        self.check_constraint_values('payment_transactions', 'status')
        
        # Get data
        data, columns = self.get_table_data('payment_transactions')
        
        if not data:
            logger.info("No payment transactions to migrate")
            return
        
        new_cur = self.new_conn.cursor()
        
        try:
            migrated_count = 0
            skipped_count = 0
            
            for record in data:
                # Map foreign keys
                new_user_id = id_mappings['users'].get(record['user_id'])
                new_course_id = id_mappings['courses'].get(record['course_id'])
                
                if not new_user_id or not new_course_id:
                    logger.warning(f"  Skipping transaction {record['order_id']} - user/course not found")
                    skipped_count += 1
                    continue
                
                # Map status - check what values are actually allowed
                status = record['status']
                if status:
                    status = status.lower().strip()
                    # Map based on actual constraint
                    if status in ['failure', 'fail', 'cancelled', 'canceled']:
                        status = 'failed'
                    elif status in ['success', 'successful']:
                        status = 'success'  # or 'completed' - need to verify
                    elif status in ['pending', 'processing']:
                        status = 'pending'  # or 'initiated'
                
                new_cur.execute("""
                    INSERT INTO payment_transactions (
                        user_id, course_id, order_id, ccavenue_order_id,
                        amount, currency, status, payment_response,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_user_id, new_course_id, record['order_id'], record.get('ccavenue_order_id'),
                    record['amount'], record['currency'], status, record.get('payment_response'),
                    record['created_at'], record.get('updated_at') or record['created_at']
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} payment transactions (skipped {skipped_count})")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Payment transaction migration failed: {e}")
            logger.error(f"  Problematic record: {record}")
            raise
        finally:
            new_cur.close()
    
    def migrate_user_purchases(self):
        """Migrate user_purchases"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING USER PURCHASES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('user_purchases'):
            logger.info("[SKIP] User purchases already migrated")
            return
        
        data, columns = self.get_table_data('user_purchases')
        
        if not data:
            logger.info("No user purchases to migrate")
            return
        
        new_cur = self.new_conn.cursor()
        
        try:
            migrated_count = 0
            skipped_count = 0
            
            for record in data:
                new_user_id = id_mappings['users'].get(record['user_id'])
                new_course_id = id_mappings['courses'].get(record['course_id'])
                
                if not new_user_id or not new_course_id:
                    logger.warning(f"  Skipping purchase - user/course not found")
                    skipped_count += 1
                    continue
                
                # payment_id in old DB is tracking_id (text), but new DB expects integer FK
                # Set to NULL since we can't map tracking IDs to payment table IDs
                new_cur.execute("""
                    INSERT INTO user_purchases (
                        user_id, course_id, payment_id, amount, currency,
                        status, payment_method, purchased_at, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_user_id, new_course_id, None,  # Set payment_id to NULL
                    record['amount'], record['currency'], record['status'],
                    record.get('payment_method'), record['purchased_at'], record.get('expires_at')
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} user purchases (skipped {skipped_count})")
            logger.info("  Note: payment_id set to NULL (old DB had tracking IDs, new DB expects FK)")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] User purchase migration failed: {e}")
            logger.error(f"  Problematic record: {record}")
            raise
        finally:
            new_cur.close()
    
    def migrate_quizzes(self):
        """Migrate quizzes"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING QUIZZES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('quizzes'):
            logger.info("[SKIP] Quizzes already migrated")
            return
        
        data, columns = self.get_table_data('quizzes')
        
        if not data:
            logger.info("No quizzes to migrate")
            return
        
        new_cur = self.new_conn.cursor()
        
        try:
            migrated_count = 0
            skipped_count = 0
            
            for record in data:
                old_id = record['id']
                new_course_id = id_mappings['courses'].get(record['course_id'])
                new_module_id = id_mappings['modules'].get(record['module_id']) if record.get('module_id') else None
                
                if not new_course_id:
                    logger.warning(f"  Skipping quiz {record['quiz_id']} - course not found")
                    skipped_count += 1
                    continue
                
                new_cur.execute("""
                    INSERT INTO quizzes (
                        quiz_id, course_id, module_id, title, description,
                        quiz_type, passing_score, time_limit, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    record['quiz_id'], new_course_id, new_module_id,
                    record['title'], record.get('description'),
                    record.get('quiz_type'), record.get('passing_score'),
                    record.get('time_limit'), record['created_at']
                ))
                
                new_id = new_cur.fetchone()[0]
                id_mappings['quizzes'][old_id] = new_id
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} quizzes (skipped {skipped_count})")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Quiz migration failed: {e}")
            raise
        finally:
            new_cur.close()
    
    def migrate_quiz_questions(self):
        """Migrate quiz_questions"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING QUIZ QUESTIONS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('quiz_questions'):
            logger.info("[SKIP] Quiz questions already migrated")
            return
        
        data, columns = self.get_table_data('quiz_questions')
        
        if not data:
            logger.info("No quiz questions to migrate")
            return
        
        new_cur = self.new_conn.cursor()
        
        try:
            migrated_count = 0
            
            for record in data:
                # Convert options to JSONB - psycopg2 retrieves JSONB as Python objects
                # We need to wrap it with Json() for proper insertion
                options_data = record['options']
                if options_data is not None:
                    # If it's already a dict/list, wrap with Json()
                    # If it's a string, parse it first
                    if isinstance(options_data, str):
                        options_data = json.loads(options_data)
                    options_jsonb = psycopg2.extras.Json(options_data)
                else:
                    options_jsonb = None
                
                # quiz_id is VARCHAR, not a foreign key
                new_cur.execute("""
                    INSERT INTO quiz_questions (
                        quiz_id, question_number, question_text, options,
                        correct_answer, explanation, difficulty, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record['quiz_id'], record['question_number'],
                    record['question_text'], options_jsonb,
                    record['correct_answer'], record.get('explanation'),
                    record.get('difficulty'), record['created_at']
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} quiz questions")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Quiz question migration failed: {e}")
            logger.error(f"  Problematic record: {record}")
            raise
        finally:
            new_cur.close()
    
    def migrate_quiz_responses(self):
        """Migrate quiz_responses"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING QUIZ RESPONSES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('quiz_responses'):
            logger.info("[SKIP] Quiz responses already migrated")
            return
        
        data, columns = self.get_table_data('quiz_responses')
        
        if not data:
            logger.info("No quiz responses to migrate")
            return
        
        new_cur = self.new_conn.cursor()
        
        try:
            migrated_count = 0
            skipped_count = 0
            
            for record in data:
                new_user_id = id_mappings['users'].get(record['user_id'])
                
                if not new_user_id:
                    logger.warning(f"  Skipping response - user not found")
                    skipped_count += 1
                    continue
                
                # Convert answers to JSONB
                answers_data = record['answers']
                if answers_data is not None:
                    if isinstance(answers_data, str):
                        answers_data = json.loads(answers_data)
                    answers_jsonb = psycopg2.extras.Json(answers_data)
                else:
                    answers_jsonb = None
                
                new_cur.execute("""
                    INSERT INTO quiz_responses (
                        quiz_id, user_id, answers, score, total_questions,
                        correct_answers, submitted_at, time_taken
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record['quiz_id'], new_user_id, answers_jsonb,
                    record.get('score'), record.get('total_questions'),
                    record.get('correct_answers'), record['submitted_at'],
                    record.get('time_taken')
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} quiz responses (skipped {skipped_count})")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Quiz response migration failed: {e}")
            logger.error(f"  Problematic record: {record}")
            raise
        finally:
            new_cur.close()
    
    def migrate_course_images(self):
        """Migrate course_images using course name matching"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING COURSE IMAGES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('course_images'):
            logger.info("[SKIP] Course images already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            # Get course images with course names from old DB via JOIN
            old_cur.execute("""
                SELECT ci.id, ci.image_url, ci.course_name, c.title as course_title, ci.created_at, ci.updated_at
                FROM course_images ci
                LEFT JOIN courses c ON ci.course_id = c.id
            """)
            old_images = old_cur.fetchall()
            logger.info(f"  Retrieved {len(old_images)} course images from old DB")
            
            # Build course name to new course ID mapping from new DB
            new_cur.execute("SELECT id, title FROM courses")
            course_name_map = {}
            for new_id, title in new_cur.fetchall():
                course_name_map[title.lower().strip()] = new_id
            logger.info(f"  Built mapping for {len(course_name_map)} courses in new DB")
            
            migrated_count = 0
            skipped_count = 0
            
            for old_image in old_images:
                old_id, image_url, course_name, course_title, created_at, updated_at = old_image
                
                # Try to match by course_name first, then by course_title
                match_name = None
                if course_name:
                    match_name = course_name.lower().strip()
                elif course_title:
                    match_name = course_title.lower().strip()
                
                if not match_name:
                    logger.warning(f"  Skipping image {old_id} - no course name/title")
                    skipped_count += 1
                    continue
                
                new_course_id = course_name_map.get(match_name)
                
                if not new_course_id:
                    logger.warning(f"  Skipping image for course '{match_name[:50]}' - not found in new DB")
                    skipped_count += 1
                    continue
                
                # Check if this course already has an image (unique constraint)
                new_cur.execute("SELECT id FROM course_images WHERE course_id = %s", (new_course_id,))
                if new_cur.fetchone():
                    logger.warning(f"  Skipping image for course '{match_name[:50]}' - already has image")
                    skipped_count += 1
                    continue
                
                new_cur.execute("""
                    INSERT INTO course_images (
                        course_id, image_url, course_name, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    new_course_id, image_url, match_name, created_at, updated_at or created_at
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} course images (skipped {skipped_count})")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Course images migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_user_progress(self):
        """Migrate user_progress"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING USER PROGRESS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('user_progress'):
            logger.info("[SKIP] User progress already migrated")
            return
        
        data, columns = self.get_table_data('user_progress')
        
        if not data:
            logger.info("No user progress to migrate")
            return
        
        new_cur = self.new_conn.cursor()
        
        try:
            migrated_count = 0
            skipped_count = 0
            
            for record in data:
                new_user_id = id_mappings['users'].get(record['user_id'])
                new_course_id = id_mappings['courses'].get(record['course_id'])
                new_module_id = id_mappings['modules'].get(record['module_id']) if record.get('module_id') else None
                new_topic_id = id_mappings['topics'].get(record['topic_id']) if record.get('topic_id') else None
                
                if not new_user_id or not new_course_id:
                    logger.warning(f"  Skipping progress - user/course not found")
                    skipped_count += 1
                    continue
                
                new_cur.execute("""
                    INSERT INTO user_progress (
                        user_id, course_id, module_id, topic_id, status,
                        progress_percentage, last_accessed, completion_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_user_id, new_course_id, new_module_id, new_topic_id,
                    record.get('status'), record.get('progress_percentage'),
                    record['last_accessed'], record.get('completion_date')
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Migrated {migrated_count} user progress records (skipped {skipped_count})")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] User progress migration failed: {e}")
            raise
        finally:
            new_cur.close()

def main():
    logger.info("\n[START] Migrating Remaining Tables")
    logger.info(f"Started at: {datetime.now()}")
    
    migration = RemainingTablesMigration()
    
    try:
        if not migration.connect():
            return
        
        # Rebuild ID mappings first
        migration.rebuild_id_mappings()
        
        # Migrate remaining tables
        # migration.migrate_payment_transactions()  # Already migrated - 30 records
        migration.migrate_user_purchases()
        migration.migrate_quizzes()
        migration.migrate_quiz_questions()
        migration.migrate_quiz_responses()
        migration.migrate_course_images()
        migration.migrate_user_progress()
        
        logger.info("\n" + "="*80)
        logger.info("[SUCCESS] All remaining tables migrated successfully!")
        logger.info(f"Completed at: {datetime.now()}")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"\n[ERROR] Migration failed: {e}")
        logger.error("Rolling back changes...")
        if migration.new_conn:
            migration.new_conn.rollback()
    finally:
        migration.close()

if __name__ == "__main__":
    main()
