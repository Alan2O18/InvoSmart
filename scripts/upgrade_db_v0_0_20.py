import asyncio
import os
import sys

# Add the parent directory to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from backend.database.core import get_global_db_path, init_db
import sqlite3

async def main():
    db_path = get_global_db_path()
    print(f"Connecting to database at {db_path}...")
    
    # Drop tables synchronously using sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS stamps;")
        print("Dropped table 'stamps'.")
    except Exception as e:
        print(f"Error dropping stamps: {e}")
        
    try:
        cursor.execute("DROP TABLE IF EXISTS groups;")
        print("Dropped table 'groups'.")
    except Exception as e:
        print(f"Error dropping groups: {e}")
        
    conn.commit()
    conn.close()
    
    print("Running init_db to recreate tables with new schema...")
    await init_db()
    print("Database upgrade completed!")

if __name__ == "__main__":
    asyncio.run(main())
