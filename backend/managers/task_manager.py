# main_src/project_queue.py
"""
TaskManager (updated)

Changes in this revision:
- Added `settings` table to record project-level flags (e.g. `enqueue_closed`).
- Added status/count helpers: `count_jobs`, `any_pending_or_running`, `get_counts`.
- Added graceful shutdown helpers: `close_enqueuing`, `is_enqueuing_closed`.
- Added blocking helper `wait_for_job_or_shutdown(stage, timeout, poll_interval)` that lets a worker wait for new work or decide to exit.
- Added `mark_all_pending_as_failed_if_stale` helper (optional) to recover stuck jobs after long crashes.

Design notes:
- Workers that previously saw `claim_for_ocr()` return None should now call `wait_for_job_or_shutdown('ocr', timeout=..., poll_interval=...)` or periodically call `any_pending_or_running('ocr')` and also check `is_enqueuing_closed()` to decide whether to exit.
- `close_enqueuing()` should be called by the coordinator (stage one) when no more new jobs will be enqueued for this project; this avoids races where workers wait indefinitely.

This file is intended to live in main_src/project_queue.py and be edited collaboratively.
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
  ocr_start_at REAL,
  ocr_done_at REAL,
  llm_start_at REAL,
  llm_done_at REAL,
  ocr_result_json TEXT,
  llm_result_json TEXT,
  manual_ocr_text TEXT,        -- User-edited OCR text for corrections
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


class TaskManager:
    def __init__(self, project_dir: str, db_name: str = DEFAULT_DB_NAME):
        self.project_dir = project_dir
        self.db_path = os.path.join(project_dir, db_name)
        self._init_db()
        self.lock = threading.Lock()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.executescript(JOB_TABLE_SQL)
        cur.executescript(EVENTS_TABLE_SQL)
        
        # Migration: add manual correction columns if they don't exist
        try:
            cur.execute("SELECT manual_ocr_text FROM jobs LIMIT 1")
        except sqlite3.OperationalError:
            # Columns don't exist, add them
            cur.execute("ALTER TABLE jobs ADD COLUMN manual_ocr_text TEXT")
            cur.execute("ALTER TABLE jobs ADD COLUMN manual_updated_at REAL")
        
        conn.commit()
        conn.close()

    # ---------------------
    # Basic queue ops
    # ---------------------
    def enqueue(self, image_path: str, job_id: str = "", stage: str = "ocr"):
        with self.lock:
            if job_id == "":
                job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:6]}"
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
            INSERT OR REPLACE INTO jobs(job_id, image_path, status, stage, updated_at)
            VALUES (?, ?, 'ready', ?, strftime('%s','now'))
            """,
                (job_id, image_path, stage),
            )
            conn.commit()
            conn.close()
            self._emit_event(
                job_id, "enqueued", {"image_path": image_path, "stage": stage}
            )
            return job_id

    def claim_for_ocr(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT job_id, image_path FROM jobs WHERE status IN ('ready', 'pending') AND stage='ocr' ORDER BY created_at ASC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            job_id = row["job_id"]
            cur.execute(
                "UPDATE jobs SET status='running', ocr_start_at=strftime('%s','now'), updated_at=strftime('%s','now') WHERE job_id=?",
                (job_id,),
            )
            conn.commit()
            conn.close()
            self._emit_event(job_id, "ocr_claimed", {})
            return {"job_id": job_id, "image_path": row["image_path"]}

    def claim_for_llm(self) -> Optional[Dict[str, Any]]:
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT job_id, image_path, ocr_result_json FROM jobs WHERE status IN ('ready', 'pending') AND stage='llm' ORDER BY created_at ASC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "SELECT job_id FROM jobs WHERE (status IN ('ready', 'pending') AND stage='ocr') OR (status='running') LIMIT 1"
                )
                if not cur.fetchone():
                    conn.close()
                    return "all_task_done"
                else:
                    conn.close()
                    return None
            job_id = row["job_id"]
            cur.execute(
                "UPDATE jobs SET status='running', llm_start_at=strftime('%s','now'), updated_at=strftime('%s','now') WHERE job_id=?",
                (job_id,),
            )
            conn.commit()
            conn.close()
            self._emit_event(job_id, "llm_claimed", {})
            try:
                ocr_data = (
                    json.loads(row["ocr_result_json"])
                    if row["ocr_result_json"]
                    else None
                )
            except Exception:
                ocr_data = None
            return {
                "job_id": job_id,
                "image_path": row["image_path"],
                "ocr_result": ocr_data,
            }

    def reset_and_claim(self, job_id: str, stage: str) -> Optional[Dict[str, Any]]:
        """
        Atomically reset a job to 'running' for a specific stage and return it.
        This prevents other workers from claiming it.
        Also clears completion timestamps to allow proper rerun.
        """
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            # First check if job exists
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            
            # Update status and clear timestamps based on stage
            now = int(time.time())
            if stage == 'ocr':
                # OCR rerun: clear both OCR and LLM timestamps (since LLM depends on OCR)
                cur.execute(
                    """UPDATE jobs SET status='running', stage=?, updated_at=?, 
                       ocr_done_at=NULL, llm_done_at=NULL, 
                       ocr_result_json=NULL, llm_result_json=NULL 
                       WHERE job_id=?""",
                    (stage, now, job_id)
                )
            elif stage == 'llm':
                # LLM rerun: only clear LLM timestamp, keep OCR results
                cur.execute(
                    """UPDATE jobs SET status='running', stage=?, updated_at=?, 
                       llm_done_at=NULL, llm_result_json=NULL 
                       WHERE job_id=?""",
                    (stage, now, job_id)
                )
            else:
                # Generic stage: just update status
                cur.execute(
                    "UPDATE jobs SET status='running', stage=?, updated_at=? WHERE job_id=?",
                    (stage, now, job_id)
                )
            conn.commit()
            
            # Fetch updated row data
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            conn.close()
            
            self._emit_event(job_id, f"{stage}_claimed_manual", {})
            
            res = {
                "job_id": job_id,
                "image_path": row["image_path"],
            }
            
            if stage == 'llm':
                try:
                    ocr_data = json.loads(row["ocr_result_json"]) if row["ocr_result_json"] else None
                except:
                    ocr_data = None
                res["ocr_result"] = ocr_data
                
            return res

    def complete_ocr(
        self, job_id: str, ocr_result: Dict[str, Any], advance_to_stage_llm: bool = True
    ):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            now = int(time.time())
            ocr_json = json.dumps(ocr_result, ensure_ascii=False)
            if advance_to_stage_llm:
                cur.execute(
                    """UPDATE jobs SET ocr_result_json=?, ocr_done_at=?, stage='llm', status='ready', updated_at=strftime('%s','now') WHERE job_id=?""",
                    (ocr_json, now, job_id),
                )
            else:
                cur.execute(
                    """UPDATE jobs SET ocr_result_json=?, ocr_done_at=?, status='ready', updated_at=strftime('%s','now') WHERE job_id=?""",
                    (ocr_json, now, job_id),
                )
            conn.commit()
            conn.close()
            self._emit_event(job_id, "ocr_completed", {"ocr_done_at": now})
            return True

    def complete_llm(
        self, job_id: str, llm_result: Dict[str, Any], mark_final: bool = True
    ):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            now = int(time.time())
            llm_json = json.dumps(llm_result, ensure_ascii=False)
            if mark_final:
                cur.execute(
                    """UPDATE jobs SET llm_result_json=?, llm_done_at=?, status='done', stage='finalize', updated_at=strftime('%s','now') WHERE job_id=?""",
                    (llm_json, now, job_id),
                )
            else:
                cur.execute(
                    """UPDATE jobs SET llm_result_json=?, llm_done_at=?, status='pending', updated_at=strftime('%s','now') WHERE job_id=?""",
                    (llm_json, now, job_id),
                )
            conn.commit()
            conn.close()
            self._emit_event(job_id, "llm_completed", {"llm_done_at": now})
            return True

    def fail_job(self, job_id: str, reason: str = ""):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE jobs SET status='failed', updated_at=strftime('%s','now') WHERE job_id=?",
                (job_id,),
            )
            conn.commit()
            conn.close()
            self._emit_event(job_id, "failed", {"reason": reason})

    def delete_job(self, job_id: str):
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM jobs WHERE job_id=?", (job_id,))
            conn.commit()
            conn.close()
            self._emit_event(job_id, "deleted", {})

    # ---------------------
    # Query / monitoring helpers
    # ---------------------
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None

    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
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
            res = {r["status"]: r["cnt"] for r in rows}
            return res

    # ---------------------
    # Worker friendly blocking wait / shutdown logic
    # ---------------------

    # ---------------------
    # Administrative helpers
    # ---------------------
    def dump_all(self) -> Dict[str, Any]:
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

    def mark_all_pending_as_failed_if_stale(self, stale_seconds: int = 60 * 60 * 6):
        """Mark pending/running jobs older than stale_seconds as failed. Useful after long crash."""
        cutoff = int(time.time()) - int(stale_seconds)
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE jobs SET status='failed', updated_at=strftime('%s','now') WHERE (status='pending' OR status='running') AND created_at<?",
            (cutoff,),
        )
        conn.commit()
        conn.close()

    def _emit_event(self, job_id: str, event_type: str, payload: Dict[str, Any]):
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events(job_id, event_type, payload) VALUES(?,?,?)",
            (job_id, event_type, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    # --- Manual Correction Methods ---

    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full job details including OCR/LLM results and manual text."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Parse JSON fields
            ocr_result = None
            llm_result = None
            try:
                if row["ocr_result_json"]:
                    ocr_result = json.loads(row["ocr_result_json"])
            except:
                pass
            try:
                if row["llm_result_json"]:
                    llm_result = json.loads(row["llm_result_json"])
            except:
                pass
            
            return {
                "job_id": row["job_id"],
                "image_path": row["image_path"],
                "status": row["status"],
                "stage": row["stage"],
                "ocr_result": ocr_result,
                "llm_result": llm_result,
                "manual_ocr_text": row["manual_ocr_text"],
                "manual_updated_at": row["manual_updated_at"],
                "ocr_done_at": row["ocr_done_at"],
                "llm_done_at": row["llm_done_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def save_manual_text(self, job_id: str, manual_text: str) -> bool:
        """Save user's manual correction text."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            now = int(time.time())
            cur.execute(
                """UPDATE jobs SET manual_ocr_text=?, manual_updated_at=?, updated_at=? 
                   WHERE job_id=?""",
                (manual_text, now, now, job_id)
            )
            conn.commit()
            affected = cur.rowcount
            conn.close()
            
            if affected > 0:
                self._emit_event(job_id, "manual_text_saved", {"timestamp": now})
            return affected > 0
