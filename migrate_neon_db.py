"""
Database Migration Script: UUID to SERIAL
Migrates data from old database (UUID IDs) to new database (SERIAL IDs)
Maintains all relationships through ID mapping dictionaries
"""

import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
from typing import Dict, List, Tuple
import logging
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection strings
OLD_DB_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-still-cake-adz101ej-pooler.c-2.us-east-1.aws.neon.tech/prof_AI?sslmode=require&channel_binding=require"
NEW_DB_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Batch commit size to prevent long transactions
BATCH_COMMIT_SIZE = 100

# ID Mapping dictionaries
id_mappings = {
    'users': {},
    'courses': {},
    'modules': {},
    'topics': {},
    'enrollments': {},
    'payments': {},
    'quizzes': {}
}

def map_student_type(old_value):
    """Map old student_type values to new schema constraints"""
    if not old_value:
        return None
    
    old_value_lower = old_value.lower().strip()
    
    # Mapping dictionary
    mapping = {
        'college': 'undergrad',
        'undergraduate': 'undergrad',
        'undergrad': 'undergrad',
        'graduate': 'postgrad',
        'postgraduate': 'postgrad',
        'postgrad': 'postgrad',
        'high_school': 'high_school',
        'highschool': 'high_school',
        'high school': 'high_school',
        'professional': 'professional',
        'working': 'professional',
        'working professional': 'professional'
    }
    
    return mapping.get(old_value_lower, 'undergrad')  # Default to undergrad

