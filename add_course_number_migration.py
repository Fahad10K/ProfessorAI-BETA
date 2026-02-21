"""
Migration script to add course_number column to existing courses
Assigns sequential integers 1, 2, 3... to existing courses
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env file")
    sys.exit(1)

def add_course_number_column():
    """Add course_number column and populate with sequential integers"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔄 Starting migration: Add course_number column")
        
        # Step 1: Add column (if not exists)
        print("📝 Step 1: Adding course_number column...")
        session.execute(text("""
            ALTER TABLE courses 
            ADD COLUMN IF NOT EXISTS course_number INTEGER;
        """))
        session.commit()
        print("   ✅ Column added")
        
        # Step 2: Get all courses ordered by creation date
        print("📝 Step 2: Fetching existing courses...")
        result = session.execute(text("""
            SELECT id, title, created_at 
            FROM courses 
            ORDER BY created_at ASC;
        """))
        courses = result.fetchall()
        print(f"   Found {len(courses)} courses")
        
        # Step 3: Assign sequential numbers
        print("📝 Step 3: Assigning course numbers...")
        for idx, course in enumerate(courses, start=1):
            course_id = course[0]
            title = course[1]
            
            session.execute(
                text("UPDATE courses SET course_number = :num WHERE id = :id"),
                {"num": idx, "id": course_id}
            )
            print(f"   {idx}. {title[:50]}... -> course_number = {idx}")
        
        session.commit()
        print("   ✅ Course numbers assigned")
        
        # Step 4: Add unique constraint
        print("📝 Step 4: Adding unique constraint...")
        session.execute(text("""
            ALTER TABLE courses 
            ADD CONSTRAINT courses_course_number_unique 
            UNIQUE (course_number);
        """))
        session.commit()
        print("   ✅ Unique constraint added")
        
        # Step 5: Make column NOT NULL
        print("📝 Step 5: Setting NOT NULL constraint...")
        session.execute(text("""
            ALTER TABLE courses 
            ALTER COLUMN course_number SET NOT NULL;
        """))
        session.commit()
        print("   ✅ NOT NULL constraint added")
        
        print("\n✅ Migration completed successfully!")
        print(f"\n📊 Summary:")
        print(f"   - Added course_number column")
        print(f"   - Assigned numbers 1-{len(courses)} to existing courses")
        print(f"   - Added unique constraint")
        print(f"   - Added NOT NULL constraint")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRATION: Add course_number to courses table")
    print("=" * 60)
    print()
    
    confirm = input("This will modify the courses table. Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Migration cancelled")
        sys.exit(0)
    
    add_course_number_column()
