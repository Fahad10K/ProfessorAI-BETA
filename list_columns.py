import psycopg2
from config import DATABASE_URL

def get_table_columns():
    """Retrieve and print all tables and their columns from the database."""
    try:
        # Connect to the database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Get all tables in the public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        
        # For each table, get its columns
        for table in tables:
            table_name = table[0]
            print(f"\nTable: {table_name}")
            print("-" * (len(table_name) + 8))  # 8 is the length of "Table: "
            
            # Get column details for the current table
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            # Print column details
            for col in columns:
                col_name, data_type, is_nullable, default_val = col
                print(f"  {col_name.ljust(30)} {data_type.ljust(20)} "
                      f"{'NULL' if is_nullable == 'YES' else 'NOT NULL'.ljust(10)} "
                      f"DEFAULT {default_val if default_val else 'None'}")
        
        print("\n--- Database schema inspection complete ---")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close the connection
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    print("Fetching database schema...\n")
    get_table_columns()
