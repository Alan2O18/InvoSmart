import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .project_crud import ProjectCRUD
from .project_setup import ProjectSetup

logger = logging.getLogger("ProjectManagerV4")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

class ProjectManager:
    def __init__(self, config: Dict):
        self.global_db_path = Path(config["global_db_path"]).expanduser().resolve()
        self.workspace_root = Path(config["workspace_root"]).expanduser().resolve()
        
        self.project_crud = ProjectCRUD(self.global_db_path)
        self.project_setup = ProjectSetup(self.workspace_root, self.project_crud)

    def list_projects(self) -> list[dict]:
        return self.project_crud.list_projects()

    def _project_root(self, project_id: str) -> Path:
        return self.project_setup._project_root(project_id)

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
        return self.project_setup.setup_project(
            project_id, input_image, name, notes, metadata, resume_if_db_exists, force_setup
        )

    def update_project_status(self, project_id: str, status_code: str):
        self.project_crud.update_project_status(project_id, status_code)

    def update_metadata(self, project_id: str, metadata: Dict):
        self.project_crud.update_project_metadata(project_id, metadata)

    def update_activity_info(self, project_id: str, info: Dict[str, Any]):
        self.project_crud.update_activity_info(project_id, info)

    def upsert_group(self, group_name: str, leader_name: str):
        self.project_crud.upsert_group(group_name, leader_name)

    def list_groups(self) -> list[dict]:
        return self.project_crud.list_groups()

    def delete_group(self, group_name: str):
        self.project_crud.delete_group(group_name)

    def delete_project(self, project_id: str):
        # Delete files first
        self.project_setup.delete_project_files(project_id)
        # Then delete from DB
        self.project_crud.delete_project(project_id)

    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        # This logic was previously in detect_project_progress
        # We can keep it here or move to a status helper.
        # For now, let's keep it here but clean it up.
        root = self._project_root(project_id)
        if not root.exists():
            raise FileNotFoundError("project root not found")
        
        layout = self.project_setup._ensure_layout(root)
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
                    "SELECT COUNT(1) AS cnt FROM jobs WHERE status = 'done' AND llm_result_json IS NOT NULL"
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
        """
        Calculate suggested_status and sync it to the database.
        Call this after major operations (split, OCR, LLM, etc.)
        """
        try:
            status_info = self.get_project_status(project_id)
            suggested_status = status_info["suggested_status"]
            
            # Get current status from DB
            project = self.project_crud.get_project(project_id)
            if project and project.get("status") != suggested_status:
                # Only update if status has changed
                self.update_project_status(project_id, suggested_status)
                logger.info(f"Auto-synced status for {project_id}: {suggested_status}")
        except Exception as e:
            logger.error(f"Error syncing status for {project_id}: {e}")

