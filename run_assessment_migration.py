import psycopg2
import logging
import sys

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('assessment_migration.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

NEW_DB_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def main():
    logger.info("\n" + "="*80)
    logger.info("[START] Creating Assessment System Tables")
    logger.info("="*80)
    
    try:
        # Read SQL file
        logger.info("Reading SQL migration file...")
        with open('create_assessment_tables.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        logger.info("[SUCCESS] SQL file loaded")
        
        # Connect to database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(NEW_DB_URL)
        conn.autocommit = False
        cur = conn.cursor()
        logger.info("[SUCCESS] Connected to database")
        
        # Execute SQL
        logger.info("\nExecuting SQL migration...")
        cur.execute(sql_content)
        conn.commit()
        logger.info("[SUCCESS] SQL migration completed")
        
        # Verify tables were created
        logger.info("\nVerifying created tables...")
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('uploaded_notes', 'assessments', 'assessment_questions', 'user_assessment_responses')
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        logger.info(f"\nCreated {len(tables)} tables:")
        for table in tables:
            logger.info(f"  ✓ {table[0]}")
            
            # Get column count
            cur.execute(f"""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_name = '{table[0]}'
            """)
            col_count = cur.fetchone()[0]
            logger.info(f"    └─ {col_count} columns")
        
        logger.info("\n" + "="*80)
        logger.info("[SUCCESS] Assessment system tables created successfully!")
        logger.info("="*80)
        
        logger.info("\nTables overview:")
        logger.info("  1. uploaded_notes - User-uploaded notes and content")
        logger.info("  2. assessments - AI-generated assessments from notes")
        logger.info("  3. assessment_questions - Questions for each assessment")
        logger.info("  4. user_assessment_responses - User attempts and answers")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"\n[ERROR] Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == "__main__":
    main()
