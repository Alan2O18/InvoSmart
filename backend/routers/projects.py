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
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except:
                pass

        result = engine.create_project(project_id, saved_file_paths, metadata=meta_dict)
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
