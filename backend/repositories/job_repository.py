# Job Repository - 資料存取層 (VLM-First 全域集中版)
"""
JobRepository handles all direct database CRUD operations for jobs.
Phase 2: All jobs are stored in global.db with project_id to differentiate projects.

VLM-First Schema:
- 移除 OCR 相關欄位
- 簡化 stage 為 vlm/done
- 統一使用 vlm_result_json
- 全域集中：以 project_id 區隔不同專案
"""
import sqlite3
import json
import time
import uuid
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# 全域資料庫路徑
GLOBAL_DB_PATH = Path(__file__).parent.parent / "data" / "global.db"

# VLM-First 全域集中版 Schema
JOB_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
  project_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  image_path TEXT NOT NULL,
  status TEXT NOT NULL,           -- ready, pending, running, done, failed
  vlm_result_json TEXT,           -- VLM 處理結果 (JSON)
  vlm_stats TEXT,                 -- VLM 效能統計 (JSON)
  validation_json TEXT,           -- 驗證結果 (JSON)
  qr_verified INTEGER DEFAULT 0,  -- QR 驗證通過
  manual_json_text TEXT,          -- User-edited JSON result
  manual_updated_at REAL,         -- Last manual edit timestamp
  created_at REAL DEFAULT (strftime('%s','now')),
  updated_at REAL DEFAULT (strftime('%s','now')),
  PRIMARY KEY (project_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(project_id, status);
"""

EVENTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  job_id TEXT,
  event_type TEXT,
  ts REAL DEFAULT (strftime('%s','now')),
  payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(project_id, job_id);
"""


class JobRepository:
    """
    Data access layer for job persistence (VLM-First, Global DB).
    All operations are scoped to a specific project_id.
    All data is stored in the centralized global.db.
    """

    _db_initialized: set = set()  # set of DB paths already initialized
    _init_lock = threading.Lock()

    def __init__(self, project_id: str, db_path: Optional[Path] = None):
        self.project_id = project_id
        self.db_path = db_path or GLOBAL_DB_PATH
        self.lock = threading.Lock()
        self._ensure_schema(self.db_path)

    @classmethod
    def _ensure_schema(cls, db_path: Optional[Path] = None):
        """Ensure global DB schema exists (runs once per db_path per process)."""
        target = db_path or GLOBAL_DB_PATH
        with cls._init_lock:
            if str(target) in cls._db_initialized:
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(target), timeout=30, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            cur = conn.cursor()
            cur.executescript(JOB_TABLE_SQL)
            cur.executescript(EVENTS_TABLE_SQL)
            conn.commit()
            conn.close()
            cls._db_initialized.add(str(target))
            logger.info(f"[JobRepository] 全域 Schema 初始化完成: {target}")

    def _get_conn(self):
        """Get database connection with optimal settings."""
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    # ---------------------
    # CRUD Operations
    # ---------------------
    def insert_job(self, job_id: str, image_path: str, status: str = "ready") -> str:
        """Insert or replace a job record."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """
            INSERT OR REPLACE INTO jobs(project_id, job_id, image_path, status, updated_at)
            VALUES (?, ?, ?, ?, strftime('%s','now'))
            """,
                (self.project_id, job_id, image_path, status),
            )
            conn.commit()
            conn.close()
            return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE project_id=? AND job_id=?", (self.project_id, job_id))
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None

    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID. Returns True if deleted."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM jobs WHERE project_id=? AND job_id=?", (self.project_id, job_id))
            affected = cur.rowcount
            # Also delete related events
            cur.execute("DELETE FROM events WHERE project_id=? AND job_id=?", (self.project_id, job_id))
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
            values = list(fields.values()) + [self.project_id, job_id]

            cur.execute(
                f"UPDATE jobs SET {set_clause}, updated_at=strftime('%s','now') WHERE project_id=? AND job_id=?",
                values
            )
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0

    # ---------------------
    # VLM-First 專用方法
    # ---------------------
    def complete_vlm(self, job_id: str, vlm_result: Dict[str, Any],
                     validation: Dict[str, Any] = None,
                     stats: Dict[str, Any] = None,
                     qr_verified: bool = False) -> bool:
        """Complete VLM processing and mark job as done."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()

            vlm_json = json.dumps(vlm_result, ensure_ascii=False)
            validation_json = json.dumps(validation, ensure_ascii=False) if validation else None
            stats_json = json.dumps(stats, ensure_ascii=False) if stats else None

            cur.execute(
                """UPDATE jobs SET
                   status='done',
                   vlm_result_json=?,
                   validation_json=?,
                   vlm_stats=?,
                   qr_verified=?,
                   updated_at=strftime('%s','now')
                   WHERE project_id=? AND job_id=?""",
                (vlm_json, validation_json, stats_json, 1 if qr_verified else 0, self.project_id, job_id)
            )
            affected = cur.rowcount
            conn.commit()
            conn.close()

            if affected > 0:
                self.emit_event(job_id, "vlm_completed", {"qr_verified": qr_verified})
            return affected > 0

    # ---------------------
    # Query Methods
    # ---------------------
    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs for this project, optionally filtered by status."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            if status:
                cur.execute(
                    "SELECT * FROM jobs WHERE project_id=? AND status=? ORDER BY created_at ASC",
                    (self.project_id, status),
                )
            else:
                cur.execute("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at ASC", (self.project_id,))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def count_jobs(self) -> Dict[str, int]:
        """Count jobs grouped by status."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT status, COUNT(1) as cnt FROM jobs WHERE project_id=? GROUP BY status", (self.project_id,))
            rows = cur.fetchall()
            conn.close()
            return {r["status"]: r["cnt"] for r in rows}

    def has_pending_work(self) -> bool:
        """Check if there's any pending or running work."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT job_id FROM jobs
                   WHERE project_id=? AND status IN ('ready', 'pending', 'running') LIMIT 1""",
                (self.project_id,)
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
            "INSERT INTO events(project_id, job_id, event_type, payload) VALUES(?,?,?,?)",
            (self.project_id, job_id, event_type, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    # ---------------------
    # Administrative Methods
    # ---------------------
    def dump_all(self) -> Dict[str, Any]:
        """Dump all database contents for this project (debugging)."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE project_id=? ORDER BY created_at ASC", (self.project_id,))
        jobs = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM events WHERE project_id=? ORDER BY ts ASC", (self.project_id,))
        events = [dict(r) for r in cur.fetchall()]
        conn.close()
        return {"jobs": jobs, "events": events}

    def mark_stale_as_failed(self, stale_seconds: int = 60 * 60 * 6) -> int:
        """Mark pending/running jobs older than stale_seconds as failed."""
        cutoff = int(time.time()) - int(stale_seconds)
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE jobs SET status='failed', updated_at=strftime('%s','now')
                   WHERE project_id=? AND (status='pending' OR status='running') AND created_at<?""",
                (self.project_id, cutoff),
            )
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected

    def delete_all_project_jobs(self) -> int:
        """Delete ALL jobs and events for this project (used when deleting a project)."""
        with self.lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM events WHERE project_id=?", (self.project_id,))
            cur.execute("DELETE FROM jobs WHERE project_id=?", (self.project_id,))
            affected = cur.rowcount
            conn.commit()
            conn.close()
            logger.info(f"[JobRepository] 已清除專案 {self.project_id} 的所有任務 ({affected} 筆)")
            return affected

    # ---------------------
    # Presentation Helpers (ex-TaskManager)
    # ---------------------
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full job details with parsed JSON (for editor view)."""
        job = self.get_job(job_id)
        if not job:
            return None

        vlm_result = None
        validation = None
        vlm_stats = None
        manual_json = None

        try:
            if job.get("vlm_result_json"):
                vlm_result = json.loads(job["vlm_result_json"])
        except Exception:
            pass
        try:
            if job.get("validation_json"):
                validation = json.loads(job["validation_json"])
        except Exception:
            pass
        try:
            if job.get("vlm_stats"):
                vlm_stats = json.loads(job["vlm_stats"])
        except Exception:
            pass
        try:
            if job.get("manual_json_text"):
                manual_json = json.loads(job["manual_json_text"])
        except Exception:
            pass

        return {
            "job_id": job["job_id"],
            "image_path": job["image_path"],
            "status": job["status"],
            "vlm_result": vlm_result,
            "validation": validation,
            "vlm_stats": vlm_stats,
            "qr_verified": bool(job.get("qr_verified")),
            "manual_json": manual_json,
            "manual_updated_at": job.get("manual_updated_at"),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        }

    def save_manual_json(self, job_id: str, json_data: dict) -> bool:
        """儲存人工編輯的 JSON 結果"""
        json_text = json.dumps(json_data, ensure_ascii=False)
        now = int(time.time())

        result = self.update_job(
            job_id,
            manual_json_text=json_text,
            manual_updated_at=now
        )

        if result:
            self.emit_event(job_id, "manual_json_saved", {"timestamp": now})
        return result

    def get_display_result(self, job_id: str) -> Optional[dict]:
        """獲取顯示用的結果 (優先級: manual_json_text → vlm_result_json)"""
        job = self.get_job(job_id)
        if not job:
            return None

        if job.get("manual_json_text"):
            try:
                return json.loads(job["manual_json_text"])
            except Exception:
                pass

        if job.get("vlm_result_json"):
            try:
                return json.loads(job["vlm_result_json"])
            except Exception:
                pass

        return None
