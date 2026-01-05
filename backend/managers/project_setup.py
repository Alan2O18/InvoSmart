import os
import shutil
import sqlite3
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ProjectSetup:
    def __init__(self, workspace_root: Path, project_crud):
        self.workspace_root = workspace_root
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.project_crud = project_crud

    def _project_root(self, project_id: str) -> Path:
        return (self.workspace_root / project_id).resolve()

    def _ensure_layout(self, root: Path):
        splits = root / "分割發票"
        raws = root / "原始輸入"
        splits.mkdir(parents=True, exist_ok=True)
        raws.mkdir(parents=True, exist_ok=True)
        return {"splits": splits, "raws": raws}

    def _init_jobs_db(self, db_path: str, overwrite: bool = False):
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
            cur.executescript(
                """
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              image_path TEXT NOT NULL,
              status TEXT NOT NULL,
              stage TEXT NOT NULL,
              ocr_result_json TEXT,
              llm_result_json TEXT,
              ocr_stats TEXT,
              llm_stats TEXT,
              manual_ocr_text TEXT,
              manual_updated_at REAL,
              created_at REAL DEFAULT (strftime('%s','now')),
              updated_at REAL DEFAULT (strftime('%s','now')),
              auto_advance INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            """
            )
            conn.commit()
        finally:
            conn.close()

    def setup_project(
        self,
        project_id: str,
        input_image: Optional[list[str]] = None,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict] = None,
        resume_if_db_exists: bool = True,
        force_setup: bool = False,
    ) -> Dict[str, Any]:
        root = self._project_root(project_id)
        
        # Check if already registered
        existing = self.project_crud.get_project(project_id)
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
            # Resume existing project
            self.project_crud.register_project(project_id, name, str(root), notes, metadata)
            logger.info("resume project %s from existing jobs.db %s", project_id, str(jobs_db))
            return {
                "status": "resumed_registered",
                "project_root": str(root),
                "project_status": "NEW",
            }
        else:
            # Create new project
            self._init_jobs_db(str(jobs_db), overwrite=True)
            self.project_crud.register_project(project_id, name, str(root), notes, metadata)
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

    def delete_project_files(self, project_id: str):
        root = self._project_root(project_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
