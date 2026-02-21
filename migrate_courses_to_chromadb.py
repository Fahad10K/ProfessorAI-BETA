"""
Migration Script: Populate ChromaDB with Course Content from Neon DB

This script:
1. Retrieves all courses from Neon PostgreSQL database
2. Adds course content to ChromaDB with metadata (course_id, course_name, module, week, title)
3. Enables course-specific filtering for faster RAG retrieval

Usage:
    python migrate_courses_to_chromadb.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

import config
from core.cloud_vectorizer import CloudVectorizer
from services.database_service_v2 import DatabaseServiceV2


def get_courses_from_neon():
    """
    Retrieve all courses from Neon PostgreSQL database using DatabaseServiceV2.
    
    Returns:
        List of course dictionaries with complete structure:
        {
            "id": int,
            "title": str,
            "course_number": int,
            "modules": [
                {
                    "week": int,
                    "title": str,
                    "topics": [
                        {"title": str, "content": str}
                    ]
                }
            ]
        }
    """
    try:
        logger.info("Initializing database service...")
        db_service = DatabaseServiceV2()
        
        # Get list of all courses (basic info)
        logger.info("Fetching list of all courses...")
        courses_list = db_service.get_all_courses()
        
        if not courses_list:
            logger.warning("No courses found in database")
            return []
        
        logger.info(f"Found {len(courses_list)} courses, fetching full content...")
        
        # For each course, get complete content with modules and topics
        full_courses = []
        for course_basic in courses_list:
            course_id = course_basic.get('id')
            course_number = course_basic.get('course_number')
            
            logger.info(f"Fetching content for course ID {course_id} (course_number: {course_number})...")
            
            # Use the same method as the API endpoints
            course_full = db_service.get_course_with_content(course_number or course_id)
            
            if course_full:
                full_courses.append(course_full)
                module_count = len(course_full.get('modules', []))
                topic_count = sum(len(m.get('topics', [])) for m in course_full.get('modules', []))
                logger.info(f"  ✅ Course {course_id}: {module_count} modules, {topic_count} topics")
            else:
                logger.warning(f"  ⚠️ Could not fetch full content for course {course_id}")
        
        logger.info(f"Successfully retrieved {len(full_courses)} complete courses from database")
        return full_courses
        
    except Exception as e:
        logger.error(f"Error retrieving courses from database: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def get_courses_from_json():
    """
    Fallback: Retrieve courses from JSON file if database is not available.
    
    Returns:
        List of course dictionaries
    """
    json_path = Path(__file__).parent / "course_output.json"
    
    if not json_path.exists():
        logger.error(f"Course JSON file not found: {json_path}")
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            courses = json.load(f)
        
        logger.info(f"Retrieved {len(courses)} courses from JSON file")
        return courses
        
    except Exception as e:
        logger.error(f"Error reading courses from JSON: {e}")
        return []


def migrate_courses_to_chromadb(courses, skip_duplicates=True):
    """
    Migrate course content to ChromaDB with metadata.
    
    Args:
        courses: List of course dictionaries from database
        skip_duplicates: Skip courses already in ChromaDB (default True)
    
    Returns:
        Tuple of (success_count, failure_count, skipped_count)
    """
    if not courses:
        logger.warning("No courses to migrate")
        return 0, 0, 0
    
    try:
        # Initialize ChromaDB Cloud vectorizer
        logger.info("Initializing ChromaDB Cloud connection...")
        vectorizer = CloudVectorizer()
        
        success_count = 0
        failure_count = 0
        skipped_count = 0
        
        for idx, course in enumerate(courses, 1):
            # Support both database schema (id, title) and legacy (course_id, course_title)
            course_id = course.get('id') or course.get('course_number') or course.get('course_id')
            course_title = course.get('title') or course.get('course_title', 'Unknown Course')
            module_count = len(course.get('modules', []))
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Processing [{idx}/{len(courses)}] Course ID: {course_id}")
            logger.info(f"  Title: {course_title}")
            logger.info(f"  Modules: {module_count}")
            logger.info(f"{'='*80}")
            
            # Add course content to vectorstore with metadata (with duplicate checking)
            success = vectorizer.add_course_content_to_vectorstore(course, skip_duplicates=skip_duplicates)
            
            if success:
                # Check if it was skipped (returns True but with warning)
                # We can detect this by checking if warning was logged
                # For now, count as success
                success_count += 1
                logger.info(f"✅ Successfully processed course {course_id}: {course_title}")
            else:
                failure_count += 1
                logger.error(f"❌ Failed to migrate course {course_id}: {course_title}")
        
        return success_count, failure_count, skipped_count
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0, len(courses), 0


def main():
    """Main migration function."""
    logger.info("="*80)
    logger.info("Course Content Migration to ChromaDB")
    logger.info("="*80)
    
    # Step 1: Retrieve courses from database or JSON
    logger.info("\n[STEP 1] Retrieving courses...")
    
    # Try database first (using DatabaseServiceV2)
    logger.info("Attempting to retrieve courses from Neon database...")
    courses = get_courses_from_neon()
    
    # Fallback to JSON if database returns nothing
    if not courses:
        logger.warning("No courses found in database, trying JSON fallback...")
        courses = get_courses_from_json()
    
    if not courses:
        logger.error("No courses found in database or JSON file. Exiting.")
        return
    
    logger.info(f"Found {len(courses)} courses to migrate")
    
    # Step 2: Migrate courses to ChromaDB (with duplicate checking enabled)
    logger.info("\n[STEP 2] Migrating courses to ChromaDB...")
    logger.info("Note: Duplicate courses will be automatically skipped")
    success_count, failure_count, skipped_count = migrate_courses_to_chromadb(courses, skip_duplicates=True)
    
    # Step 3: Summary
    logger.info("\n" + "="*80)
    logger.info("MIGRATION SUMMARY")
    logger.info("="*80)
    logger.info(f"Total courses: {len(courses)}")
    logger.info(f"✅ Successfully migrated: {success_count}")
    logger.info(f"⏭️  Skipped (already exists): {skipped_count}")
    logger.info(f"❌ Failed to migrate: {failure_count}")
    logger.info("="*80)
    
    if success_count > 0:
        logger.info("\n✅ Migration completed successfully!")
        logger.info("\nYou can now use course_id parameter in chat endpoints to filter RAG results:")
        logger.info("  POST /api/chat")
        logger.info("  POST /api/chat-with-audio")
        logger.info("  POST /api/chat-with-audio-stream")
        logger.info("\nExample request:")
        logger.info('  {"user_id": 16, "message": "What is machine learning?", "course_id": 3}')
    else:
        logger.error("\n❌ Migration failed. Please check the errors above.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\nMigration interrupted by user")
    except Exception as e:
        logger.error(f"\n\nUnexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
