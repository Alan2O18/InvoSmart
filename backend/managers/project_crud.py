import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any

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

class ProjectCRUD:
    def __init__(self, global_db_path: Path):
        self.global_db_path = global_db_path
        self._ensure_global_db()

    def _conn_global(self):
        conn = sqlite3.connect(str(self.global_db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

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
        conn = self._conn_global()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(sql_projects)
            conn.execute(sql_groups)
            
            # Check if metadata column exists (migration for very old DBs)
            try:
                conn.execute("SELECT metadata FROM projects LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE projects ADD COLUMN metadata TEXT")
            
            conn.commit()
        finally:
            conn.close()

    def list_projects(self) -> list[dict]:
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

    def get_project(self, project_id: str) -> dict:
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

    def register_project(self, project_id: str, name: str, root_path: str, notes: str = None, metadata: dict = None):
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
        """
        Update specific activity fields by merging them into the metadata JSON.
        """
        conn = self._conn_global()
        try:
            # First fetch existing metadata
            cur = conn.cursor()
            cur.execute("SELECT metadata FROM projects WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if not row:
                return # Project not found
            
            current_metadata = {}
            if row[0]:
                try:
                    current_metadata = json.loads(row[0])
                except:
                    pass
            
            # Merge new info
            current_metadata.update(info)
            
            # Update DB
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
        conn = self._conn_global()
        try:
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.commit()
        finally:
            conn.close()

    # --- Group Management ---
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

    def list_groups(self) -> list[dict]:
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
