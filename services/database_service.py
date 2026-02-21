"""
Database Service - PostgreSQL (Neon) integration
CURRENTLY DISABLED - Using JSON files for now

TODO: Enable when ready to migrate to Neon PostgreSQL
Instructions:
1. Create Neon account at https://neon.tech
2. Create database project
3. Get connection string
4. Add to config.py: DATABASE_URL = "postgresql://..."
5. Uncomment the code below
6. Run: pip install asyncpg sqlalchemy
7. Run migrations: python -m alembic upgrade head
"""

# PLACEHOLDER: Database configuration
DATABASE_URL = None  # TODO: Add Neon connection string
# Example: "postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/profai?sslmode=require"

USE_DATABASE = False  # TODO: Set to True when Neon is configured

"""
# UNCOMMENT BELOW WHEN READY TO USE NEON POSTGRESQL

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import logging

Base = declarative_base()

# ============= DATABASE MODELS =============

class Course(Base):
    '''Courses table - stores course metadata and full course structure'''
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, unique=True, nullable=False)  # For compatibility with old system
    course_title = Column(String(500), nullable=False)
    course_data = Column(JSON, nullable=False)  # Full course JSON structure
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")
    
    def to_dict(self):
        '''Convert to dictionary matching current JSON structure'''
        return self.course_data

class Quiz(Base):
    '''Quizzes table - stores quiz data'''
    __tablename__ = 'quizzes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.course_id'), nullable=False)
    quiz_id = Column(String(100), unique=True, nullable=False)
    quiz_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    course = relationship("Course", back_populates="quizzes")
    answers = relationship("QuizAnswer", back_populates="quiz", cascade="all, delete-orphan")

class QuizAnswer(Base):
    '''Quiz answers table - stores user quiz submissions'''
    __tablename__ = 'quiz_answers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String(100), ForeignKey('quizzes.quiz_id'), nullable=False)
    user_id = Column(String(100), nullable=True)  # Optional user identification
    answers = Column(JSON, nullable=False)
    score = Column(Integer, nullable=True)
    submitted_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="answers")

class JobStatusDB(Base):
    '''Job status table - tracks background processing jobs'''
    __tablename__ = 'job_status'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), unique=True, nullable=False)
    status = Column(String(50), nullable=False)  # pending, processing, completed, failed
    progress = Column(Integer, default=0)
    message = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

# ============= DATABASE SERVICE =============

class DatabaseService:
    '''Service for database operations'''
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def init_db(self):
        '''Initialize database tables'''
        Base.metadata.create_all(self.engine)
        logging.info("Database tables created successfully")
    
    def get_session(self):
        '''Get database session'''
        return self.SessionLocal()
    
    # ============= COURSE OPERATIONS =============
    
    def save_course(self, course_data: dict) -> int:
        '''Save course to database'''
        session = self.get_session()
        try:
            # Check if course_id exists
            existing = session.query(Course).filter_by(
                course_id=course_data['course_id']
            ).first()
            
            if existing:
                # Update existing
                existing.course_data = course_data
                existing.updated_at = datetime.now()
            else:
                # Create new
                course = Course(
                    course_id=course_data['course_id'],
                    course_title=course_data['course_title'],
                    course_data=course_data
                )
                session.add(course)
            
            session.commit()
            return course_data['course_id']
            
        except Exception as e:
            session.rollback()
            logging.error(f"Error saving course: {e}")
            raise
        finally:
            session.close()
    
    def get_all_courses(self) -> list:
        '''Get all courses'''
        session = self.get_session()
        try:
            courses = session.query(Course).all()
            return [course.to_dict() for course in courses]
        finally:
            session.close()
    
    def get_course(self, course_id: int) -> dict:
        '''Get single course by ID'''
        session = self.get_session()
        try:
            course = session.query(Course).filter_by(course_id=course_id).first()
            return course.to_dict() if course else None
        finally:
            session.close()
    
    def get_next_course_id(self) -> int:
        '''Get next available course ID'''
        session = self.get_session()
        try:
            max_id = session.query(Course.course_id).order_by(
                Course.course_id.desc()
            ).first()
            return (max_id[0] + 1) if max_id else 1
        finally:
            session.close()
    
    # ============= QUIZ OPERATIONS =============
    
    def save_quiz(self, course_id: int, quiz_id: str, quiz_data: dict):
        '''Save quiz to database'''
        session = self.get_session()
        try:
            existing = session.query(Quiz).filter_by(quiz_id=quiz_id).first()
            
            if existing:
                existing.quiz_data = quiz_data
            else:
                quiz = Quiz(
                    course_id=course_id,
                    quiz_id=quiz_id,
                    quiz_data=quiz_data
                )
                session.add(quiz)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logging.error(f"Error saving quiz: {e}")
            raise
        finally:
            session.close()
    
    def get_quiz(self, quiz_id: str) -> dict:
        '''Get quiz by ID'''
        session = self.get_session()
        try:
            quiz = session.query(Quiz).filter_by(quiz_id=quiz_id).first()
            return quiz.quiz_data if quiz else None
        finally:
            session.close()
    
    # ============= JOB STATUS OPERATIONS =============
    
    def create_job(self, job_id: str) -> str:
        '''Create new job in database'''
        session = self.get_session()
        try:
            job = JobStatusDB(
                job_id=job_id,
                status='pending'
            )
            session.add(job)
            session.commit()
            return job_id
        except Exception as e:
            session.rollback()
            logging.error(f"Error creating job: {e}")
            raise
        finally:
            session.close()
    
    def update_job_status(self, job_id: str, status: str, message: str = None):
        '''Update job status'''
        session = self.get_session()
        try:
            job = session.query(JobStatusDB).filter_by(job_id=job_id).first()
            if job:
                job.status = status
                if message:
                    job.message = message
                
                if status == 'processing' and not job.started_at:
                    job.started_at = datetime.now()
                elif status in ['completed', 'failed']:
                    job.completed_at = datetime.now()
                
                session.commit()
        finally:
            session.close()
    
    def get_job_status(self, job_id: str) -> dict:
        '''Get job status'''
        session = self.get_session()
        try:
            job = session.query(JobStatusDB).filter_by(job_id=job_id).first()
            if job:
                return {
                    'job_id': job.job_id,
                    'status': job.status,
                    'progress': job.progress,
                    'message': job.message,
                    'result': job.result,
                    'error': job.error,
                    'created_at': job.created_at.isoformat(),
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None
                }
            return None
        finally:
            session.close()

# ============= INITIALIZATION =============

def get_database_service():
    '''Get database service instance'''
    if not DATABASE_URL:
        logging.warning("DATABASE_URL not configured, using JSON files")
        return None
    
    try:
        db_service = DatabaseService(DATABASE_URL)
        db_service.init_db()
        logging.info("Database service initialized successfully")
        return db_service
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        return None

# Global instance
db_service = get_database_service() if USE_DATABASE else None

END OF COMMENTED CODE
"""

