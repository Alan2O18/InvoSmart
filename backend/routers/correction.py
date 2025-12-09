# Correction Router - 人工修正端點
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.engine import engine

logger = logging.getLogger(__name__)
router = APIRouter()


class ManualTextRequest(BaseModel):
    manual_text: str


@router.put("/{project_id}/jobs/{job_id}/manual")
def save_manual_text(project_id: str, job_id: str, request: ManualTextRequest):
    """Save user's manual correction text."""
    try:
        tm = engine.get_task_manager(project_id)
        success = tm.save_manual_text(job_id, request.manual_text)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"status": "saved", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving manual text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/regenerate_from_manual")
def regenerate_from_manual(project_id: str, job_id: str):
    """Regenerate LLM result using manual OCR text."""
    try:
        tm = engine.get_task_manager(project_id)
        details = tm.get_job_details(job_id)
        if not details:
            raise HTTPException(status_code=404, detail="Job not found")
        
        manual_text = details.get("manual_ocr_text")
        if not manual_text:
            raise HTTPException(status_code=400, detail="No manual text to process")
        
        # Call LLM handler directly with manual text
        llm_result = engine.llm_handler.structure_with_llm(manual_text)
        
        # Save the new LLM result
        tm.complete_llm(job_id, llm_result, mark_final=True)
        
        return {"status": "regenerated", "job_id": job_id, "llm_result": llm_result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating from manual: {e}")
        raise HTTPException(status_code=500, detail=str(e))
