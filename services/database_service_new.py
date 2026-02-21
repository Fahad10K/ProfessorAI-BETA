"""
Database Service - PostgreSQL (Neon) Integration
Production-ready database operations using the normalized schema

This matches the schema from migrations/001_initial_schema.sql
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ARRAY, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
USE_DATABASE = os.getenv('USE_DATABASE', 'false').lower() == 'true'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()

# ============================================================
# DATABASE MODELS (Match migration schema)
# ============================================================

class User(Base):
    """User accounts (students, teachers, admins)"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    full_name = Column(String(255))
    role = Column(String(50), default='student')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    metadata = Column(JSONB)


class Course(Base):
    """Main course entities"""
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    created_by = Column(String(100), ForeignKey('users.user_id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    status = Column(String(50), default='active')
    metadata = Column(JSONB)
    
    # Relationships
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")


class Module(Base):
    """Course modules (weekly structure)"""
    __tablename__ = 'modules'
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.course_id', ondelete='CASCADE'), nullable=False)
    week = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    learning_objectives = Column(ARRAY(Text))
    order_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    course = relationship("Course", back_populates="modules")
    topics = relationship("Topic", back_populates="module", cascade="all, delete-orphan")


class Topic(Base):
    """Module topics (individual lessons)"""
    __tablename__ = 'topics'
    
    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey('modules.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer)
    estimated_time = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    module = relationship("Module", back_populates="topics")


class Quiz(Base):
    """Quiz metadata"""
    __tablename__ = 'quizzes'
    
    id = Column(Integer, primary_key=True)
    quiz_id = Column(String(100), unique=True, nullable=False)
    course_id = Column(Integer, ForeignKey('courses.course_id', ondelete='CASCADE'), nullable=False)
    module_id = Column(Integer, ForeignKey('modules.id', ondelete='SET NULL'))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    quiz_type = Column(String(50), default='module')
    passing_score = Column(Integer, default=70)
    time_limit = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    course = relationship("Course", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    """Individual quiz questions"""
    __tablename__ = 'quiz_questions'
    
    id = Column(Integer, primary_key=True)
    quiz_id = Column(String(100), ForeignKey('quizzes.quiz_id', ondelete='CASCADE'), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=False)
    correct_answer = Column(String(1), nullable=False)
    explanation = Column(Text)
    difficulty = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions")


class QuizResponse(Base):
    """User quiz submissions and scores"""
    __tablename__ = 'quiz_responses'
    
    id = Column(Integer, primary_key=True)
    quiz_id = Column(String(100), ForeignKey('quizzes.quiz_id', ondelete='CASCADE'), nullable=False)
    user_id = Column(String(100), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    answers = Column(JSONB, nullable=False)
    score = Column(Integer)
    total_questions = Column(Integer)
    correct_answers = Column(Integer)
    submitted_at = Column(DateTime, default=datetime.now)
    time_taken = Column(Integer)


class JobQueue(Base):
    """Background job tracking (Celery tasks)"""
    __tablename__ = 'job_queue'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(String(100), unique=True, nullable=False)
    task_id = Column(String(100))
    job_type = Column(String(50), nullable=False)
    status = Column(String(50), default='pending')
    progress = Column(Integer, default=0)
    message = Column(Text)
    result = Column(JSONB)
    error = Column(Text)
    created_by = Column(String(100), ForeignKey('users.user_id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)


# ============================================================
# DATABASE SERVICE CLASS
# ============================================================

class DatabaseService:
    """Database operations service"""
    
    def __init__(self, database_url: str = None):
        """Initialize database connection"""
        self.database_url = database_url or DATABASE_URL
        
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")
        
        self.engine = create_engine(
            self.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("✅ Database service initialized")
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    # ============================================================
    # COURSE OPERATIONS
    # ============================================================
    
    def create_course(self, course_data: Dict[str, Any], created_by: str = 'system_teacher') -> int:
        """Create a new course with modules and topics"""
        with self.get_session() as session:
            # Create course
            course = Course(
                course_id=course_data.get('course_id', 1),
                title=course_data.get('course_title', 'Untitled Course'),
                description=course_data.get('description', ''),
                created_by=created_by,
                status='active'
            )
            session.add(course)
            session.flush()  # Get course.id
            
            # Create modules
            for module_data in course_data.get('modules', []):
                module = Module(
                    course_id=course.course_id,
                    week=module_data.get('week', 1),
                    title=module_data.get('title', ''),
                    description=module_data.get('description', ''),
                    learning_objectives=module_data.get('learning_objectives', []),
                    order_index=module_data.get('week', 1)
                )
                session.add(module)
                session.flush()  # Get module.id
                
                # Create topics
                for idx, topic_data in enumerate(module_data.get('sub_topics', [])):
                    topic = Topic(
                        module_id=module.id,
                        title=topic_data.get('title', ''),
                        content=topic_data.get('content', ''),
                        order_index=idx + 1
                    )
                    session.add(topic)
            
            session.commit()
            logger.info(f"✅ Created course: {course.title} (ID: {course.course_id})")
            return course.course_id
    
    def get_course(self, course_id: int) -> Optional[Dict[str, Any]]:
        """Get course with all modules and topics"""
        with self.get_session() as session:
            course = session.query(Course).filter(Course.course_id == course_id).first()
            
            if not course:
                return None
            
            # Build course structure
            course_dict = {
                'course_id': course.course_id,
                'course_title': course.title,
                'description': course.description,
                'created_at': course.created_at.isoformat() if course.created_at else None,
                'modules': []
            }
            
            # Add modules
            for module in sorted(course.modules, key=lambda m: m.week):
                module_dict = {
                    'week': module.week,
                    'title': module.title,
                    'description': module.description,
                    'learning_objectives': module.learning_objectives or [],
                    'sub_topics': []
                }
                
                # Add topics
                for topic in sorted(module.topics, key=lambda t: t.order_index or 0):
                    topic_dict = {
                        'title': topic.title,
                        'content': topic.content
                    }
                    module_dict['sub_topics'].append(topic_dict)
                
                course_dict['modules'].append(module_dict)
            
            return course_dict
    
    def list_courses(self, created_by: str = None) -> List[Dict[str, Any]]:
        """List all courses"""
        with self.get_session() as session:
            query = session.query(Course)
            
            if created_by:
                query = query.filter(Course.created_by == created_by)
            
            courses = query.all()
            
            return [{
                'course_id': c.course_id,
                'course_title': c.title,
                'modules': len(c.modules),
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in courses]
    
    # ============================================================
    # QUIZ OPERATIONS
    # ============================================================
    
    def create_quiz(self, quiz_data: Dict[str, Any]) -> str:
        """Create a quiz with questions"""
        with self.get_session() as session:
            # Get module_id if module quiz
            module_id = None
            if quiz_data.get('module_week'):
                module = session.query(Module).filter(
                    Module.course_id == quiz_data.get('course_id'),
                    Module.week == quiz_data['module_week']
                ).first()
                if module:
                    module_id = module.id
            
            # Create quiz
            quiz = Quiz(
                quiz_id=quiz_data['quiz_id'],
                course_id=quiz_data.get('course_id', 1),
                module_id=module_id,
                title=quiz_data.get('title', 'Quiz'),
                quiz_type=quiz_data.get('quiz_type', 'module')
            )
            session.add(quiz)
            session.flush()
            
            # Create questions
            for question_data in quiz_data.get('questions', []):
                question = QuizQuestion(
                    quiz_id=quiz.quiz_id,
                    question_number=question_data.get('question_number', 1),
                    question_text=question_data.get('question', ''),
                    options=question_data.get('options', {}),
                    correct_answer=question_data.get('correct_answer', 'A'),
                    explanation=question_data.get('explanation', '')
                )
                session.add(question)
            
            session.commit()
            logger.info(f"✅ Created quiz: {quiz.quiz_id}")
            return quiz.quiz_id
    
    def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get quiz with all questions"""
        with self.get_session() as session:
            quiz = session.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
            
            if not quiz:
                return None
            
            return {
                'quiz_id': quiz.quiz_id,
                'title': quiz.title,
                'course_id': quiz.course_id,
                'questions': [{
                    'question_number': q.question_number,
                    'question': q.question_text,
                    'options': q.options,
                    'correct_answer': q.correct_answer,
                    'explanation': q.explanation
                } for q in sorted(quiz.questions, key=lambda q: q.question_number)]
            }
    
    # ============================================================
    # JOB TRACKING
    # ============================================================
    
    def create_job(self, job_id: str, task_id: str, job_type: str, created_by: str = None) -> None:
        """Create a job tracking record"""
        with self.get_session() as session:
            job = JobQueue(
                job_id=job_id,
                task_id=task_id,
                job_type=job_type,
                status='pending',
                created_by=created_by
            )
            session.add(job)
    
    def update_job_status(self, job_id: str, status: str, progress: int = None, 
                         message: str = None, result: Dict = None, error: str = None) -> None:
        """Update job status"""
        with self.get_session() as session:
            job = session.query(JobQueue).filter(JobQueue.job_id == job_id).first()
            
            if job:
                job.status = status
                if progress is not None:
                    job.progress = progress
                if message:
                    job.message = message
                if result:
                    job.result = result
                if error:
                    job.error = error
                
                if status == 'processing' and not job.started_at:
                    job.started_at = datetime.now()
                elif status in ['completed', 'failed']:
                    job.completed_at = datetime.now()


# ============================================================
# SINGLETON INSTANCE
# ============================================================

_db_service = None

def get_database_service() -> Optional[DatabaseService]:
    """Get database service singleton"""
    global _db_service
    
    if not USE_DATABASE:
        return None
    
    if _db_service is None:
        try:
            _db_service = DatabaseService()
        except Exception as e:
            logger.error(f"Failed to initialize database service: {e}")
            return None
    
    return _db_service
