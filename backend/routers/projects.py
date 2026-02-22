# Projects Router - 專案 CRUD 端點
import shutil
import os
import tempfile
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectCreate(BaseModel):
    project_id: str
    metadata: Optional[dict] = None


@router.get("/")
def list_projects(engine: Engine = Depends(get_engine)):
    """List all projects."""
    return engine.project_repo.list_projects()


@router.post("/")
def create_project(
    project_id: str = Form(...),
    metadata: str = Form(None),  # JSON string
    files: List[UploadFile] = File(...),
    engine: Engine = Depends(get_engine)
):
    """Create a new project with uploaded files."""
    temp_dir = tempfile.mkdtemp()
    saved_file_paths = []
    
    try:
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_file_paths.append(file_path)
        
        meta_dict = {}
        activity_name = None
        if metadata:
            try:
                meta_dict = json.loads(metadata)
                activity_name = meta_dict.get('name') or meta_dict.get('projectName')
            except:
                pass

        result = engine.create_project(project_id, saved_file_paths, name=activity_name, metadata=meta_dict)
        return result
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.put("/{project_id}")
def update_project(project_id: str, metadata: dict, engine: Engine = Depends(get_engine)):
    """Update project metadata."""
    try:
        activity_name = metadata.get('name') or metadata.get('projectName')
        if activity_name:
            existing = engine.project_repo.get_project(project_id)
            if existing:
                conn = engine.project_repo._conn_global()
                try:
                    import time
                    now = int(time.time())
                    conn.execute(
                        "UPDATE projects SET name = ?, updated_at = ? WHERE project_id = ?",
                        (activity_name, now, project_id)
                    )
                    conn.commit()
                finally:
                    conn.close()
        
        return engine.project_repo.update_project_metadata(project_id, metadata)
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
def delete_project(project_id: str, engine: Engine = Depends(get_engine)):
    """Delete a project."""
    try:
        return engine.project_repo.delete_project(project_id)
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
def get_project_status(project_id: str, engine: Engine = Depends(get_engine)):
    """Get project status and details."""
    try:
        engine.project_repo.sync_status_to_db(project_id)
        return engine.project_repo.get_project_status(project_id)
    except Exception as e:
        logger.error(f"Error getting status for {project_id}: {e}")
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/activity_info")
def update_activity_info(project_id: str, info: dict, engine: Engine = Depends(get_engine)):
    """Update project activity info."""
    try:
        return engine.project_repo.update_activity_info(project_id, info)
    except Exception as e:
        logger.error(f"Error updating activity info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/job-ids")
def get_project_job_ids(project_id: str, engine: Engine = Depends(get_engine)):
    """Get list of job IDs for navigation."""
    try:
        job_repo = engine.get_job_repo(project_id)
        jobs = job_repo.list_jobs()
        # Return lightweight list for navigation
        return [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "image_path": job["image_path"]
            }
            for job in jobs
        ]
    except Exception as e:
        logger.error(f"Error getting job IDs for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
