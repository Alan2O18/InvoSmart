# Exports Router - 報表匯出與封存端點
"""
Exports Router

Handles report generation and project archiving:
- Excel export
- Word export (uses normalized template path)
- Project archive
"""
import os
import pathlib
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()

# Canonical template location (normalised from dev_data in P4)
_ASSETS_TEMPLATES = pathlib.Path(__file__).parent.parent / "assets" / "templates"


@router.post("/{project_id}/run_export")
async def run_export(project_id: str, engine: Engine = Depends(get_engine)):
    """Export project to Excel."""
    try:
        return await engine.run_excel(project_id)
    except Exception as e:
        logger.error(f"Error exporting excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_word_export")
async def run_word_export(project_id: str, engine: Engine = Depends(get_engine)):
    """Export project to Word report template."""
    try:
        template_path = _ASSETS_TEMPLATES / "報表範本.docx"

        if not template_path.exists():
            raise HTTPException(status_code=500, detail="Word template not found")

        out_path = await engine.export_handler.run_word(project_id, str(template_path))

        if not os.path.exists(out_path):
            raise HTTPException(status_code=500, detail="Generated Word file not found")

        filename = os.path.basename(out_path)
        return FileResponse(
            path=out_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting word: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/run_archive")
async def run_archive(project_id: str, engine: Engine = Depends(get_engine)):
    """Archive project."""
    try:
        return await engine.archive_project(project_id)
    except Exception as e:
        logger.error(f"Error archiving project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
