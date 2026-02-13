# Correction Router - 人工修正端點
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


class ManualTextRequest(BaseModel):
    manual_text: str


@router.put("/{project_id}/jobs/{job_id}/manual")
def save_manual_text(project_id: str, job_id: str, request: ManualTextRequest, engine: Engine = Depends(get_engine)):
    """Save user's manual correction text."""
    try:
        job_repo = engine.get_job_repo(project_id)
        success = job_repo.save_manual_json(job_id, {"manual_text": request.manual_text})
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"status": "saved", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving manual text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/regenerate_from_manual")
def regenerate_from_manual(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Regenerate VLM result using manual text - DEPRECATED in VLM-First."""
    raise HTTPException(status_code=501, detail="Regeneration from manual text is not supported in VLM-First architecture. Use re-processing instead.")
