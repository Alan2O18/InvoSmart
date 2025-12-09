# Projects Router - 專案 CRUD 端點
import shutil
import os
import tempfile
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from backend.engine import engine

logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectCreate(BaseModel):
    project_id: str
    metadata: Optional[dict] = None


@router.get("/")
def list_projects():
    """List all projects."""
    return engine.project_manager.list_projects()


@router.post("/")
def create_project(
    project_id: str = Form(...),
    metadata: str = Form(None),  # JSON string
    files: List[UploadFile] = File(...)
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
                # Extract 'name' field from metadata for the database name column
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
def update_project(project_id: str, metadata: dict):
    """Update project metadata."""
    try:
        # Extract 'name' from metadata if present to update database name field
        activity_name = metadata.get('name') or metadata.get('projectName')
        if activity_name:
            # Update ONLY the name field without touching status or other fields
            existing = engine.project_manager.project_crud.get_project(project_id)
            if existing:
                # Direct SQL update to avoid resetting status
                conn = engine.project_manager.project_crud._conn_global()
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
        
        # Also update metadata
        return engine.project_manager.update_metadata(project_id, metadata)
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
def delete_project(project_id: str):
    """Delete a project."""
    try:
        return engine.project_manager.delete_project(project_id)
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
def get_project_status(project_id: str):
    """Get project status and details."""
    try:
        # Auto-sync status to database before returning
        engine.project_manager.sync_status_to_db(project_id)
        return engine.project_manager.get_project_status(project_id)
    except Exception as e:
        logger.error(f"Error getting status for {project_id}: {e}")
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/activity_info")
def update_activity_info(project_id: str, info: dict):
    """Update project activity info."""
    try:
        return engine.project_manager.update_activity_info(project_id, info)
    except Exception as e:
        logger.error(f"Error updating activity info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
