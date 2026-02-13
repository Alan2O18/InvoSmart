# Processing Router - 處理操作端點 (VLM-First)
import logging
from fastapi import APIRouter, HTTPException, Form, Depends
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{project_id}/run_split")
def run_split(project_id: str, engine: Engine = Depends(get_engine)):
    """Run split for all raw files in project."""
    try:
        return engine.run_splitting(project_id)
    except Exception as e:
        logger.error(f"Error running split for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/split/{filename}")
def run_split_single(project_id: str, filename: str, engine: Engine = Depends(get_engine)):
    """Run split for a single file."""
    try:
        return engine.run_split_single(project_id, filename)
    except Exception as e:
        logger.error(f"Error running split single for {project_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_processing")
def run_processing(project_id: str, engine: Engine = Depends(get_engine)):
    """Run VLM processing for all jobs in project (VLM-First)."""
    try:
        return engine.run_processing(project_id)
    except Exception as e:
        logger.error(f"Error running processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_export")
def run_export(project_id: str, engine: Engine = Depends(get_engine)):
    """Export project to Excel."""
    try:
        return engine.run_excel(project_id)
    except Exception as e:
        logger.error(f"Error exporting excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_archive")
def run_archive(project_id: str, engine: Engine = Depends(get_engine)):
    """Archive project."""
    try:
        return engine.archive_project(project_id)
    except Exception as e:
        logger.error(f"Error archiving project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/regenerate")
def regenerate_project(project_id: str, excel_path: str = Form(...), engine: Engine = Depends(get_engine)):
    """Regenerate project from archived Excel."""
    try:
        return engine.regenerate_project(project_id, excel_path)
    except Exception as e:
        logger.error(f"Error regenerating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
