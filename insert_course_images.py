import psycopg2
import json
import logging
from datetime import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('insert_course_images.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

NEW_DB_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Course images data from old DB
COURSE_IMAGES_DATA = [
    {"id":"195bd044-3787-46ef-bef0-e067ef9e4feb","course_id":"17","image_url":"https://icmamritsar.com/wp-content/uploads/2022/01/business-studies.webp","created_at":"2025-11-17 19:46:23.880648","updated_at":"2025-12-09 21:37:13.981","course_name":"Teacher Training Certificate Programme for AI Awareness"},
    {"id":"2ce139d6-ceb7-4591-9676-3797062176a9","course_id":"7","image_url":"https://t4.ftcdn.net/jpg/05/62/74/25/360_F_562742563_PosEgK2rE0LCRcwGauTfYi8JmwYG26fu.jpg","created_at":"2025-11-17 19:40:28.635167","updated_at":"2025-12-09 21:37:13.083","course_name":"Social Change and Development in India"},
    {"id":"7d2cb017-96ed-493c-930d-0ae746bcbdfd","course_id":"3","image_url":"https://as1.ftcdn.net/jpg/06/22/78/30/1000_F_622783021_xUOeMWwkCUVjbnEBJTNaOcX6aZVpbrie.jpg","created_at":"2025-11-17 19:38:56.428543","updated_at":"2025-12-09 21:37:12.858","course_name":"Hindi to English Speaking course"},
    {"id":"849c2522-092f-48d2-aaf4-907ec534f938","course_id":"1","image_url":"https://www.infolks.info/blog/wp-content/uploads/2023/08/cover-01-1-1-1024x682.jpg","created_at":"2025-11-17 19:32:35.471434","updated_at":"2025-12-09 21:37:12.631","course_name":"Generative AI Handson"},
    {"id":"c3f6740e-2a34-44b0-94cd-83cfee917c64","course_id":"14","image_url":"https://www.smartling.com/hubfs/BP20211116_-_4_English-to-Arabic_Translation_Challenges_and_How_to_Solve_Them_-_750x422.jpg","created_at":"2025-11-17 19:43:55.483995","updated_at":"2025-12-09 21:37:13.756","course_name":"Virtual Reality"},
    {"id":"c7ebe48d-a089-460c-a3a9-15e6dbbeb1a4","course_id":"13","image_url":"https://www.shutterstock.com/image-vector/psychology-word-concept-use-cover-260nw-1316058086.jpg","created_at":"2025-11-17 19:43:17.034024","updated_at":"2025-12-09 21:37:13.532","course_name":"Class 12th NCERT - Political Science -  Politics in India Since Independence"},
    {"id":"c9bb15c9-5ae5-465e-913b-3be973c73f22","course_id":"8","image_url":"https://indianinfo.com/wp-content/uploads/2025/04/social-change.jpeg","created_at":"2025-11-17 19:47:50.159692","updated_at":"2025-12-09 21:37:14.431","course_name":"Bhaswati sanskrit"},
    {"id":"dfd5c326-24ea-4f31-a2ba-958bba1025b7","course_id":"1ec613a4-93df-4e8f-b01b-fbaf19679a0a","image_url":"https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?w=800&h=600&fit=crop","created_at":"2025-12-09 07:21:09.74763","updated_at":"2025-12-09 21:37:14.656","course_name":"Indian Societies"},
    {"id":"ec389809-4cf0-49fc-8ad2-1177e8228a36","course_id":"11","image_url":"https://www.shutterstock.com/image-photo/finance-banking-investment-asset-allocation-600nw-2467052941.jpg","created_at":"2025-11-17 19:42:05.445529","updated_at":"2025-12-09 21:37:13.308","course_name":"Class 12th NCERT Psychology book"},
    {"id":"fe279c48-7975-48e8-8fb2-65205d952b70","course_id":"18","image_url":"https://icmamritsar.com/wp-content/uploads/2022/01/business-studies.webp","created_at":"2025-11-17 19:46:28.914463","updated_at":"2025-12-09 21:37:14.205","course_name":"Class 12th - NCERT - Chemistry Part - 1"}
]

def main():
    logger.info("\n" + "="*80)
    logger.info("[START] Inserting Course Images")
    logger.info("="*80)
    
    try:
        # Connect to new database
        logger.info("Connecting to NEW database...")
        conn = psycopg2.connect(NEW_DB_URL)
        conn.autocommit = False
        cur = conn.cursor()
        logger.info("[SUCCESS] Connected to database")
        
        # Build course name to ID mapping from new DB
        cur.execute("SELECT id, title FROM courses")
        course_name_map = {}
        for course_id, title in cur.fetchall():
            course_name_map[title.lower().strip()] = course_id
        logger.info(f"Built mapping for {len(course_name_map)} courses")
        
        inserted_count = 0
        skipped_count = 0
        
        for image_data in COURSE_IMAGES_DATA:
            course_name = image_data['course_name'].lower().strip()
            image_url = image_data['image_url']
            created_at = image_data['created_at']
            updated_at = image_data['updated_at']
            
            # Find matching course in new DB
            new_course_id = course_name_map.get(course_name)
            
            if not new_course_id:
                logger.warning(f"  Skipping image for '{image_data['course_name'][:50]}' - course not found in new DB")
                skipped_count += 1
                continue
            
            # Check if course already has an image
            cur.execute("SELECT id FROM course_images WHERE course_id = %s", (new_course_id,))
            if cur.fetchone():
                logger.warning(f"  Skipping '{image_data['course_name'][:50]}' - already has image")
                skipped_count += 1
                continue
            
            # Insert image
            cur.execute("""
                INSERT INTO course_images (
                    course_id, image_url, course_name, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                new_course_id, image_url, course_name, created_at, updated_at
            ))
            logger.info(f"  Inserted image for: {image_data['course_name']}")
            inserted_count += 1
        
        conn.commit()
        logger.info("\n" + "="*80)
        logger.info(f"[SUCCESS] Inserted {inserted_count} course images (skipped {skipped_count})")
        logger.info("="*80)
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"\n[ERROR] Failed to insert course images: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    main()
