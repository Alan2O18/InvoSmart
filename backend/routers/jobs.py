# Jobs Router - Job 管理端點 (VLM-First)
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{project_id}/jobs")
async def get_project_jobs(project_id: str, engine: Engine = Depends(get_engine)):
    """Get all jobs for a project (from global.db)."""
    try:
        await engine.project_repo.sync_status_to_db(project_id)
        job_repo = engine.get_job_repo(project_id)
        return await job_repo.list_jobs()
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/jobs/{job_id}/details")
async def get_job_details(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Get full job details for the editor view."""
    try:
        tm = engine.get_job_repo(project_id)
        details = await tm.get_job_details(job_id)
        if not details:
            raise HTTPException(status_code=404, detail="Job not found")
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/jobs/{job_id}")
async def delete_job(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Delete a job."""
    try:
        return await engine.delete_job(project_id, job_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/process")
async def run_single_processing(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Run VLM processing for a single job (VLM-First)."""
    try:
        return await engine.run_single_processing(project_id, job_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error running single processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from backend.routers.suggestions import get_suggestion_repo, SuggestionRepository

class ManualJsonRequest(BaseModel):
    json_data: dict


class SubRect(BaseModel):
    points: List[List[float]]


class ApplyResplitRequest(BaseModel):
    sub_rects: List[SubRect]


@router.put("/{project_id}/jobs/{job_id}/json")
async def save_manual_json(
    project_id: str, 
    job_id: str, 
    request: ManualJsonRequest, 
    engine: Engine = Depends(get_engine),
    suggestion_repo: SuggestionRepository = Depends(get_suggestion_repo)
):
    """Save user's manual JSON edit and extract knowledge into suggestion DB."""
    try:
        success = await engine.save_manual_json(project_id, job_id, request.json_data)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")

        # === 回饋機制：從人工確認的 JSON 萃取知識 ===
        try:
            added = await suggestion_repo.extract_from_manual_json(request.json_data)
            logger.info(f"[FeedbackLoop] 儲存成功，已萃取 {added} 筆建議詞")
        except Exception as fb_err:
            # 回饋失敗不影響主業務
            logger.warning(f"[FeedbackLoop] 建議詞萃取失敗（不影響儲存）: {fb_err}")

        return {"status": "saved", "job_id": job_id}
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving manual JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/detect-sub-rects")
async def detect_sub_rects(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Detect potential sub-rectangles for manual second-stage splitting."""
    try:
        rects = await engine.detect_job_sub_rects(project_id, job_id)
        return {
            "status": "ok",
            "job_id": job_id,
            "rects": rects,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting sub-rects for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/apply-resplit")
async def apply_resplit(
    project_id: str,
    job_id: str,
    request: ApplyResplitRequest,
    engine: Engine = Depends(get_engine),
):
    """Apply manual sub-rectangles and replace the old job with re-split jobs."""
    try:
        payload = [rect.model_dump() if hasattr(rect, "model_dump") else rect.dict() for rect in request.sub_rects]
        return await engine.apply_job_resplit(project_id, job_id, payload)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying resplit for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

