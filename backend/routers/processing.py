# Processing Router - 影像收錄與 AI 辨識管線端點
"""
Processing Router

Handles pipeline operations:
- Split (image splitting)
- Processing (VLM recognition)
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{project_id}/run_split")
async def run_split(project_id: str, engine: Engine = Depends(get_engine)):
    """Run split for all raw files in project."""
    try:
        return await engine.run_splitting(project_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error running split for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/split/{filename}")
async def run_split_single(project_id: str, filename: str, engine: Engine = Depends(get_engine)):
    """Run split for a single file."""
    try:
        return await engine.run_split_single(project_id, filename)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error running split single for {project_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_processing")
async def run_processing(project_id: str, engine: Engine = Depends(get_engine)):
    """Run VLM processing for all jobs in project (VLM-First)."""
    try:
        return await engine.run_processing(project_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error running processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
