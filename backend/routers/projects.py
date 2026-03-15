# Projects Router - 專案 CRUD 端點
import os
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError
from backend.utils.utils import handle_upload_files

logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectCreate(BaseModel):
    project_id: str
    metadata: Optional[dict] = None


@router.get("/")
async def list_projects(engine: Engine = Depends(get_engine)):
    """List all projects."""
    return await engine.project_repo.list_projects()


@router.post("/")
async def create_project(
    project_id: str = Form(...),
    metadata: str = Form(None),  # JSON string
    files: List[UploadFile] = File(...),
    engine: Engine = Depends(get_engine)
):
    """Create a new project with uploaded files."""
    try:
        async with handle_upload_files(files) as saved_file_paths:
            meta_dict = {}
            activity_name = None
            if metadata:
                try:
                    meta_dict = json.loads(metadata)
                    activity_name = meta_dict.get('name') or meta_dict.get('projectName')
                except Exception:
                    pass

            result = await engine.create_project(project_id, saved_file_paths, name=activity_name, metadata=meta_dict)
            return result
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}")
async def update_project(project_id: str, metadata: dict, engine: Engine = Depends(get_engine)):
    """Update project metadata."""
    try:
        await engine.project_repo.update_project_metadata(project_id, metadata)
        return await engine.project_repo.get_project(project_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(project_id: str, engine: Engine = Depends(get_engine)):
    """Delete a project."""
    try:
        return await engine.project_repo.delete_project(project_id)
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/detail")
async def get_project_detail(project_id: str, engine: Engine = Depends(get_engine)):
    """Get full project payload (including metadata)."""
    try:
        project = await engine.project_repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detail for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
async def get_project_status(project_id: str, engine: Engine = Depends(get_engine)):
    """Get project status and details."""
    try:
        await engine.project_repo.sync_status_to_db(project_id)
        return await engine.project_repo.get_project_status(project_id)
    except Exception as e:
        logger.error(f"Error getting status for {project_id}: {e}")
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/activity_info")
async def update_activity_info(project_id: str, info: dict, engine: Engine = Depends(get_engine)):
    """Update project activity info."""
    try:
        await engine.project_repo.update_activity_info(project_id, info)
        return await engine.project_repo.get_project(project_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating activity info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/generate-voucher-pdf")
async def generate_voucher_pdf(project_id: str, engine: Engine = Depends(get_engine)):
    """產生並下載憑證黏貼 PDF"""
    try:
        pdf_path = await engine.generate_voucher_pdf(project_id)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF generation failed")
            
        return FileResponse(
            path=pdf_path,
            filename=f"憑證黏貼_{project_id}.pdf",
            media_type="application/pdf"
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        logger.error(f"Error generating voucher PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
