# Correction Router - 人工修正端點
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError

logger = logging.getLogger(__name__)
router = APIRouter()


class ManualTextRequest(BaseModel):
    manual_text: str


@router.put("/{project_id}/jobs/{job_id}/manual")
async def save_manual_text(project_id: str, job_id: str, request: ManualTextRequest, engine: Engine = Depends(get_engine)):
    """Save user's manual correction text."""
    try:
        success = await engine.save_manual_json(project_id, job_id, {"manual_text": request.manual_text})
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"status": "saved", "job_id": job_id}
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving manual text: {e}")
        raise HTTPException(status_code=500, detail=str(e))

