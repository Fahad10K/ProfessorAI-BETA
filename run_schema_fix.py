"""
Execute SQL script to fix user_sessions table schema
Adds the missing session_id column
"""
import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

def fix_user_sessions_schema():
    """Add session_id column to user_sessions table"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("🔧 Fixing user_sessions table schema...")
        
        # Check if column exists
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_sessions' AND column_name = 'session_id'
        """)
        
        if cur.fetchone():
            print("✅ session_id column already exists")
        else:
            print("➕ Adding session_id column...")
            
            # Add session_id column
            cur.execute("""
                ALTER TABLE user_sessions 
                ADD COLUMN session_id TEXT;
            """)
            conn.commit()
            print("✅ Added session_id column")
            
            # Update existing rows with UUIDs
            cur.execute("""
                UPDATE user_sessions 
                SET session_id = gen_random_uuid()::text 
                WHERE session_id IS NULL;
            """)
            conn.commit()
            print(f"✅ Updated {cur.rowcount} existing rows with UUIDs")
            
            # Make it NOT NULL and UNIQUE
            cur.execute("""
                ALTER TABLE user_sessions 
                ALTER COLUMN session_id SET NOT NULL;
            """)
            cur.execute("""
                ALTER TABLE user_sessions 
                ADD CONSTRAINT user_sessions_session_id_key UNIQUE (session_id);
            """)
            conn.commit()
            print("✅ Added NOT NULL and UNIQUE constraints")
            
            # Create index
            cur.execute("""
                CREATE INDEX idx_user_sessions_session_id ON user_sessions(session_id);
            """)
            conn.commit()
            print("✅ Created index on session_id")
        
        # Verify final schema
        print("\n📋 Final user_sessions schema:")
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'user_sessions'
            ORDER BY ordinal_position
        """)
        
        for row in cur.fetchall():
            nullable = "NULL" if row[2] == 'YES' else "NOT NULL"
            default = row[3] if row[3] else "-"
            print(f"  - {row[0]:<20} {row[1]:<25} {nullable:<10} {default}")
        
        cur.close()
        conn.close()
        
        print("\n✅ Schema fix completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    fix_user_sessions_schema()
