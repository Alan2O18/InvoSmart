# Processing Router - 處理操作端點
import logging
from fastapi import APIRouter, HTTPException, Form
from backend.engine import engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{project_id}/run_split")
def run_split(project_id: str):
    """Run split for all raw files in project."""
    try:
        return engine.run_splitting(project_id)
    except Exception as e:
        logger.error(f"Error running split for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/split/{filename}")
def run_split_single(project_id: str, filename: str):
    """Run split for a single file."""
    try:
        return engine.run_split_single(project_id, filename)
    except Exception as e:
        logger.error(f"Error running split single for {project_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_ocr")
def run_ocr(project_id: str):
    """Run OCR for all jobs in project."""
    try:
        return engine.run_ocr(project_id)
    except Exception as e:
        logger.error(f"Error running OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_llm")
def run_llm(project_id: str):
    """Run LLM for all jobs in project."""
    try:
        return engine.run_llm(project_id)
    except Exception as e:
        logger.error(f"Error running LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_export")
def run_export(project_id: str):
    """Export project to Excel."""
    try:
        return engine.run_excel(project_id)
    except Exception as e:
        logger.error(f"Error exporting excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_archive")
def run_archive(project_id: str):
    """Archive project."""
    try:
        return engine.archive_project(project_id)
    except Exception as e:
        logger.error(f"Error archiving project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/regenerate")
def regenerate_project(project_id: str, excel_path: str = Form(...)):
    """Regenerate project from archived Excel."""
    try:
        return engine.regenerate_project(project_id, excel_path)
    except Exception as e:
        logger.error(f"Error regenerating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
