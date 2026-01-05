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
def regenerate_from_manual(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Regenerate LLM result using manual OCR text."""
    try:
        tm = engine.get_task_manager(project_id)
        
        # 使用優先級邏輯獲取 OCR 文字 (manual > ocr_result)
        manual_text = tm.get_ocr_for_regenerate(job_id)
        if not manual_text:
            raise HTTPException(status_code=400, detail="No OCR text available for regeneration")
        
        llm_result = engine.llm_handler.structure_with_llm(manual_text)
        tm.complete_llm(job_id, llm_result, mark_final=True)
        
        return {"status": "regenerated", "job_id": job_id, "llm_result": llm_result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating from manual: {e}")
        raise HTTPException(status_code=500, detail=str(e))
