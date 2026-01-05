# Job Repository - 資料存取層
"""
JobRepository handles all direct database CRUD operations for jobs.
This separates data access concerns from state machine logic.
"""
import sqlite3
import os
import json
import time
import uuid
import threading
from typing import Optional, Dict, Any, List, Tuple

DEFAULT_DB_NAME = "jobs.db"

JOB_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  image_path TEXT NOT NULL,
  status TEXT NOT NULL,        -- ready, pending, running, done, failed
  stage TEXT NOT NULL,         -- e.g. load, ocr, llm, finalize
  ocr_result_json TEXT,
  llm_result_json TEXT,
  ocr_stats TEXT,              -- OCR 效能統計 (JSON)
  llm_stats TEXT,              -- LLM 效能統計 (JSON 陣列)
  manual_ocr_text TEXT,        -- User-edited OCR text for corrections
  manual_json_text TEXT,       -- User-edited JSON result
  edit_mode TEXT,              -- Current edit mode: 'ocr' | 'json'
  manual_updated_at REAL,      -- Last manual edit timestamp
  created_at REAL DEFAULT (strftime('%s','now')),
  updated_at REAL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT,
  event_type TEXT,
  ts REAL DEFAULT (strftime('%s','now')),
  payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
"""


class JobRepository:
    """
    Data access layer for job persistence.
    Handles all SQLite CRUD operations and event logging.
    """
    
    def __init__(self, project_dir: str, db_name: str = DEFAULT_DB_NAME):
        self.project_dir = project_dir
        self.db_path = os.path.join(project_dir, db_name)
        self._init_db()
        self.lock = threading.Lock()

    def _get_conn(self):
        """Get database connection with optimal settings."""
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema with migrations."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.executescript(JOB_TABLE_SQL)
        cur.executescript(EVENTS_TABLE_SQL)
        
        # Migration: add manual correction columns if they don't exist
        try:
            cur.execute("SELECT manual_ocr_text FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE jobs ADD COLUMN manual_ocr_text TEXT")
            cur.execute("ALTER TABLE jobs ADD COLUMN manual_updated_at REAL")

        # Migration: add manual_json_text and edit_mode
        try:
            cur.execute("SELECT manual_json_text FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE jobs ADD COLUMN manual_json_text TEXT")
            try:
                cur.execute("ALTER TABLE jobs ADD COLUMN edit_mode TEXT")
            except sqlite3.OperationalError:
                pass
        
        # Migration: add stats columns if they don't exist
        try:
            cur.execute("SELECT ocr_stats FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE jobs ADD COLUMN ocr_stats TEXT")
            cur.execute("ALTER TABLE jobs ADD COLUMN llm_stats TEXT")
        
        conn.commit()
        conn.close()


    # ---------------------
    # CRUD Operations
    # ---------------------
    def insert_job(self, job_id: str, image_path: str, status: str, stage: str) -> str:
        """Insert or replace a job record."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
            INSERT OR REPLACE INTO jobs(job_id, image_path, status, stage, updated_at)
            VALUES (?, ?, ?, ?, strftime('%s','now'))
            """,
                (job_id, image_path, status, stage),
            )
            conn.commit()
            conn.close()
            return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None

    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID. Returns True if deleted."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0

    def update_job(self, job_id: str, **fields) -> bool:
        """Update specific fields of a job."""
        with self.lock:
            if not fields:
                return False
            conn = self._get_conn()
            cur = conn.cursor()
            
            set_clause = ", ".join([f"{k}=?" for k in fields.keys()])
            values = list(fields.values()) + [job_id]
            
            cur.execute(
                f"UPDATE jobs SET {set_clause}, updated_at=strftime('%s','now') WHERE job_id=?",
                values
            )
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0

    # ---------------------
    # Query Methods
    # ---------------------
    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs, optionally filtered by status."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            if status:
                cur.execute(
                    "SELECT * FROM jobs WHERE status=? ORDER BY created_at ASC",
                    (status,),
                )
            else:
                cur.execute("SELECT * FROM jobs ORDER BY created_at ASC")
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def count_jobs(self, stage: Optional[str] = None) -> Dict[str, int]:
        """Count jobs grouped by status, optionally filtered by stage."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            q = "SELECT status, COUNT(1) as cnt FROM jobs"
            params: Tuple = ()
            if stage:
                q += " WHERE stage=?"
                params = (stage,)
            q += " GROUP BY status"
            cur.execute(q, params)
            rows = cur.fetchall()
            conn.close()
            return {r["status"]: r["cnt"] for r in rows}

    def find_claimable_job(self, stage: str) -> Optional[Dict[str, Any]]:
        """Find a job ready to be claimed for a specific stage."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT * FROM jobs 
                   WHERE status IN ('ready', 'pending') AND stage=? 
                   ORDER BY created_at ASC LIMIT 1""",
                (stage,)
            )
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None

    def has_pending_work(self) -> bool:
        """Check if there's any pending or running work."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT job_id FROM jobs 
                   WHERE (status IN ('ready', 'pending') AND stage='ocr') 
                   OR (status='running') LIMIT 1"""
            )
            row = cur.fetchone()
            conn.close()
            return row is not None

    # ---------------------
    # Event Logging
    # ---------------------
    def emit_event(self, job_id: str, event_type: str, payload: Dict[str, Any]):
        """Log an event for a job."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events(job_id, event_type, payload) VALUES(?,?,?)",
            (job_id, event_type, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    # ---------------------
    # Administrative Methods
    # ---------------------
    def dump_all(self) -> Dict[str, Any]:
        """Dump all database contents for debugging."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs ORDER BY created_at ASC")
        jobs = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM events ORDER BY ts ASC")
        events = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT key, value FROM settings")
        settings = {r["key"]: r["value"] for r in cur.fetchall()}
        conn.close()
        return {"jobs": jobs, "events": events, "settings": settings}

    def mark_stale_as_failed(self, stale_seconds: int = 60 * 60 * 6) -> int:
        """Mark pending/running jobs older than stale_seconds as failed."""
        cutoff = int(time.time()) - int(stale_seconds)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE jobs SET status='failed', updated_at=strftime('%s','now') 
                   WHERE (status='pending' OR status='running') AND created_at<?""",
                (cutoff,),
            )
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected
