"""
Extract Course Data to JSON
Extracts course titles, IDs, and week-wise topics from Neon DB and saves to JSON file.
"""

import json
import logging
from typing import List, Dict
from services.database_service_v2 import DatabaseServiceV2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_courses_with_topics() -> List[Dict]:
    """
    Extract all courses with their week-wise topics from the database.
    
    Returns:
        List of courses with structure:
        {
            "course_id": int,
            "course_title": str,
            "weeks": [
                {
                    "week_number": int,
                    "week_title": str,
                    "topics": [
                        {
                            "topic_id": int,
                            "topic_title": str
                        }
                    ]
                }
            ]
        }
    """
    db = DatabaseServiceV2()
    
    logger.info("📚 Fetching all courses from database...")
    all_courses = db.get_all_courses()
    
    if not all_courses:
        logger.warning("⚠️ No courses found in database")
        return []
    
    logger.info(f"✅ Found {len(all_courses)} courses")
    
    courses_data = []
    
    for course in all_courses:
        course_id = course.get('id')
        course_title = course.get('title')
        
        logger.info(f"\n📖 Processing Course {course_id}: {course_title}")
        
        # Get full course content with modules and topics
        full_course = db.get_course_with_content(course_id)
        
        if not full_course or 'modules' not in full_course:
            logger.warning(f"⚠️ No modules found for course {course_id}")
            continue
        
        modules = full_course.get('modules', [])
        
        # Organize topics by week
        weeks = []
        for module in modules:
            week_number = module.get('week_number')
            week_title = module.get('title')
            topics_data = module.get('topics', [])
            
            # Extract only topic ID and title
            topics = [
                {
                    "topic_id": topic.get('id'),
                    "topic_title": topic.get('title')
                }
                for topic in topics_data
            ]
            
            weeks.append({
                "week_number": week_number,
                "week_title": week_title,
                "topics": topics
            })
        
        logger.info(f"  ✓ Extracted {len(weeks)} weeks with {sum(len(w['topics']) for w in weeks)} topics")
        
        # Add to courses data
        courses_data.append({
            "course_id": course_id,
            "course_title": course_title,
            "weeks": weeks
        })
    
    return courses_data


def save_to_json(data: List[Dict], output_file: str = "courses_week_topics.json"):
    """Save extracted data to JSON file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Successfully saved data to {output_file}")
        
        # Print summary
        total_courses = len(data)
        total_weeks = sum(len(course['weeks']) for course in data)
        total_topics = sum(
            sum(len(week['topics']) for week in course['weeks'])
            for course in data
        )
        
        logger.info(f"\n📊 Summary:")
        logger.info(f"  - Total Courses: {total_courses}")
        logger.info(f"  - Total Weeks: {total_weeks}")
        logger.info(f"  - Total Topics: {total_topics}")
        
    except Exception as e:
        logger.error(f"❌ Error saving to JSON: {e}")
        raise


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("Starting Course Data Extraction")
    logger.info("=" * 60)
    
    try:
        # Extract courses with topics
        courses_data = extract_courses_with_topics()
        
        if not courses_data:
            logger.warning("⚠️ No data extracted. Exiting.")
            return
        
        # Save to JSON
        save_to_json(courses_data)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Course data extraction completed successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Error during extraction: {e}")
        raise


if __name__ == "__main__":
    main()
