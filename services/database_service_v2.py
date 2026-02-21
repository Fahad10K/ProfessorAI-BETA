"""
Database Service V2 - PostgreSQL (Neon) integration with new schema
Supports user_sessions, messages, and all course-related tables
"""

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, timedelta
import json
import os

logger = logging.getLogger(__name__)

# Get database URL from environment or config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

class DatabaseServiceV2:
    """Enhanced database service for new schema with sessions and messages"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        self.pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            self.pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=self.database_url
            )
            logger.info("✅ Database connection pool initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database pool: {e}")
            raise
    
    def get_connection(self):
        """Get connection from pool"""
        return self.pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)
    
    def _validate_connection(self, conn):
        """Validate connection is alive, reconnect if needed"""
        try:
            # Simple query to test connection
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def execute_query(self, query: str, params: tuple = None, fetch: str = None):
        """Execute query with automatic connection management and retry logic"""
        conn = None
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                conn = self.get_connection()
                
                # Validate connection before use
                if not self._validate_connection(conn):
                    logger.warning(f"⚠️ Connection invalid on attempt {attempt + 1}, getting fresh connection")
                    self.return_connection(conn)
                    # Close the bad connection and get a fresh one
                    try:
                        conn.close()
                    except:
                        pass
                    conn = self.get_connection()
                
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, params)
                    
                    if fetch == 'one':
                        result = cur.fetchone()
                    elif fetch == 'all':
                        result = cur.fetchall()
                    else:
                        result = None
                    
                    conn.commit()
                    return result
                    
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                # Connection errors - retry with fresh connection
                if conn:
                    try:
                        conn.rollback()
                        self.return_connection(conn)
                        conn.close()
                    except:
                        pass
                    conn = None
                
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Connection error on attempt {attempt + 1}, retrying: {e}")
                    continue
                else:
                    logger.error(f"❌ Database connection error after {max_retries} attempts: {e}")
                    raise
                    
            except Exception as e:
                if conn:
                    conn.rollback()
                logger.error(f"Database error: {e}")
                raise
            finally:
                if conn:
                    self.return_connection(conn)
    
    # ============= COURSE OPERATIONS =============
    
    def get_all_courses(self) -> List[Dict]:
        """Get all courses with all columns including country"""
        query = """
            SELECT 
                id, title, description, level, teacher_id,
                course_order, course_number, country, file_metadata,
                created_by, created_at, updated_at
            FROM courses
            ORDER BY course_order ASC, id ASC
        """
        
        try:
            result = self.execute_query(query, fetch='all')
            if not result:
                return []
            
            # Convert RealDictRow to regular dict
            courses = []
            for row in result:
                course = dict(row)
                # Convert timestamps to ISO format
                if course.get('created_at'):
                    course['created_at'] = course['created_at'].isoformat()
                if course.get('updated_at'):
                    course['updated_at'] = course['updated_at'].isoformat()
                courses.append(course)
            
            return courses
        except Exception as e:
            logger.error(f"Error fetching courses: {e}")
            return []
    
    def get_course(self, course_id: int) -> Optional[Dict]:
        """Get single course by ID"""
        query = """
            SELECT 
                id, title, description, level, teacher_id,
                course_order, course_number, country, file_metadata,
                created_by, created_at, updated_at
            FROM courses
            WHERE id = %s
        """
        
        try:
            result = self.execute_query(query, (course_id,), fetch='one')
            if result:
                course = dict(result)
                if course.get('created_at'):
                    course['created_at'] = course['created_at'].isoformat()
                if course.get('updated_at'):
                    course['updated_at'] = course['updated_at'].isoformat()
                return course
            return None
        except Exception as e:
            logger.error(f"Error fetching course {course_id}: {e}")
            return None
    
    def get_course_by_number(self, course_number: int) -> Optional[Dict]:
        """Get course by course_number (basic info only)"""
        query = """
            SELECT 
                id, title, description, level, teacher_id,
                course_order, course_number, country, file_metadata,
                created_by, created_at, updated_at
            FROM courses
            WHERE course_number = %s
        """
        
        try:
            result = self.execute_query(query, (course_number,), fetch='one')
            if result:
                course = dict(result)
                if course.get('created_at'):
                    course['created_at'] = course['created_at'].isoformat()
                if course.get('updated_at'):
                    course['updated_at'] = course['updated_at'].isoformat()
                return course
            return None
        except Exception as e:
            logger.error(f"Error fetching course by number {course_number}: {e}")
            return None
    
    def get_course_modules(self, course_id: int) -> List[Dict]:
        """Get all modules for a course"""
        query = """
            SELECT 
                id, course_id, week, title, description,
                learning_objectives, order_index, created_at
            FROM modules
            WHERE course_id = %s
            ORDER BY order_index, week
        """
        
        try:
            result = self.execute_query(query, (course_id,), fetch='all')
            if not result:
                return []
            
            modules = []
            for row in result:
                module = dict(row)
                if module.get('created_at'):
                    module['created_at'] = module['created_at'].isoformat()
                modules.append(module)
            
            return modules
        except Exception as e:
            logger.error(f"Error fetching modules for course {course_id}: {e}")
            return []
    
    def get_module_topics(self, module_id: int) -> List[Dict]:
        """Get all topics for a module"""
        query = """
            SELECT 
                id, module_id, title, content,
                order_index, estimated_time, created_at
            FROM topics
            WHERE module_id = %s
            ORDER BY order_index
        """
        
        try:
            result = self.execute_query(query, (module_id,), fetch='all')
            if not result:
                return []
            
            topics = []
            for row in result:
                topic = dict(row)
                if topic.get('created_at'):
                    topic['created_at'] = topic['created_at'].isoformat()
                topics.append(topic)
            
            return topics
        except Exception as e:
            logger.error(f"Error fetching topics for module {module_id}: {e}")
            return []
    
    def get_course_with_content(self, course_identifier: Any) -> Optional[Dict]:
        """Get complete course structure with modules and topics"""
        # First get the course
        try:
            # Try as integer (course_number)
            course_num = int(course_identifier)
            course = self.get_course_by_number(course_num)
        except (ValueError, TypeError):
            # Try as UUID (course_id)
            course = self.get_course(course_identifier)
        
        if not course:
            return None
        
        # Get course_id for querying modules
        course_id = course.get('id')
        if not course_id:
            return course
        
        # Fetch modules
        modules = self.get_course_modules(course_id)
        
        # For each module, fetch topics
        for module in modules:
            module_id = module.get('id')
            if module_id:
                topics = self.get_module_topics(module_id)
                module['topics'] = topics
        
        # Add modules to course
        course['modules'] = modules
        
        logger.info(f"✅ Fetched complete course content: {len(modules)} modules, {sum(len(m.get('topics', [])) for m in modules)} topics")
        
        return course
    
    # ============= QUIZ OPERATIONS =============
    
    def create_quiz(self, quiz_data: Dict[str, Any], course_id: int) -> str:
        """Create a quiz with questions"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Get module_id if module quiz
                module_id = None
                if quiz_data.get('module_week'):
                    cur.execute(
                        "SELECT id FROM modules WHERE course_id = %s AND week = %s",
                        (course_id, quiz_data['module_week'])
                    )
                    module_result = cur.fetchone()
                    if module_result:
                        module_id = module_result[0]
                
                # Create quiz
                quiz_id = quiz_data.get('quiz_id', f"quiz_{os.urandom(4).hex()}")
                cur.execute("""
                    INSERT INTO quizzes (quiz_id, course_id, module_id, title, quiz_type, description)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    quiz_id,
                    course_id,
                    module_id,
                    quiz_data.get('title', 'Quiz'),
                    quiz_data.get('quiz_type', 'module'),
                    quiz_data.get('description', '')
                ))
                
                # Create questions
                for question_data in quiz_data.get('questions', []):
                    cur.execute("""
                        INSERT INTO quiz_questions (
                            quiz_id, question_number, question_text,
                            options, correct_answer, explanation
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        quiz_id,
                        question_data.get('question_number', 1),
                        question_data.get('question_text', question_data.get('question', '')),
                        json.dumps(question_data.get('options', {})),
                        question_data.get('correct_answer', 'A'),
                        question_data.get('explanation', '')
                    ))
                
                conn.commit()
                logger.info(f"✅ Created quiz: {quiz_id} with {len(quiz_data.get('questions', []))} questions")
                return quiz_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating quiz: {e}")
            raise
        finally:
            self.return_connection(conn)
    
    def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get quiz with all questions"""
        query = """
            SELECT q.quiz_id, q.title, q.description, q.quiz_type, q.course_id,
                   m.week as module_week
            FROM quizzes q
            LEFT JOIN modules m ON q.module_id = m.id
            WHERE q.quiz_id = %s
        """
        
        try:
            quiz_result = self.execute_query(query, (quiz_id,), fetch='one')
            if not quiz_result:
                return None
            
            quiz = dict(quiz_result)
            
            # Get questions
            questions_query = """
                SELECT question_number, question_text, options,
                       correct_answer, explanation
                FROM quiz_questions
                WHERE quiz_id = %s
                ORDER BY question_number
            """
            questions_result = self.execute_query(questions_query, (quiz_id,), fetch='all')
            
            quiz['questions'] = []
            for q in questions_result:
                question = dict(q)
                # Parse JSON options if stored as string
                if isinstance(question['options'], str):
                    question['options'] = json.loads(question['options'])
                question['question_id'] = f"{quiz_id}_q{question['question_number']}"
                question['topic'] = ''
                quiz['questions'].append(question)
            
            return quiz
        except Exception as e:
            logger.error(f"Error fetching quiz {quiz_id}: {e}")
            return None
    
    def save_quiz_response(self, response_data: Dict[str, Any]) -> int:
        """Save user quiz submission to database"""
        query = """
            INSERT INTO quiz_responses (
                quiz_id, user_id, answers, score,
                total_questions, correct_answers, time_taken
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            result = self.execute_query(query, (
                response_data['quiz_id'],
                response_data['user_id'],
                json.dumps(response_data['answers']),
                response_data.get('score'),
                response_data.get('total_questions'),
                response_data.get('correct_answers'),
                response_data.get('time_taken')
            ), fetch='one')
            
            response_id = result[0]
            logger.info(f"✅ Saved quiz response: {response_data['quiz_id']} for user {response_data['user_id']} - Score: {response_data.get('score')}/{response_data.get('total_questions')}")
            return response_id
        except Exception as e:
            logger.error(f"Error saving quiz response: {e}")
            raise
    
    def get_user_quiz_responses(self, user_id: int, quiz_id: str = None) -> List[Dict[str, Any]]:
        """Get user's quiz submission history"""
        if quiz_id:
            query = """
                SELECT id, quiz_id, user_id, answers, score,
                       total_questions, correct_answers, time_taken, submitted_at
                FROM quiz_responses
                WHERE user_id = %s AND quiz_id = %s
                ORDER BY submitted_at DESC
            """
            params = (user_id, quiz_id)
        else:
            query = """
                SELECT id, quiz_id, user_id, answers, score,
                       total_questions, correct_answers, time_taken, submitted_at
                FROM quiz_responses
                WHERE user_id = %s
                ORDER BY submitted_at DESC
            """
            params = (user_id,)
        
        try:
            results = self.execute_query(query, params, fetch='all')
            responses = []
            for r in results:
                response = dict(r)
                if response.get('submitted_at'):
                    response['submitted_at'] = response['submitted_at'].isoformat()
                # Parse JSON answers if stored as string
                if isinstance(response.get('answers'), str):
                    response['answers'] = json.loads(response['answers'])
                responses.append(response)
            
            return responses
        except Exception as e:
            logger.error(f"Error fetching quiz responses for user {user_id}: {e}")
            return []
    
    def get_user_quiz_stats(self, user_id: int) -> Dict[str, Any]:
        """Get quiz statistics for a user"""
        query = """
            SELECT 
                COUNT(*) as total_attempts,
                AVG(score) as avg_score,
                MAX(score) as best_score,
                SUM(CASE WHEN score >= 70 THEN 1 ELSE 0 END) as passed_count
            FROM quiz_responses
            WHERE user_id = %s
        """
        
        try:
            result = self.execute_query(query, (user_id,), fetch='one')
            if result:
                stats = dict(result)
                # Convert Decimal to float for JSON serialization
                if stats.get('avg_score'):
                    stats['avg_score'] = float(stats['avg_score'])
                return stats
            return {
                'total_attempts': 0,
                'avg_score': 0,
                'best_score': 0,
                'passed_count': 0
            }
        except Exception as e:
            logger.error(f"Error fetching quiz stats for user {user_id}: {e}")
            return {
                'total_attempts': 0,
                'avg_score': 0,
                'best_score': 0,
                'passed_count': 0
            }
    
    # ============= SESSION OPERATIONS =============
    
    def get_user_session(self, user_id: int) -> Optional[Dict]:
        """Get active session for a user"""
        query = """
            SELECT 
                id, user_id, session_id, current_course_id,
                ip_address, user_agent, device_type, message_count,
                is_active, started_at, last_activity_at, expires_at
            FROM user_sessions
            WHERE user_id = %s AND is_active = true
            ORDER BY last_activity_at DESC
            LIMIT 1
        """
        
        try:
            result = self.execute_query(query, (user_id,), fetch='one')
            if result:
                session = dict(result)
                # Convert timestamps
                for field in ['started_at', 'last_activity_at', 'expires_at']:
                    if session.get(field):
                        session[field] = session[field].isoformat()
                return session
            return None
        except Exception as e:
            logger.error(f"Error fetching session for user {user_id}: {e}")
            return None
    
    def create_user_session(
        self, 
        user_id: int, 
        session_id: int,
        ip_address: str = None,
        user_agent: str = None,
        device_type: str = None
    ) -> Optional[Dict]:
        """Create new session for user, deactivating any existing active sessions"""
        
        # CRITICAL: Check one more time if active session exists (race condition protection)
        existing = self.get_user_session(user_id)
        if existing and existing.get('is_active'):
            logger.info(f"🔄 Found existing active session {existing['session_id']} during create, reusing it")
            return existing
        
        # Deactivate all existing active sessions for this user before creating new one
        deactivate_query = """
            UPDATE user_sessions 
            SET is_active = false 
            WHERE user_id = %s AND is_active = true
        """
        
        insert_query = """
            INSERT INTO user_sessions (
                user_id, session_id, ip_address, user_agent, device_type,
                is_active, started_at, last_activity_at, expires_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, user_id, session_id, started_at, last_activity_at, expires_at
        """
        
        now = datetime.utcnow()
        expires_at = now + timedelta(days=7)  # Sessions expire after 7 days
        
        try:
            # Deactivate old sessions
            self.execute_query(deactivate_query, (user_id,))
            logger.info(f"🔒 Deactivated old sessions for user {user_id}")
            
            # Create new session
            result = self.execute_query(
                insert_query,
                (user_id, session_id, ip_address, user_agent, device_type, 
                 True, now, now, expires_at),
                fetch='one'
            )
            
            if result:
                session = dict(result)
                for field in ['started_at', 'last_activity_at', 'expires_at']:
                    if session.get(field):
                        session[field] = session[field].isoformat()
                logger.info(f"✅ Created session {session_id} for user {user_id}")
                return session
            return None
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def update_session_activity(self, session_id: int):
        """Update session last_activity_at"""
        query = """
            UPDATE user_sessions
            SET last_activity_at = %s
            WHERE session_id = %s AND is_active = true
        """
        
        try:
            self.execute_query(query, (datetime.utcnow(), session_id))
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
    
    def end_session(self, session_id: int):
        """End a session"""
        query = """
            UPDATE user_sessions
            SET is_active = false, ended_at = %s
            WHERE session_id = %s
        """
        
        try:
            self.execute_query(query, (datetime.utcnow(), session_id))
            logger.info(f"✅ Ended session {session_id}")
        except Exception as e:
            logger.error(f"Error ending session: {e}")
    
    # ============= MESSAGE OPERATIONS =============
    
    def get_session_messages(
        self, 
        session_id: int, 
        limit: int = 20
    ) -> List[Dict]:
        """Get messages for a session (last N messages)"""
        query = """
            SELECT 
                id, user_id, session_id, role, content, message_type,
                course_id, module_id, topic_id, metadata, tokens_used,
                model_used, audio_url, transcript, created_at
            FROM messages
            WHERE session_id = (SELECT id FROM user_sessions WHERE session_id = %s)
            ORDER BY created_at DESC
            LIMIT %s
        """
        
        try:
            result = self.execute_query(query, (session_id, limit), fetch='all')
            if not result:
                return []
            
            # Reverse to get chronological order and convert to dict
            messages = []
            for row in reversed(result):
                msg = dict(row)
                if msg.get('created_at'):
                    msg['created_at'] = msg['created_at'].isoformat()
                messages.append(msg)
            
            return messages
        except Exception as e:
            logger.error(f"Error fetching messages for session {session_id}: {e}")
            return []
    
    def add_message(
        self,
        user_id: int,
        session_id: int,
        role: str,
        content: str,
        message_type: str = 'text',
        course_id: int = None,
        metadata: Dict = None,
        tokens_used: int = None,
        model_used: str = None
    ) -> Optional[Dict]:
        """Add message to session"""
        query = """
            INSERT INTO messages (
                user_id, session_id, role, content, message_type,
                course_id, metadata, tokens_used, model_used, created_at
            ) VALUES (
                %s, 
                (SELECT id FROM user_sessions WHERE session_id = %s),
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id, created_at
        """
        
        try:
            # Convert metadata dict to JSON
            metadata_json = json.dumps(metadata) if metadata else None
            
            result = self.execute_query(
                query,
                (user_id, session_id, role, content, message_type, 
                 course_id, metadata_json, tokens_used, model_used, datetime.utcnow()),
                fetch='one'
            )
            
            if result:
                msg = dict(result)
                if msg.get('created_at'):
                    msg['created_at'] = msg['created_at'].isoformat()
                return msg
            return None
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            return None
    
    def get_conversation_history(
        self,
        session_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """Get conversation history formatted for LLM (last N turns = 2N messages)"""
        logger.info(f"🔍 [CONVERSATION HISTORY] Fetching history for session_id: {session_id}, limit: {limit} turns")
        
        messages = self.get_session_messages(session_id, limit=limit * 2)
        
        logger.info(f"📚 [CONVERSATION HISTORY] Retrieved {len(messages)} messages from DB")
        
        # Format for LLM: simple role/content pairs
        conversation = []
        for idx, msg in enumerate(messages):
            role = msg['role']
            content = msg['content']
            conversation.append({
                "role": role,
                "content": content
            })
            # Log each message for debugging
            content_preview = content[:100] + "..." if len(content) > 100 else content
            logger.info(f"  [{idx+1}] {role}: {content_preview}")
        
        logger.info(f"✅ [CONVERSATION HISTORY] Formatted {len(conversation)} messages for LLM")
        return conversation
    
    # ============= ADMIN DASHBOARD OPERATIONS =============
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get statistics for admin dashboard"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            stats = {}
            
            # Total courses
            cur.execute("SELECT COUNT(*) as count FROM courses")
            stats['total_courses'] = cur.fetchone()['count']
            
            # Total users
            cur.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cur.fetchone()['count']
            
            # Users by role
            cur.execute("""
                SELECT role, COUNT(*) as count 
                FROM users 
                GROUP BY role
            """)
            stats['users_by_role'] = {row['role']: row['count'] for row in cur.fetchall()}
            
            # Active sessions (last 24 hours)
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM user_sessions 
                WHERE is_active = true 
                AND last_activity_at > NOW() - INTERVAL '24 hours'
            """)
            stats['active_sessions_24h'] = cur.fetchone()['count']
            
            # Total messages
            cur.execute("SELECT COUNT(*) as count FROM messages")
            stats['total_messages'] = cur.fetchone()['count']
            
            # Total enrollments
            cur.execute("SELECT COUNT(*) as count FROM enrollments")
            stats['total_enrollments'] = cur.fetchone()['count']
            
            # Paid enrollments
            cur.execute("SELECT COUNT(*) as count FROM enrollments WHERE is_paid = true")
            stats['paid_enrollments'] = cur.fetchone()['count']
            
            # Total purchases
            cur.execute("SELECT COUNT(*) as count FROM user_purchases")
            stats['total_purchases'] = cur.fetchone()['count']
            
            # Total revenue
            cur.execute("""
                SELECT SUM(amount) as total_revenue 
                FROM user_purchases 
                WHERE status = 'completed'
            """)
            revenue_result = cur.fetchone()
            stats['total_revenue'] = float(revenue_result['total_revenue']) if revenue_result['total_revenue'] else 0.0
            
            # Course list with enrollment counts
            cur.execute("""
                SELECT 
                    c.id, c.title, c.country, c.level,
                    COUNT(DISTINCT e.id) as enrollment_count,
                    COUNT(DISTINCT CASE WHEN e.is_paid THEN e.id END) as paid_enrollment_count
                FROM courses c
                LEFT JOIN enrollments e ON c.id = e.course_id
                GROUP BY c.id, c.title, c.country, c.level
                ORDER BY enrollment_count DESC
            """)
            stats['courses'] = [dict(row) for row in cur.fetchall()]
            
            # Recent users (last 10) with detailed info
            cur.execute("""
                SELECT 
                    id, username, email, role, 
                    student_type, college_name, degree, school_class, school_affiliation,
                    institution, subject, experience,
                    terms_accepted, email_verified, is_active, 
                    last_login_at, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 10
            """)
            stats['recent_users'] = []
            for row in cur.fetchall():
                user = dict(row)
                # Convert timestamps to ISO format
                for field in ['created_at', 'updated_at', 'last_login_at']:
                    if user.get(field):
                        user[field] = user[field].isoformat()
                stats['recent_users'].append(user)
            
            # Session activity (last 7 days)
            cur.execute("""
                SELECT 
                    DATE(started_at) as date,
                    COUNT(*) as session_count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM user_sessions
                WHERE started_at > NOW() - INTERVAL '7 days'
                GROUP BY DATE(started_at)
                ORDER BY date DESC
            """)
            stats['session_activity_7d'] = []
            for row in cur.fetchall():
                activity = dict(row)
                if activity.get('date'):
                    activity['date'] = activity['date'].isoformat()
                stats['session_activity_7d'].append(activity)
            
            conn.commit()
            return stats
            
        except Exception as e:
            logger.error(f"Error fetching dashboard stats: {e}")
            if conn:
                conn.rollback()
            return {}
        finally:
            if conn:
                cur.close()
                self.return_connection(conn)
    
    def get_all_users(
        self, 
        role: str = None, 
        is_active: bool = None, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all users with optional filtering"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Build query with optional filters
            query = """
                SELECT 
                    id, username, email, role, 
                    student_type, college_name, degree, school_class, school_affiliation,
                    institution, subject, experience,
                    terms_accepted, email_verified, is_active, 
                    last_login_at, created_at, updated_at
                FROM users
                WHERE 1=1
            """
            params = []
            
            if role:
                query += " AND role = %s"
                params.append(role)
            
            if is_active is not None:
                query += " AND is_active = %s"
                params.append(is_active)
            
            query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cur.execute(query, params)
            
            users = []
            for row in cur.fetchall():
                user = dict(row)
                # Convert timestamps to ISO format
                for field in ['created_at', 'updated_at', 'last_login_at']:
                    if user.get(field):
                        user[field] = user[field].isoformat()
                users.append(user)
            
            conn.commit()
            return users
            
        except Exception as e:
            logger.error(f"Error fetching users: {e}")
            if conn:
                conn.rollback()
            return []
        finally:
            if conn:
                cur.close()
                self.return_connection(conn)
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed user information by ID"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cur.execute("""
                SELECT 
                    id, username, email, role, 
                    student_type, college_name, degree, school_class, school_affiliation,
                    institution, subject, experience,
                    terms_accepted, email_verified, is_active, 
                    last_login_at, created_at, updated_at
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            row = cur.fetchone()
            if row:
                user = dict(row)
                # Convert timestamps to ISO format
                for field in ['created_at', 'updated_at', 'last_login_at']:
                    if user.get(field):
                        user[field] = user[field].isoformat()
                return user
            return None
            
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                cur.close()
                self.return_connection(conn)
    
    # ============= ASSESSMENT SYSTEM OPERATIONS =============
    
    def create_uploaded_note(
        self,
        user_id: int,
        session_id: int,
        file_name: str,
        file_type: str,
        file_size: int,
        content: str,
        file_url: str = None
    ) -> Optional[int]:
        """Create new uploaded note record"""
        query = """
            INSERT INTO uploaded_notes (
                user_id, session_id, file_name, file_type, file_size,
                content, file_url, processing_status, uploaded_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            result = self.execute_query(
                query,
                (user_id, session_id, file_name, file_type, file_size,
                 content, file_url, 'completed', datetime.utcnow()),
                fetch='one'
            )
            
            if result:
                note_id = result['id']
                logger.info(f"✅ Created uploaded note {note_id} for user {user_id}")
                return note_id
            return None
        except Exception as e:
            logger.error(f"Error creating uploaded note: {e}")
            return None
    
    def get_uploaded_note(self, note_id: int) -> Optional[Dict]:
        """Get uploaded note by ID"""
        query = """
            SELECT * FROM uploaded_notes WHERE id = %s
        """
        
        try:
            result = self.execute_query(query, (note_id,), fetch='one')
            if result:
                note = dict(result)
                for field in ['uploaded_at', 'processed_at', 'created_at', 'updated_at']:
                    if note.get(field):
                        note[field] = note[field].isoformat()
                return note
            return None
        except Exception as e:
            logger.error(f"Error fetching uploaded note {note_id}: {e}")
            return None
    
    def get_user_uploaded_notes(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get all uploaded notes for a user"""
        query = """
            SELECT * FROM uploaded_notes 
            WHERE user_id = %s 
            ORDER BY uploaded_at DESC 
            LIMIT %s
        """
        
        try:
            result = self.execute_query(query, (user_id, limit), fetch='all')
            notes = []
            for row in result:
                note = dict(row)
                for field in ['uploaded_at', 'processed_at', 'created_at', 'updated_at']:
                    if note.get(field):
                        note[field] = note[field].isoformat()
                notes.append(note)
            return notes
        except Exception as e:
            logger.error(f"Error fetching user notes: {e}")
            return []
    
    def create_assessment(
        self,
        user_id: int,
        session_id: int,
        uploaded_note_id: int,
        title: str,
        description: str,
        difficulty_level: str = 'medium',
        total_questions: int = 0,
        topics_covered: List[str] = None
    ) -> Optional[int]:
        """Create new assessment"""
        query = """
            INSERT INTO assessments (
                user_id, session_id, uploaded_note_id, title, description,
                difficulty_level, total_questions, topics_covered, status, generated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            result = self.execute_query(
                query,
                (user_id, session_id, uploaded_note_id, title, description,
                 difficulty_level, total_questions, topics_covered or [], 'active', datetime.utcnow()),
                fetch='one'
            )
            
            if result:
                assessment_id = result['id']
                logger.info(f"✅ Created assessment {assessment_id}")
                return assessment_id
            return None
        except Exception as e:
            logger.error(f"Error creating assessment: {e}")
            return None
    
    def get_assessment(self, assessment_id: int) -> Optional[Dict]:
        """Get assessment by ID"""
        query = """
            SELECT * FROM assessments WHERE id = %s
        """
        
        try:
            result = self.execute_query(query, (assessment_id,), fetch='one')
            if result:
                assessment = dict(result)
                for field in ['generated_at', 'created_at', 'updated_at']:
                    if assessment.get(field):
                        assessment[field] = assessment[field].isoformat()
                return assessment
            return None
        except Exception as e:
            logger.error(f"Error fetching assessment {assessment_id}: {e}")
            return None
    
    def create_assessment_question(
        self,
        assessment_id: int,
        question_number: int,
        question_text: str,
        options: Dict,
        correct_answer: str,
        explanation: str = None,
        difficulty: str = 'medium',
        points: int = 1
    ) -> Optional[int]:
        """Create assessment question"""
        query = """
            INSERT INTO assessment_questions (
                assessment_id, question_number, question_text, question_type,
                options, correct_answer, explanation, difficulty, points
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        
        try:
            import json
            result = self.execute_query(
                query,
                (assessment_id, question_number, question_text, 'multiple_choice',
                 json.dumps(options), correct_answer, explanation, difficulty, points),
                fetch='one'
            )
            
            if result:
                return result['id']
            return None
        except Exception as e:
            logger.error(f"Error creating assessment question: {e}")
            return None
    
    def get_assessment_questions(self, assessment_id: int) -> List[Dict]:
        """Get all questions for an assessment"""
        query = """
            SELECT * FROM assessment_questions 
            WHERE assessment_id = %s 
            ORDER BY question_number ASC
        """
        
        try:
            result = self.execute_query(query, (assessment_id,), fetch='all')
            questions = []
            for row in result:
                question = dict(row)
                if question.get('created_at'):
                    question['created_at'] = question['created_at'].isoformat()
                questions.append(question)
            return questions
        except Exception as e:
            logger.error(f"Error fetching assessment questions: {e}")
            return []
    
    def save_assessment_response(
        self,
        user_id: int,
        session_id: int,
        assessment_id: int,
        answers: Dict,
        score: int,
        percentage: float,
        total_questions: int,
        correct_answers: int,
        incorrect_answers: int,
        time_taken: int = None
    ) -> Optional[int]:
        """Save user's assessment response"""
        query = """
            INSERT INTO user_assessment_responses (
                user_id, session_id, assessment_id, attempt_number, answers,
                score, percentage, total_questions, correct_answers, 
                incorrect_answers, unanswered, time_taken, status, submitted_at
            ) VALUES (
                %s, %s, %s, 
                (SELECT COALESCE(MAX(attempt_number), 0) + 1 
                 FROM user_assessment_responses 
                 WHERE user_id = %s AND assessment_id = %s),
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id, attempt_number
        """
        
        try:
            import json
            unanswered = total_questions - correct_answers - incorrect_answers
            
            result = self.execute_query(
                query,
                (user_id, session_id, assessment_id, user_id, assessment_id,
                 json.dumps(answers), score, percentage, total_questions,
                 correct_answers, incorrect_answers, unanswered, time_taken,
                 'graded', datetime.utcnow()),
                fetch='one'
            )
            
            if result:
                logger.info(f"✅ Saved assessment response {result['id']} (attempt #{result['attempt_number']})")
                return result['id']
            return None
        except Exception as e:
            logger.error(f"Error saving assessment response: {e}")
            return None
    
    def get_user_assessment_responses(self, user_id: int, assessment_id: int) -> List[Dict]:
        """Get user's responses for an assessment"""
        query = """
            SELECT * FROM user_assessment_responses 
            WHERE user_id = %s AND assessment_id = %s 
            ORDER BY attempt_number DESC
        """
        
        try:
            result = self.execute_query(query, (user_id, assessment_id), fetch='all')
            responses = []
            for row in result:
                response = dict(row)
                for field in ['started_at', 'submitted_at', 'created_at', 'updated_at']:
                    if response.get(field):
                        response[field] = response[field].isoformat()
                responses.append(response)
            return responses
        except Exception as e:
            logger.error(f"Error fetching assessment responses: {e}")
            return []
    
    def get_user_assessments(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get all assessments for a user"""
        query = """
            SELECT a.*, un.file_name, un.file_type,
                   COUNT(DISTINCT uar.id) as attempt_count,
                   MAX(uar.percentage) as best_score
            FROM assessments a
            JOIN uploaded_notes un ON a.uploaded_note_id = un.id
            LEFT JOIN user_assessment_responses uar ON a.id = uar.assessment_id AND uar.user_id = %s
            WHERE a.user_id = %s
            GROUP BY a.id, un.file_name, un.file_type
            ORDER BY a.generated_at DESC
            LIMIT %s
        """
        
        try:
            result = self.execute_query(query, (user_id, user_id, limit), fetch='all')
            assessments = []
            for row in result:
                assessment = dict(row)
                for field in ['generated_at', 'created_at', 'updated_at']:
                    if assessment.get(field):
                        assessment[field] = assessment[field].isoformat()
                assessments.append(assessment)
            return assessments
        except Exception as e:
            logger.error(f"Error fetching user assessments: {e}")
            return []
    
    # ============= COMPLETION TRACKING OPERATIONS =============
    
    def mark_topic_complete(
        self,
        user_id: int,
        course_id: int,
        module_id: int,
        topic_id: int
    ) -> bool:
        """Mark a topic as completed for a user"""
        query = """
            INSERT INTO user_progress (
                user_id, course_id, module_id, topic_id, 
                status, progress_percentage, last_accessed, completion_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, course_id, module_id, topic_id)
            DO UPDATE SET
                status = 'completed',
                progress_percentage = 100,
                last_accessed = %s,
                completion_date = %s
            RETURNING id
        """
        
        try:
            now = datetime.utcnow()
            result = self.execute_query(
                query,
                (user_id, course_id, module_id, topic_id, 
                 'completed', 100, now, now, now, now),
                fetch='one'
            )
            
            if result:
                logger.info(f"✅ Marked topic {topic_id} complete for user {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking topic complete: {e}")
            return False
    
    def get_user_progress(self, user_id: int, course_id: int) -> List[Dict]:
        """Get user's progress for a course"""
        query = """
            SELECT up.*, 
                   c.title as course_title,
                   m.title as module_title,
                   t.title as topic_title
            FROM user_progress up
            JOIN courses c ON up.course_id = c.id
            LEFT JOIN modules m ON up.module_id = m.id
            LEFT JOIN topics t ON up.topic_id = t.id
            WHERE up.user_id = %s AND up.course_id = %s
            ORDER BY up.last_accessed DESC
        """
        
        try:
            result = self.execute_query(query, (user_id, course_id), fetch='all')
            progress = []
            for row in result:
                prog = dict(row)
                for field in ['last_accessed', 'completion_date']:
                    if prog.get(field):
                        prog[field] = prog[field].isoformat()
                progress.append(prog)
            return progress
        except Exception as e:
            logger.error(f"Error fetching user progress: {e}")
            return []
    
    def get_course_completion_stats(self, user_id: int, course_id: int) -> Dict:
        """Get completion statistics for a course"""
        conn = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get total topics in course
            cur.execute("""
                SELECT COUNT(*) as total_topics
                FROM topics t
                JOIN modules m ON t.module_id = m.id
                WHERE m.course_id = %s
            """, (course_id,))
            total_topics = cur.fetchone()['total_topics']
            
            # Get completed topics
            cur.execute("""
                SELECT COUNT(*) as completed_topics
                FROM user_progress
                WHERE user_id = %s AND course_id = %s 
                AND status = 'completed' AND topic_id IS NOT NULL
            """, (user_id, course_id))
            completed_topics = cur.fetchone()['completed_topics']
            
            completion_percentage = (completed_topics / total_topics * 100) if total_topics > 0 else 0
            
            conn.commit()
            
            return {
                'total_topics': total_topics,
                'completed_topics': completed_topics,
                'completion_percentage': round(completion_percentage, 2)
            }
            
        except Exception as e:
            logger.error(f"Error fetching completion stats: {e}")
            if conn:
                conn.rollback()
            return {'total_topics': 0, 'completed_topics': 0, 'completion_percentage': 0}
        finally:
            if conn:
                cur.close()
                self.return_connection(conn)
    
    def close(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")


# Global instance
_db_service_v2 = None

def get_database_service() -> DatabaseServiceV2:
    """Get or create database service instance"""
    global _db_service_v2
    
    if _db_service_v2 is None:
        try:
            _db_service_v2 = DatabaseServiceV2()
            logger.info("✅ DatabaseServiceV2 initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize DatabaseServiceV2: {e}")
            raise
    
    return _db_service_v2
