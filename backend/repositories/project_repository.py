# backend/repositories/project_repository.py
"""
ProjectRepository - 專案資料存取層

合併原 project_crud.py + project_setup.py + project_manager.py 的功能。
負責：
- 專案 CRUD (全域資料庫)
- 專案目錄建立/檔案管理
- 組別/詞彙管理
"""
import sqlite3
import json
import time
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

PROJECT_STATUS = {
    "NEW": "新建（空）",
    "INGESTED": "已匯入原始資料",
    "SPLIT": "已切分",
    "PROCESSING": "辨識中",
    "PROCESSED": "辨識完畢",
    "ARCHIVED": "已匯出 Excel",
    "SEALED": "已封存",
}

# VLM-First jobs.db Schema
JOBS_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  image_path TEXT NOT NULL,
  status TEXT NOT NULL,
  vlm_result_json TEXT,
  vlm_stats TEXT,
  validation_json TEXT,
  qr_verified INTEGER DEFAULT 0,
  manual_json_text TEXT,
  manual_updated_at REAL,
  created_at REAL DEFAULT (strftime('%s','now')),
  updated_at REAL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT,
  event_type TEXT,
  ts REAL DEFAULT (strftime('%s','now')),
  payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
"""


class ProjectRepository:
    """專案資料存取層 (合併版)"""

    def __init__(self, config: Dict):
        self.global_db_path = Path(config["global_db_path"]).expanduser().resolve()
        self.workspace_root = Path(config["workspace_root"]).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self._ensure_global_db()

    def _conn_global(self):
        conn = sqlite3.connect(str(self.global_db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    # ===================================================
    # Global DB Schema
    # ===================================================
    def _ensure_global_db(self):
        sql_projects = """
        CREATE TABLE IF NOT EXISTS projects (
          project_id TEXT PRIMARY KEY,
          name TEXT,
          root_path TEXT,
          status TEXT,
          created_at REAL,
          updated_at REAL,
          notes TEXT,
          metadata TEXT
        );
        """
        sql_groups = """
        CREATE TABLE IF NOT EXISTS groups (
            group_name TEXT PRIMARY KEY,
            leader_name TEXT
        );
        """
        sql_vocab = """
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY,
            category TEXT,
            term TEXT,
            frequency INTEGER DEFAULT 1,
            last_seen_at REAL,
            UNIQUE(category, term)
        );
        """
        conn = self._conn_global()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(sql_projects)
            conn.execute(sql_groups)
            conn.execute(sql_vocab)

            # Migration: metadata column
            try:
                conn.execute("SELECT metadata FROM projects LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE projects ADD COLUMN metadata TEXT")

            conn.commit()
        finally:
            conn.close()

    # ===================================================
    # Project CRUD
    # ===================================================
    def _project_root(self, project_id: str) -> Path:
        return (self.workspace_root / project_id).resolve()

    def list_projects(self) -> List[dict]:
        conn = self._conn_global()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM projects ORDER BY updated_at DESC")
            rows = cur.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except:
                        d["metadata"] = {}
                else:
                    d["metadata"] = {}
                result.append(d)
            return result
        finally:
            conn.close()

    def get_project(self, project_id: str) -> Optional[dict]:
        conn = self._conn_global()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                if d.get("metadata"):
                    try:
                        d["metadata"] = json.loads(d["metadata"])
                    except:
                        d["metadata"] = {}
                return d
            return None
        finally:
            conn.close()

    def register_project(self, project_id: str, name: str, root_path: str,
                         notes: str = None, metadata: dict = None):
        conn = self._conn_global()
        try:
            now = int(time.time())
            metadata_json = json.dumps(metadata) if metadata else None
            conn.execute(
                "INSERT OR REPLACE INTO projects (project_id, name, root_path, status, created_at, updated_at, notes, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, name or project_id, root_path, "NEW", now, now, notes, metadata_json),
            )
            conn.commit()
        finally:
            conn.close()

    def update_project_status(self, project_id: str, status_code: str):
        if status_code not in PROJECT_STATUS:
            raise ValueError("Unknown status code: " + status_code)
        conn = self._conn_global()
        try:
            now = int(time.time())
            conn.execute(
                "UPDATE projects SET status = ?, updated_at = ? WHERE project_id = ?",
                (status_code, now, project_id),
            )
            conn.commit()
            logger.info("project %s status -> %s", project_id, status_code)
        finally:
            conn.close()

    def update_project_metadata(self, project_id: str, metadata: Dict):
        conn = self._conn_global()
        try:
            now = int(time.time())
            metadata_json = json.dumps(metadata)
            conn.execute(
                "UPDATE projects SET metadata = ?, updated_at = ? WHERE project_id = ?",
                (metadata_json, now, project_id),
            )
            conn.commit()
        finally:
            conn.close()

    def update_activity_info(self, project_id: str, info: Dict[str, Any]):
        """Merge activity fields into project metadata."""
        conn = self._conn_global()
        try:
            cur = conn.cursor()
            cur.execute("SELECT metadata FROM projects WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if not row:
                return

            current_metadata = {}
            if row[0]:
                try:
                    current_metadata = json.loads(row[0])
                except:
                    pass

            current_metadata.update(info)
            now = int(time.time())
            metadata_json = json.dumps(current_metadata)
            conn.execute(
                "UPDATE projects SET metadata = ?, updated_at = ? WHERE project_id = ?",
                (metadata_json, now, project_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_project(self, project_id: str):
        # Delete files first
        root = self._project_root(project_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        # Then delete from DB
        conn = self._conn_global()
        try:
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.commit()
        finally:
            conn.close()

    # ===================================================
    # Project Setup / Directory Management
    # ===================================================
    def _ensure_layout(self, root: Path):
        splits = root / "分割發票"
        raws = root / "原始輸入"
        splits.mkdir(parents=True, exist_ok=True)
        raws.mkdir(parents=True, exist_ok=True)
        return {"splits": splits, "raws": raws}

    def _init_jobs_db(self, db_path: str, overwrite: bool = False):
        """初始化 jobs.db (VLM-First Schema)"""
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and not overwrite:
            return
        if p.exists() and overwrite:
            try:
                p.unlink()
            except Exception:
                pass
        conn = sqlite3.connect(str(p))
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.executescript(JOBS_DB_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def setup_project(
        self,
        project_id: str,
        input_image: Optional[List[str]] = None,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict] = None,
        resume_if_db_exists: bool = True,
        force_setup: bool = False,
    ) -> Dict[str, Any]:
        root = self._project_root(project_id)

        # Check if already registered
        existing = self.get_project(project_id)
        if existing and not force_setup:
            return {
                "status": "already_registered",
                "project_root": existing["root_path"],
                "project_status": existing["status"],
            }

        existed = root.exists()
        self._ensure_layout(root)
        jobs_db = root / "jobs.db"

        if existed and jobs_db.exists() and resume_if_db_exists:
            self.register_project(project_id, name, str(root), notes, metadata)
            logger.info("resume project %s from existing jobs.db %s", project_id, str(jobs_db))
            return {
                "status": "resumed_registered",
                "project_root": str(root),
                "project_status": "NEW",
            }
        else:
            self._init_jobs_db(str(jobs_db), overwrite=True)
            self.register_project(project_id, name, str(root), notes, metadata)
            logger.info("created new project %s at %s (jobs.db init)", project_id, str(root))

            if input_image:
                for i in input_image:
                    dest_path = root / "原始輸入" / Path(i).name
                    shutil.copy(i, dest_path)

            return {
                "status": "created_new",
                "project_root": str(root),
                "project_status": "NEW",
            }

    # ===================================================
    # Project Status Detection
    # ===================================================
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Detect project progress from file system and DB state."""
        root = self._project_root(project_id)
        if not root.exists():
            raise FileNotFoundError("project root not found")

        layout = self._ensure_layout(root)
        ingested = any(layout["raws"].iterdir())
        split = any(layout["splits"].iterdir())
        db_path = root / "jobs.db"
        processing = False
        processed = False

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(1) AS cnt FROM jobs WHERE status IN ('running','processing','pending')"
                )
                r = cur.fetchone()
                processing = r and r["cnt"] and r["cnt"] > 0
                cur.execute(
                    "SELECT COUNT(1) AS cnt FROM jobs WHERE status = 'done' AND vlm_result_json IS NOT NULL"
                )
                r2 = cur.fetchone()
                processed = r2 and r2["cnt"] and r2["cnt"] > 0
            finally:
                conn.close()

        suggested = "NEW"
        if processing:
            suggested = "PROCESSING"
        elif processed:
            suggested = "PROCESSED"
        elif split:
            suggested = "SPLIT"
        elif ingested:
            suggested = "INGESTED"

        return {
            "ingested": ingested,
            "split": split,
            "processing": processing,
            "processed": processed,
            "suggested_status": suggested,
        }

    def sync_status_to_db(self, project_id: str):
        """Calculate suggested_status and sync it to the database."""
        try:
            status_info = self.get_project_status(project_id)
            suggested_status = status_info["suggested_status"]

            project = self.get_project(project_id)
            if project and project.get("status") != suggested_status:
                self.update_project_status(project_id, suggested_status)
                logger.info(f"Auto-synced status for {project_id}: {suggested_status}")
        except Exception as e:
            logger.error(f"Error syncing status for {project_id}: {e}")

    # ===================================================
    # Group Management
    # ===================================================
    def upsert_group(self, group_name: str, leader_name: str):
        conn = self._conn_global()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO groups (group_name, leader_name) VALUES (?, ?)",
                (group_name, leader_name)
            )
            conn.commit()
        finally:
            conn.close()

    def list_groups(self) -> List[dict]:
        conn = self._conn_global()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM groups")
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def delete_group(self, group_name: str):
        conn = self._conn_global()
        try:
            conn.execute("DELETE FROM groups WHERE group_name = ?", (group_name,))
            conn.commit()
        finally:
            conn.close()

    # ===================================================
    # Vocabulary Management
    # ===================================================
    def add_vocabulary_term(self, category: str, term: str):
        """新增或更新詞彙頻率"""
        if not term or not category:
            return

        term = term.strip()
        now = time.time()
        conn = self._conn_global()
        try:
            cur = conn.cursor()
            cur.execute("SELECT frequency FROM vocabulary WHERE category=? AND term=?", (category, term))
            row = cur.fetchone()

            if row:
                new_freq = row[0] + 1
                cur.execute(
                    "UPDATE vocabulary SET frequency=?, last_seen_at=? WHERE category=? AND term=?",
                    (new_freq, now, category, term)
                )
            else:
                cur.execute(
                    "INSERT INTO vocabulary (category, term, frequency, last_seen_at) VALUES (?, ?, 1, ?)",
                    (category, term, now)
                )
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding vocabulary {category}:{term} - {e}")
        finally:
            conn.close()

    def search_vocabulary(self, category: str, limit: int = 100) -> List[str]:
        """查詢高頻詞彙"""
        conn = self._conn_global()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT term FROM vocabulary WHERE category=? ORDER BY frequency DESC LIMIT ?",
                (category, limit)
            )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