# ============= MIGRATION HELPER =============

def migrate_json_to_database():
    """
    Helper function to migrate existing JSON data to Neon PostgreSQL
    
    TODO: Run this once when ready to migrate:
    1. Enable USE_DATABASE = True
    2. Configure DATABASE_URL
    3. Run: python -c "from services.database_service import migrate_json_to_database; migrate_json_to_database()"
    
    This will:
    - Read all JSON files from data/courses/
    - Import them into Neon database
    - Preserve course_ids
    - Backup JSON files
    """
    pass
    
    """
    # UNCOMMENT WHEN READY TO MIGRATE
    
    import json
    import os
    import shutil
    from datetime import datetime
    
    # Backup JSON files first
    backup_dir = f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    shutil.copytree("data/courses", f"{backup_dir}/courses")
    shutil.copytree("data/quizzes", f"{backup_dir}/quizzes")
    print(f"Backed up JSON files to {backup_dir}")
    
    if not db_service:
        print("ERROR: Database not configured!")
        return
    
    # Migrate courses
    courses_file = "data/courses/course_output.json"
    if os.path.exists(courses_file):
        with open(courses_file, 'r', encoding='utf-8') as f:
            courses_data = json.load(f)
            
            # Handle both single course and list format
            if isinstance(courses_data, dict):
                courses_data = [courses_data]
            
            for course in courses_data:
                db_service.save_course(course)
                print(f"Migrated course: {course['course_title']}")
    
    # Migrate quizzes
    quizzes_dir = "data/quizzes"
    if os.path.exists(quizzes_dir):
        for filename in os.listdir(quizzes_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(quizzes_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    quiz_data = json.load(f)
                    quiz_id = filename.replace('.json', '')
                    # Extract course_id from quiz_data or filename
                    course_id = quiz_data.get('course_id', 1)
                    db_service.save_quiz(course_id, quiz_id, quiz_data)
                    print(f"Migrated quiz: {filename}")
    
    print("Migration complete!")
    """

# For now, return None since database is not enabled
def get_db_service():
    """Get database service if enabled, otherwise None"""
    return None  # TODO: Return db_service when USE_DATABASE is True
