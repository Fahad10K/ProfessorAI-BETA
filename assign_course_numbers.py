"""
Assign course_number to existing courses (column already exists)
This script only requires UPDATE permissions, not ALTER TABLE
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

def assign_course_numbers():
    """Assign sequential course_number to existing courses without one"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔄 Starting: Assign course numbers to existing courses")
        print()
        
        # Step 1: Check if column exists
        print("📝 Step 1: Checking if course_number column exists...")
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'courses' 
            AND column_name = 'course_number';
        """))
        
        if not result.fetchone():
            print("   ❌ course_number column does not exist!")
            print("   Please add it manually first:")
            print("   ALTER TABLE courses ADD COLUMN course_number INTEGER;")
            sys.exit(1)
        
        print("   ✅ Column exists")
        
        # Step 2: Get courses without course_number
        print("📝 Step 2: Finding courses without course_number...")
        result = session.execute(text("""
            SELECT id, title, created_at 
            FROM courses 
            WHERE course_number IS NULL
            ORDER BY created_at ASC;
        """))
        courses_without_number = result.fetchall()
        
        if not courses_without_number:
            print("   ℹ️  All courses already have course_number assigned")
            
            # Show existing assignments
            result = session.execute(text("""
                SELECT course_number, title, id 
                FROM courses 
                ORDER BY course_number;
            """))
            existing = result.fetchall()
            
            if existing:
                print()
                print("📋 Current course assignments:")
                for num, title, cid in existing:
                    print(f"   {num}. {title[:60]}")
            
            session.close()
            return
        
        print(f"   Found {len(courses_without_number)} courses without numbers")
        
        # Step 3: Get the highest existing course_number
        print("📝 Step 3: Finding next available course_number...")
        result = session.execute(text("""
            SELECT COALESCE(MAX(course_number), 0) 
            FROM courses 
            WHERE course_number IS NOT NULL;
        """))
        max_number = result.scalar() or 0
        next_number = max_number + 1
        print(f"   Next available number: {next_number}")
        
        # Step 4: Assign numbers to courses
        print("📝 Step 4: Assigning course numbers...")
        print()
        
        for course in courses_without_number:
            course_id = course[0]
            title = course[1]
            
            session.execute(
                text("UPDATE courses SET course_number = :num WHERE id = :id"),
                {"num": next_number, "id": course_id}
            )
            
            print(f"   {next_number}. {title[:60]}... ✅")
            next_number += 1
        
        session.commit()
        print()
        print(f"   ✅ Assigned numbers to {len(courses_without_number)} courses")
        
        # Step 5: Verify all courses now have numbers
        print("📝 Step 5: Verifying assignment...")
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM courses 
            WHERE course_number IS NULL;
        """))
        remaining = result.scalar()
        
        if remaining > 0:
            print(f"   ⚠️  Warning: {remaining} courses still without numbers")
        else:
            print("   ✅ All courses have course_number assigned")
        
        # Show final state
        print()
        print("📊 Final course list:")
        result = session.execute(text("""
            SELECT course_number, title, id 
            FROM courses 
            ORDER BY course_number;
        """))
        all_courses = result.fetchall()
        
        for num, title, cid in all_courses:
            short_id = str(cid)[:8] + "..."
            print(f"   {num}. {title[:50]} (ID: {short_id})")
        
        print()
        print("✅ Course number assignment completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Assignment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("ASSIGN COURSE NUMBERS TO EXISTING COURSES")
    print("=" * 60)
    print()
    print("This script assigns sequential course_number values")
    print("to courses that don't have one yet.")
    print()
    print("Requirements:")
    print("  - course_number column must already exist")
    print("  - User needs UPDATE permission on courses table")
    print()
    
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("❌ Assignment cancelled")
        sys.exit(0)
    
    print()
    assign_course_numbers()