class DatabaseMigration:
    def __init__(self):
        self.old_conn = None
        self.new_conn = None
        
    def connect(self):
        """Establish connections to both databases"""
        try:
            logger.info("Connecting to OLD database...")
            self.old_conn = psycopg2.connect(OLD_DB_URL)
            self.old_conn.autocommit = False
            
            logger.info("Connecting to NEW database...")
            self.new_conn = psycopg2.connect(NEW_DB_URL)
            self.new_conn.autocommit = False
            
            logger.info("[SUCCESS] Successfully connected to both databases")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Connection failed: {e}")
            return False
    
    def reconnect(self):
        """Reconnect to databases if connection lost"""
        try:
            logger.info("Reconnecting to databases...")
            if self.old_conn:
                try:
                    self.old_conn.close()
                except:
                    pass
            if self.new_conn:
                try:
                    self.new_conn.close()
                except:
                    pass
            
            self.old_conn = psycopg2.connect(OLD_DB_URL)
            self.old_conn.autocommit = False
            self.new_conn = psycopg2.connect(NEW_DB_URL)
            self.new_conn.autocommit = False
            
            logger.info("[SUCCESS] Reconnection successful")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Reconnection failed: {e}")
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
    
    def rebuild_id_mappings(self, table_name, mapping_key):
        """Rebuild ID mappings from already migrated data"""
        try:
            old_cur = self.old_conn.cursor()
            new_cur = self.new_conn.cursor()
            
            # Get all IDs from old database ordered by creation
            if table_name == 'users':
                old_cur.execute("SELECT id FROM users ORDER BY created_at ASC")
            elif table_name == 'courses':
                old_cur.execute("SELECT id FROM courses ORDER BY created_at ASC")
            elif table_name == 'modules':
                old_cur.execute("SELECT id FROM modules ORDER BY created_at ASC")
            elif table_name == 'topics':
                old_cur.execute("SELECT id FROM topics ORDER BY created_at ASC")
            elif table_name == 'enrollments':
                old_cur.execute("SELECT id FROM enrollments ORDER BY enrolled_at ASC")
            elif table_name == 'payments':
                old_cur.execute("SELECT id FROM payments ORDER BY created_at ASC")
            elif table_name == 'quizzes':
                old_cur.execute("SELECT id FROM quizzes ORDER BY created_at ASC")
            else:
                return
            
            old_ids = [row[0] for row in old_cur.fetchall()]
            
            # Get all IDs from new database
            new_cur.execute(f"SELECT id FROM {table_name} ORDER BY id ASC")
            new_ids = [row[0] for row in new_cur.fetchall()]
            
            # Map old to new
            for old_id, new_id in zip(old_ids, new_ids):
                id_mappings[mapping_key][old_id] = new_id
            
            logger.info(f"  Rebuilt {len(id_mappings[mapping_key])} ID mappings for {table_name}")
            
            old_cur.close()
            new_cur.close()
        except Exception as e:
            logger.error(f"Failed to rebuild mappings for {table_name}: {e}")
            raise
    
    def migrate_users(self):
        """Migrate users table (no dependencies)"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING USERS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('users'):
            logger.info("[SKIP] Users table already migrated, rebuilding ID mappings...")
            self.rebuild_id_mappings('users', 'users')
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            # NOTE: Old users table does NOT have updated_at column
            old_cur.execute("""
                SELECT id, username, email, password, role,
                       student_type, college_name, degree, school_class, school_affiliation,
                       terms_accepted, created_at, institution, subject, experience
                FROM users
                ORDER BY created_at ASC
            """)
            
            old_users = old_cur.fetchall()
            logger.info(f"Found {len(old_users)} users to migrate")
            
            migrated_count = 0
            for old_user in old_users:
                old_id = old_user[0]
                
                # Map student_type to new schema constraints
                mapped_student_type = map_student_type(old_user[5]) if old_user[4] == 'student' else None
                
                # Insert into new database
                new_cur.execute("""
                    INSERT INTO users (
                        username, email, password, role,
                        student_type, college_name, degree, school_class, school_affiliation,
                        institution, subject, experience,
                        terms_accepted, email_verified, is_active,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    old_user[1], old_user[2], old_user[3], old_user[4],  # username, email, password, role
                    mapped_student_type, old_user[6], old_user[7], old_user[8], old_user[9],  # student fields (with mapped type)
                    old_user[12], old_user[13], old_user[14],  # institution, subject, experience
                    old_user[10], False, True,  # terms_accepted, email_verified, is_active
                    old_user[11], old_user[11]  # created_at, updated_at (use created_at for both)
                ))
                
                new_id = new_cur.fetchone()[0]
                id_mappings['users'][old_id] = new_id
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    logger.info(f"  Migrated {migrated_count} users...")
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} users")
            logger.info(f"   ID mapping created: {len(id_mappings['users'])} entries")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] User migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_courses(self):
        """Migrate courses table (depends on users)"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING COURSES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('courses'):
            logger.info("[SKIP] Courses table already migrated, rebuilding ID mappings...")
            self.rebuild_id_mappings('courses', 'courses')
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, title, description, level, teacher_id,
                       course_order, course_number, country, file_metadata, created_by,
                       created_at, updated_at
                FROM courses
                ORDER BY created_at ASC
            """)
            
            old_courses = old_cur.fetchall()
            logger.info(f"Found {len(old_courses)} courses to migrate")
            
            migrated_count = 0
            for old_course in old_courses:
                old_id = old_course[0]
                old_teacher_id = old_course[4]
                
                # Map teacher ID
                new_teacher_id = id_mappings['users'].get(old_teacher_id)
                if not new_teacher_id:
                    logger.warning(f"  Skipping course {old_id} - teacher not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO courses (
                        title, description, level, teacher_id,
                        course_order, course_number, country, file_metadata, created_by,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    old_course[1], old_course[2], old_course[3], new_teacher_id,
                    old_course[5], old_course[6], old_course[7], old_course[8], old_course[9],
                    old_course[10], old_course[11] or old_course[10]
                ))
                
                new_id = new_cur.fetchone()[0]
                id_mappings['courses'][old_id] = new_id
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} courses")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Course migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_course_pricing(self):
        """Migrate course_pricing table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING COURSE PRICING")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('course_pricing'):
            logger.info("[SKIP] Course pricing table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, course_id, price, currency, is_free, display_order, course_name,
                       created_at, updated_at
                FROM course_pricing
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} pricing records to migrate")
            
            migrated_count = 0
            for record in old_records:
                old_course_id = record[1]
                new_course_id = id_mappings['courses'].get(old_course_id)
                
                if not new_course_id:
                    logger.warning(f"  Skipping pricing - course {old_course_id} not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO course_pricing (
                        course_id, price, currency, is_free, display_order, course_name,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_course_id, record[2], record[3], record[4], record[5], record[6],
                    record[7], record[8] or record[7]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} pricing records")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Pricing migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_course_images(self):
        """Migrate course_images table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING COURSE IMAGES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('course_images'):
            logger.info("[SKIP] Course images table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            # First, build a mapping from course_number to course UUID
            old_cur.execute("""
                SELECT id, course_number FROM courses WHERE course_number IS NOT NULL
            """)
            course_number_to_uuid = {row[1]: row[0] for row in old_cur.fetchall()}
            logger.info(f"Built mapping for {len(course_number_to_uuid)} course numbers to UUIDs")
            
            old_cur.execute("""
                SELECT id, course_id, image_url, course_name, created_at, updated_at
                FROM course_images
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} image records to migrate")
            
            migrated_count = 0
            for record in old_records:
                # course_id in course_images appears to be course_number (integer), not UUID
                course_id_value = record[1]
                
                # Try to find the actual course UUID using course_number
                old_course_uuid = None
                if isinstance(course_id_value, int) or (isinstance(course_id_value, str) and course_id_value.isdigit()):
                    # It's a course_number, look it up
                    course_num = int(course_id_value) if isinstance(course_id_value, str) else course_id_value
                    old_course_uuid = course_number_to_uuid.get(course_num)
                else:
                    # It might already be a UUID
                    old_course_uuid = str(course_id_value)
                
                if not old_course_uuid:
                    logger.warning(f"  Skipping image - course_number {course_id_value} not found in courses")
                    continue
                
                new_course_id = id_mappings['courses'].get(old_course_uuid)
                
                if not new_course_id:
                    logger.warning(f"  Skipping image - course UUID {old_course_uuid} not found in mappings")
                    continue
                
                new_cur.execute("""
                    INSERT INTO course_images (
                        course_id, image_url, course_name, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    new_course_id, record[2], record[3], record[4], record[5] or record[4]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} image records")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Image migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_modules(self):
        """Migrate modules table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING MODULES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('modules'):
            logger.info("[SKIP] Modules table already migrated, rebuilding ID mappings...")
            self.rebuild_id_mappings('modules', 'modules')
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, course_id, week, title, description, learning_objectives, order_index, created_at
                FROM modules
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} modules to migrate")
            
            migrated_count = 0
            for record in old_records:
                old_id = record[0]
                old_course_id = record[1]
                new_course_id = id_mappings['courses'].get(old_course_id)
                
                if not new_course_id:
                    logger.warning(f"  Skipping module {old_id} - course not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO modules (
                        course_id, week, title, description, learning_objectives, order_index, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    new_course_id, record[2], record[3], record[4], record[5], record[6], record[7]
                ))
                
                new_id = new_cur.fetchone()[0]
                id_mappings['modules'][old_id] = new_id
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} modules")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Module migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_topics(self):
        """Migrate topics table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING TOPICS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('topics'):
            logger.info("[SKIP] Topics table already migrated, rebuilding ID mappings...")
            self.rebuild_id_mappings('topics', 'topics')
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, module_id, title, content, order_index, estimated_time, created_at
                FROM topics
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} topics to migrate")
            
            migrated_count = 0
            for record in old_records:
                old_id = record[0]
                old_module_id = record[1]
                new_module_id = id_mappings['modules'].get(old_module_id)
                
                if not new_module_id:
                    logger.warning(f"  Skipping topic {old_id} - module not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO topics (
                        module_id, title, content, order_index, estimated_time, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    new_module_id, record[2], record[3], record[4], record[5], record[6]
                ))
                
                new_id = new_cur.fetchone()[0]
                id_mappings['topics'][old_id] = new_id
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} topics")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Topic migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_enrollments(self):
        """Migrate enrollments table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING ENROLLMENTS")
        logger.info("="*80)
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, student_id, course_id, is_paid, enrolled_at
                FROM enrollments
                ORDER BY enrolled_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} enrollments to migrate")
            
            migrated_count = 0
            for idx, record in enumerate(old_records, 1):
                try:
                    old_id = record[0]
                    old_student_id = record[1]
                    old_course_id = record[2]
                    
                    new_student_id = id_mappings['users'].get(old_student_id)
                    new_course_id = id_mappings['courses'].get(old_course_id)
                    
                    if not new_student_id or not new_course_id:
                        logger.warning(f"  Skipping enrollment {old_id} - references not found")
                        continue
                    
                    new_cur.execute("""
                        INSERT INTO enrollments (
                            student_id, course_id, is_paid, enrolled_at
                        ) VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (
                        new_student_id, new_course_id, record[3], record[4]
                    ))
                    
                    new_id = new_cur.fetchone()[0]
                    id_mappings['enrollments'][old_id] = new_id
                    migrated_count += 1
                    
                    # Batch commit every BATCH_COMMIT_SIZE records
                    if migrated_count % BATCH_COMMIT_SIZE == 0:
                        self.new_conn.commit()
                        logger.info(f"  Committed batch: {migrated_count} enrollments migrated...")
                        
                except psycopg2.OperationalError as e:
                    if "SSL connection" in str(e) or "closed unexpectedly" in str(e):
                        logger.warning(f"  SSL connection lost at record {idx}, reconnecting...")
                        if self.reconnect():
                            new_cur = self.new_conn.cursor()
                            continue
                        else:
                            raise
                    else:
                        raise
            
            # Final commit for remaining records
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} enrollments")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Enrollment migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_payments(self):
        """Migrate payments table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING PAYMENTS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('payments'):
            logger.info("[SKIP] Payments table already migrated, rebuilding ID mappings...")
            self.rebuild_id_mappings('payments', 'payments')
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, student_id, course_id, enrollment_id, order_id,
                       amount, currency, status, payment_method,
                       transaction_id, tracking_id, bank_ref_no, ccavenue_response,
                       created_at, updated_at
                FROM payments
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} payments to migrate")
            
            migrated_count = 0
            for idx, record in enumerate(old_records, 1):
                try:
                    old_id = record[0]
                    new_student_id = id_mappings['users'].get(record[1])
                    new_course_id = id_mappings['courses'].get(record[2])
                    new_enrollment_id = id_mappings['enrollments'].get(record[3]) if record[3] else None
                    
                    if not new_student_id or not new_course_id:
                        logger.warning(f"  Skipping payment {old_id} - references not found")
                        continue
                    
                    new_cur.execute("""
                        INSERT INTO payments (
                            student_id, course_id, enrollment_id, order_id,
                            amount, currency, status, payment_method,
                            transaction_id, tracking_id, bank_ref_no, ccavenue_response,
                            created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        new_student_id, new_course_id, new_enrollment_id, record[4],
                        record[5], record[6], record[7], record[8],
                        record[9], record[10], record[11], record[12],
                        record[13], record[14] or record[13]
                    ))
                    
                    new_id = new_cur.fetchone()[0]
                    id_mappings['payments'][old_id] = new_id
                    migrated_count += 1
                    
                    # Batch commit
                    if migrated_count % BATCH_COMMIT_SIZE == 0:
                        self.new_conn.commit()
                        logger.info(f"  Committed batch: {migrated_count} payments migrated...")
                        
                except psycopg2.OperationalError as e:
                    if "SSL connection" in str(e) or "closed unexpectedly" in str(e):
                        logger.warning(f"  SSL connection lost at record {idx}, reconnecting...")
                        if self.reconnect():
                            new_cur = self.new_conn.cursor()
                            continue
                        else:
                            raise
                    else:
                        raise
            
            # Final commit
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} payments")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Payment migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_payment_transactions(self):
        """Migrate payment_transactions table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING PAYMENT TRANSACTIONS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('payment_transactions'):
            logger.info("[SKIP] Payment transactions table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        # Status mapping for constraint compliance
        def map_payment_status(old_status):
            """Map old payment status values to new schema constraints"""
            if not old_status:
                return 'initiated'
            
            status_mapping = {
                'failure': 'failed',
                'fail': 'failed',
                'success': 'completed',
                'successful': 'completed',
                'pending': 'initiated',
                'processing': 'initiated',
                'initiated': 'initiated',
                'completed': 'completed',
                'failed': 'failed',
                'cancelled': 'failed',
                'canceled': 'failed'
            }
            
            return status_mapping.get(old_status.lower().strip(), 'initiated')
        
        try:
            old_cur.execute("""
                SELECT id, user_id, course_id, order_id, ccavenue_order_id,
                       amount, currency, status, payment_response,
                       created_at, updated_at
                FROM payment_transactions
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} payment transactions to migrate")
            
            migrated_count = 0
            for record in old_records:
                new_user_id = id_mappings['users'].get(record[1])
                new_course_id = id_mappings['courses'].get(record[2])
                
                if not new_user_id or not new_course_id:
                    logger.warning(f"  Skipping transaction - references not found")
                    continue
                
                # Map status to new schema
                mapped_status = map_payment_status(record[7])
                
                new_cur.execute("""
                    INSERT INTO payment_transactions (
                        user_id, course_id, order_id, ccavenue_order_id,
                        amount, currency, status, payment_response,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_user_id, new_course_id, record[3], record[4],
                    record[5], record[6], mapped_status, record[8],
                    record[9], record[10] or record[9]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} payment transactions")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Payment transaction migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_user_purchases(self):
        """Migrate user_purchases table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING USER PURCHASES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('user_purchases'):
            logger.info("[SKIP] User purchases table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, user_id, course_id, payment_id, amount, currency,
                       status, payment_method, purchased_at, expires_at
                FROM user_purchases
                ORDER BY purchased_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} user purchases to migrate")
            
            migrated_count = 0
            for record in old_records:
                new_user_id = id_mappings['users'].get(record[1])
                new_course_id = id_mappings['courses'].get(record[2])
                new_payment_id = id_mappings['payments'].get(record[3]) if record[3] else None
                
                if not new_user_id or not new_course_id:
                    logger.warning(f"  Skipping purchase - references not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO user_purchases (
                        user_id, course_id, payment_id, amount, currency,
                        status, payment_method, purchased_at, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_user_id, new_course_id, new_payment_id, record[4], record[5],
                    record[6], record[7], record[8], record[9]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} user purchases")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] User purchase migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_quizzes(self):
        """Migrate quizzes table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING QUIZZES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('quizzes'):
            logger.info("[SKIP] Quizzes table already migrated, rebuilding ID mappings...")
            self.rebuild_id_mappings('quizzes', 'quizzes')
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, quiz_id, course_id, module_id, title, description,
                       quiz_type, passing_score, time_limit, created_at
                FROM quizzes
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} quizzes to migrate")
            
            migrated_count = 0
            for record in old_records:
                old_id = record[0]
                new_course_id = id_mappings['courses'].get(record[2])
                new_module_id = id_mappings['modules'].get(record[3]) if record[3] else None
                
                if not new_course_id:
                    logger.warning(f"  Skipping quiz {old_id} - course not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO quizzes (
                        quiz_id, course_id, module_id, title, description,
                        quiz_type, passing_score, time_limit, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    record[1], new_course_id, new_module_id, record[4], record[5],
                    record[6], record[7], record[8], record[9]
                ))
                
                new_id = new_cur.fetchone()[0]
                id_mappings['quizzes'][old_id] = new_id
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} quizzes")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Quiz migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_quiz_questions(self):
        """Migrate quiz_questions table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING QUIZ QUESTIONS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('quiz_questions'):
            logger.info("[SKIP] Quiz questions table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, quiz_id, question_number, question_text, options,
                       correct_answer, explanation, difficulty, created_at
                FROM quiz_questions
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} quiz questions to migrate")
            
            migrated_count = 0
            for record in old_records:
                # quiz_id is a VARCHAR, not a FK - copy as-is
                new_cur.execute("""
                    INSERT INTO quiz_questions (
                        quiz_id, question_number, question_text, options,
                        correct_answer, explanation, difficulty, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record[1], record[2], record[3], record[4],
                    record[5], record[6], record[7], record[8]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} quiz questions")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Quiz question migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_course_id_mapping(self):
        """Migrate course_id_mapping table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING COURSE ID MAPPING")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('course_id_mapping'):
            logger.info("[SKIP] Course ID mapping table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, new_course_id, old_course_id, description, created_at, updated_at
                FROM course_id_mapping
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} course ID mappings to migrate")
            
            migrated_count = 0
            for record in old_records:
                # Map both new_course_id and old_course_id
                mapped_new_course_id = id_mappings['courses'].get(record[1])
                mapped_old_course_id = id_mappings['courses'].get(record[2])
                
                if not mapped_new_course_id:
                    logger.warning(f"  Skipping mapping - new_course_id not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO course_id_mapping (
                        new_course_id, old_course_id, description, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    mapped_new_course_id, mapped_old_course_id, record[3], record[4], record[5]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} course ID mappings")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Course ID mapping migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_quiz_responses(self):
        """Migrate quiz_responses table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING QUIZ RESPONSES")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('quiz_responses'):
            logger.info("[SKIP] Quiz responses table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, quiz_id, user_id, answers, score, total_questions,
                       correct_answers, submitted_at, time_taken
                FROM quiz_responses
                ORDER BY submitted_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} quiz responses to migrate")
            
            migrated_count = 0
            for record in old_records:
                new_user_id = id_mappings['users'].get(record[2])
                
                if not new_user_id:
                    logger.warning(f"  Skipping response - user not found")
                    continue
                
                # quiz_id is VARCHAR, copy as-is
                new_cur.execute("""
                    INSERT INTO quiz_responses (
                        quiz_id, user_id, answers, score, total_questions,
                        correct_answers, submitted_at, time_taken
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record[1], new_user_id, record[3], record[4], record[5],
                    record[6], record[7], record[8]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} quiz responses")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] Quiz response migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_user_progress(self):
        """Migrate user_progress table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING USER PROGRESS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('user_progress'):
            logger.info("[SKIP] User progress table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, user_id, course_id, module_id, topic_id, status,
                       progress_percentage, last_accessed, completion_date
                FROM user_progress
                ORDER BY last_accessed ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} user progress records to migrate")
            
            migrated_count = 0
            for record in old_records:
                new_user_id = id_mappings['users'].get(record[1])
                new_course_id = id_mappings['courses'].get(record[2])
                new_module_id = id_mappings['modules'].get(record[3]) if record[3] else None
                new_topic_id = id_mappings['topics'].get(record[4]) if record[4] else None
                
                if not new_user_id or not new_course_id:
                    logger.warning(f"  Skipping progress - user/course not found")
                    continue
                
                new_cur.execute("""
                    INSERT INTO user_progress (
                        user_id, course_id, module_id, topic_id, status,
                        progress_percentage, last_accessed, completion_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    new_user_id, new_course_id, new_module_id, new_topic_id, record[5],
                    record[6], record[7], record[8]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} user progress records")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] User progress migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def migrate_api_access_requests(self):
        """Migrate api_access_requests table"""
        logger.info("\n" + "="*80)
        logger.info("MIGRATING API ACCESS REQUESTS")
        logger.info("="*80)
        
        # Check if already migrated
        if self.check_table_migrated('api_access_requests'):
            logger.info("[SKIP] API access requests table already migrated")
            return
        
        old_cur = self.old_conn.cursor()
        new_cur = self.new_conn.cursor()
        
        try:
            old_cur.execute("""
                SELECT id, first_name, last_name, email, phone, company,
                       job_title, use_case, status, created_at, updated_at
                FROM api_access_requests
                ORDER BY created_at ASC
            """)
            
            old_records = old_cur.fetchall()
            logger.info(f"Found {len(old_records)} API access requests to migrate")
            
            migrated_count = 0
            for record in old_records:
                # No FK dependencies, copy as-is
                new_cur.execute("""
                    INSERT INTO api_access_requests (
                        first_name, last_name, email, phone, company,
                        job_title, use_case, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    record[1], record[2], record[3], record[4], record[5],
                    record[6], record[7], record[8], record[9], record[10]
                ))
                migrated_count += 1
            
            self.new_conn.commit()
            logger.info(f"[SUCCESS] Successfully migrated {migrated_count} API access requests")
            
        except Exception as e:
            self.new_conn.rollback()
            logger.error(f"[ERROR] API access request migration failed: {e}")
            raise
        finally:
            old_cur.close()
            new_cur.close()
    
    def update_sequences(self):
        """Update SERIAL sequences after migration"""
        logger.info("\n" + "="*80)
        logger.info("UPDATING SEQUENCES")
        logger.info("="*80)
        
        cur = self.new_conn.cursor()
        
        try:
            tables = ['users', 'courses', 'modules', 'topics', 'enrollments', 'payments', 'quizzes']
            
            for table in tables:
                cur.execute(f"SELECT MAX(id) FROM {table}")
                max_id = cur.fetchone()[0]
                
                if max_id:
                    cur.execute(f"SELECT setval('{table}_id_seq', {max_id})")
                    logger.info(f"  Updated {table}_id_seq to {max_id}")
            
            self.new_conn.commit()
            logger.info("[SUCCESS] All sequences updated")
            
        except Exception as e:
            logger.error(f"[ERROR] Sequence update failed: {e}")
            raise
        finally:
            cur.close()

def main():
    logger.info("\n[START] Starting Database Migration")
    logger.info(f"Started at: {datetime.now()}")
    
    migration = DatabaseMigration()
    
    try:
        if not migration.connect():
            return
        
        # Migrate tables in dependency order
        # 1. Base tables with no dependencies
        migration.migrate_users()
        migration.migrate_api_access_requests()
        
        # 2. Courses and related tables
        migration.migrate_courses()
        migration.migrate_course_pricing()
        migration.migrate_course_images()
        migration.migrate_course_id_mapping()
        
        # 3. Course content hierarchy
        migration.migrate_modules()
        migration.migrate_topics()
        
        # 4. User interactions with courses
        migration.migrate_enrollments()
        migration.migrate_payments()
        migration.migrate_payment_transactions()
        migration.migrate_user_purchases()
        
        # 5. Quizzes and responses
        migration.migrate_quizzes()
        migration.migrate_quiz_questions()
        migration.migrate_quiz_responses()
        
        # 6. User progress tracking
        migration.migrate_user_progress()
        
        # Update sequences
        migration.update_sequences()
        
        logger.info("\n" + "="*80)
        logger.info("[SUCCESS] Migration completed successfully!")
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
