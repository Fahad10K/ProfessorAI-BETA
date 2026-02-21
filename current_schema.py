import psycopg2
from psycopg2 import sql

DATABASE_URL = "postgresql://neondb_owner:npg_VsaY4RnLEXB1@ep-flat-field-ad3wbjno-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def check_database_schema():
    try:
        # Connect to the database
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Get all tables in the public schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        
        tables = cur.fetchall()
        
        if not tables:
            print("No tables found in the database.")
            return
        
        print(f"\n{'='*80}")
        print(f"Found {len(tables)} table(s) in the database:")
        print(f"{'='*80}\n")
        
        # For each table, get its schema
        for (table_name,) in tables:
            print(f"\n📋 TABLE: {table_name}")
            print("-" * 80)
            
            # Get column information
            cur.execute("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' 
                AND table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cur.fetchall()
            
            print(f"{'Column Name':<30} {'Data Type':<20} {'Nullable':<10} {'Default':<20}")
            print("-" * 80)
            
            for col_name, data_type, max_length, nullable, default in columns:
                if max_length:
                    data_type = f"{data_type}({max_length})"
                default_str = str(default)[:20] if default else "-"
                print(f"{col_name:<30} {data_type:<20} {nullable:<10} {default_str:<20}")
            
            # Get primary keys
            cur.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                                    AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass
                AND i.indisprimary;
            """, (table_name,))
            
            pkeys = cur.fetchall()
            if pkeys:
                print(f"\n🔑 Primary Key(s): {', '.join([pk[0] for pk in pkeys])}")
            
            # Get indexes
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = %s
                AND schemaname = 'public';
            """, (table_name,))
            
            indexes = cur.fetchall()
            if indexes:
                print(f"\n📑 Indexes:")
                for idx_name, idx_def in indexes:
                    print(f"  - {idx_name}")
            
            print()
        
        cur.close()
        conn.close()
        print(f"\n{'='*80}")
        print("✅ Database schema inspection complete!")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")

if __name__ == "__main__":
    check_database_schema()