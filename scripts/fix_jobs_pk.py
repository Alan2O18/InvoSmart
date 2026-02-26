import sqlite3
from pathlib import Path

def fix_schema():
    db_path = Path("backend/data/global.db")
    if not db_path.exists():
        print("DB not found!")
        return
        
    conn = sqlite3.connect(db_path)
    
    # Disable foreign keys to do safe table recreation
    conn.execute("PRAGMA foreign_keys=OFF")
    
    try:
        # 1. Rename jobs to jobs_old
        conn.execute("ALTER TABLE jobs RENAME TO jobs_old")
        
        # 2. Recreate jobs with single job_id PK
        create_sql = """
        CREATE TABLE "jobs" (
            project_id VARCHAR NOT NULL, 
            job_id VARCHAR NOT NULL, 
            image_path VARCHAR NOT NULL, 
            status VARCHAR NOT NULL, 
            vlm_result_json TEXT, 
            vlm_stats TEXT, 
            validation_json TEXT, 
            qr_verified INTEGER DEFAULT 0, 
            manual_json_text TEXT, 
            manual_updated_at FLOAT, 
            created_at FLOAT DEFAULT (strftime('%s','now')), 
            updated_at FLOAT DEFAULT (strftime('%s','now')), 
            PRIMARY KEY (job_id), 
            CONSTRAINT fk_jobs_project_id_projects FOREIGN KEY(project_id) REFERENCES projects (project_id) ON DELETE CASCADE
        )
        """
        conn.execute(create_sql)
        
        # 3. Copy data
        copy_sql = """
        INSERT INTO jobs 
        (project_id, job_id, image_path, status, vlm_result_json, vlm_stats, validation_json, qr_verified, manual_json_text, manual_updated_at, created_at, updated_at)
        SELECT project_id, job_id, image_path, status, vlm_result_json, vlm_stats, validation_json, qr_verified, manual_json_text, manual_updated_at, created_at, updated_at
        FROM jobs_old
        """
        conn.execute(copy_sql)
        
        # 4. Drop jobs_old
        conn.execute("DROP TABLE jobs_old")
        
        # 5. Recreate missing indexes that were on jobs
        conn.execute("CREATE INDEX ix_jobs_project_id ON jobs (project_id)")
        conn.execute("CREATE INDEX ix_jobs_status ON jobs (status)")
        
        conn.commit()
        print("Jobs table rebuilt successfully.")
        
    except Exception as e:
        conn.rollback()
        print(f"Failed to fix: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema()
