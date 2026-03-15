# backend/repositories/project_repository.py
"""
ProjectRepository - 專案資料存取層

負責：
- 專案 CRUD (全域資料庫)
- 專案目錄建立/檔案管理
- 組別管理
"""
import time
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Project, Group

logger = logging.getLogger(__name__)

PROJECT_STATUS = {
    "NEW": "新建（空）",
    "INGESTED": "已匯入原始資料",
    "SPLIT": "已切分",
    "PROCESSING": "辨識中",
    "PROCESSED": "辨識完畢",
    "ARCHIVED": "已封存",
    "SEALED": "已封存（舊狀態）",
}

LOCKED_PROJECT_STATUSES = {"ARCHIVED", "SEALED"}


class ProjectArchivedError(RuntimeError):
    """Raised when a write operation targets an archived project."""

class ProjectRepository:
    """專案資料存取層 (SQLAlchemy ORM 版)"""

    def __init__(self, config: Dict, session_factory: Callable[[], AsyncSession]):
        self.workspace_root = Path(config["workspace_root"]).expanduser().resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.session_factory = session_factory

    # ===================================================
    # File System Layout Helpers
    # ===================================================
    def _project_root(self, project_id: str) -> Path:
        return (self.workspace_root / project_id).resolve()

    def _ensure_layout(self, root: Path) -> Dict[str, Path]:
        splits = root / "分割發票"
        raws = root / "原始輸入"
        splits.mkdir(parents=True, exist_ok=True)
        raws.mkdir(parents=True, exist_ok=True)
        return {"splits": splits, "raws": raws}

    # ===================================================
    # Project CRUD
    # ===================================================
    async def list_projects(self) -> List[dict]:
        async with self.session_factory() as session:
            stmt = select(Project).order_by(Project.updated_at.desc())
            result = await session.execute(stmt)
            projects = result.scalars().all()
            return [
                {
                    "project_id": p.project_id,
                    "name": p.name,
                    "root_path": p.root_path,
                    "status": p.status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "notes": p.notes,
                    "metadata": p.meta_data or {}
                }
                for p in projects
            ]

    async def get_project(self, project_id: str) -> Optional[dict]:
        async with self.session_factory() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            result = await session.execute(stmt)
            p = result.scalar_one_or_none()
            if p:
                return {
                    "project_id": p.project_id,
                    "name": p.name,
                    "root_path": p.root_path,
                    "status": p.status,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "notes": p.notes,
                    "metadata": p.meta_data or {}
                }
            return None

    async def register_project(self, project_id: str, name: str, root_path: str,
                               notes: str = None, metadata: dict = None):
        async with self.session_factory() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            p = (await session.execute(stmt)).scalar_one_or_none()
            
            now = time.time()
            if p:
                p.name = name or project_id
                p.root_path = root_path
                p.notes = notes
                p.meta_data = metadata or {}
                p.updated_at = now
            else:
                p = Project(
                    project_id=project_id,
                    name=name or project_id,
                    root_path=root_path,
                    status="NEW",
                    created_at=now,
                    updated_at=now,
                    notes=notes,
                    meta_data=metadata or {}
                )
                session.add(p)
            await session.commit()

    async def update_project_status(self, project_id: str, status_code: str):
        if status_code not in PROJECT_STATUS:
            raise ValueError("Unknown status code: " + status_code)
            
        async with self.session_factory() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            p = (await session.execute(stmt)).scalar_one_or_none()
            if p:
                p.status = status_code
                p.updated_at = time.time()
                await session.commit()
                logger.info("project %s status -> %s", project_id, status_code)

    async def update_project_metadata(self, project_id: str, metadata: Dict):
        await self.assert_project_editable(project_id)
        async with self.session_factory() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            p = (await session.execute(stmt)).scalar_one_or_none()
            if p:
                p.meta_data = metadata
                p.updated_at = time.time()
                await session.commit()

    async def update_activity_info(self, project_id: str, info: Dict[str, Any]):
        """Merge activity fields into project metadata."""
        await self.assert_project_editable(project_id)
        async with self.session_factory() as session:
            stmt = select(Project).where(Project.project_id == project_id)
            p = (await session.execute(stmt)).scalar_one_or_none()
            if p:
                current_metadata = p.meta_data or {}
                # Handle SQLAlchemy JSON mutation
                new_metadata = dict(current_metadata)
                new_metadata.update(info)
                p.meta_data = new_metadata
                p.updated_at = time.time()
                await session.commit()

    async def delete_project(self, project_id: str):
        # Delete files first
        root = self._project_root(project_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
            
        # Then delete from DB
        async with self.session_factory() as session:
            stmt = delete(Project).where(Project.project_id == project_id)
            await session.execute(stmt)
            await session.commit()

    # ===================================================
    # Group Management
    # ===================================================
    async def list_groups(self) -> List[dict]:
        async with self.session_factory() as session:
            stmt = select(Group).order_by(Group.group_name)
            result = await session.execute(stmt)
            groups = result.scalars().all()
            return [{"group_name": g.group_name, "leader_name": g.leader_name} for g in groups]

    async def upsert_group(self, group_name: str, leader_name: str):
        async with self.session_factory() as session:
            stmt = select(Group).where(Group.group_name == group_name)
            g = (await session.execute(stmt)).scalar_one_or_none()
            if g:
                g.leader_name = leader_name
            else:
                g = Group(group_name=group_name, leader_name=leader_name)
                session.add(g)
            await session.commit()

    async def delete_group(self, group_name: str):
        async with self.session_factory() as session:
            stmt = delete(Group).where(Group.group_name == group_name)
            await session.execute(stmt)
            await session.commit()

    # ===================================================
    # Project Setup / Directory Management
    # ===================================================
    async def setup_project(
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
        existing = await self.get_project(project_id)
        if existing and not force_setup:
            return {
                "status": "already_registered",
                "project_root": existing["root_path"],
                "project_status": existing["status"],
            }

        existed = root.exists()
        self._ensure_layout(root)

        if existed and resume_if_db_exists:
            await self.register_project(project_id, name, str(root), notes, metadata)
            logger.info("resume project %s from existing dir %s", project_id, str(root))
            return {
                "status": "resumed_registered",
                "project_root": str(root),
                "project_status": "NEW",
            }
        else:
            await self.register_project(project_id, name, str(root), notes, metadata)
            logger.info("created new project %s at %s (global.db)", project_id, str(root))

            if input_image:
                for i in input_image:
                    dest_path = root / "原始輸入" / Path(i).name
                    shutil.copy(i, dest_path)

            return {
                "status": "created_new",
                "project_root": str(root),
                "project_status": "NEW",
            }

    async def assert_project_editable(self, project_id: str):
        project = await self.get_project(project_id)
        if project and project.get("status") in LOCKED_PROJECT_STATUSES:
            raise ProjectArchivedError(f"Project {project_id} is archived and read-only")

    # ===================================================
    # Project Status Detection
    # ===================================================
    async def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """Detect project progress from file system and DB state."""
        from backend.database.models import Job
        
        root = self._project_root(project_id)
        if not root.exists():
            raise FileNotFoundError("project root not found")

        layout = self._ensure_layout(root)
        ingested = any(layout["raws"].iterdir())
        split = any(layout["splits"].iterdir())
        processing = False
        processed = False

        try:
            async with self.session_factory() as session:
                stmt = select(Job.status).where(Job.project_id == project_id)
                job_statuses = (await session.execute(stmt)).scalars().all()
                processing = any(s in ("running", "processing", "pending") for s in job_statuses)
                processed = any(s == "done" for s in job_statuses)
        except Exception as e:
            logger.warning(f"[ProjectRepo] 無法從 DB 取得 job 狀態: {e}")

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

    async def sync_status_to_db(self, project_id: str):
        """Calculate suggested_status and sync it to the database."""
        try:
            project = await self.get_project(project_id)
            if project and project.get("status") in LOCKED_PROJECT_STATUSES:
                return

            status_info = await self.get_project_status(project_id)
            suggested_status = status_info["suggested_status"]

            if project and project.get("status") != suggested_status:
                await self.update_project_status(project_id, suggested_status)
                logger.info(f"Auto-synced status for {project_id}: {suggested_status}")
        except Exception as e:
            logger.error(f"Error syncing status for {project_id}: {e}")
