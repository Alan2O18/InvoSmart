# Jobs Router - Job 管理端點 (VLM-First)
import logging
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{project_id}/jobs")
def get_project_jobs(project_id: str, engine: Engine = Depends(get_engine)):
    """Get all jobs for a project (from global.db)."""
    try:
        engine.project_repo.sync_status_to_db(project_id)
        job_repo = engine.get_job_repo(project_id)
        return job_repo.list_jobs()
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/jobs/{job_id}/details")
def get_job_details(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Get full job details for the editor view."""
    try:
        tm = engine.get_job_repo(project_id)
        details = tm.get_job_details(job_id)
        if not details:
            raise HTTPException(status_code=404, detail="Job not found")
        return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/jobs/{job_id}")
def delete_job(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Delete a job."""
    try:
        return engine.delete_job(project_id, job_id)
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/process")
def run_single_processing(project_id: str, job_id: str, engine: Engine = Depends(get_engine)):
    """Run VLM processing for a single job (VLM-First)."""
    try:
        return engine.run_single_processing(project_id, job_id)
    except Exception as e:
        logger.error(f"Error running single processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from pydantic import BaseModel

class ManualJsonRequest(BaseModel):
    json_data: dict


@router.put("/{project_id}/jobs/{job_id}/json")
def save_manual_json(project_id: str, job_id: str, request: ManualJsonRequest, engine: Engine = Depends(get_engine)):
    """Save user's manual JSON edit and extract knowledge into suggestion DB."""
    try:
        tm = engine.get_job_repo(project_id)
        success = tm.save_manual_json(job_id, request.json_data)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")

        # === 回饋機制：從人工確認的 JSON 萃取知識 ===
        try:
            from backend.repositories.suggestion_repository import SuggestionRepository
            suggestion_repo = SuggestionRepository(db_path=engine.global_db_path)
            added = suggestion_repo.extract_from_manual_json(request.json_data)
            logger.info(f"[FeedbackLoop] 儲存成功，已萃取 {added} 筆建議詞")
        except Exception as fb_err:
            # 回饋失敗不影響主業務
            logger.warning(f"[FeedbackLoop] 建議詞萃取失敗（不影響儲存）: {fb_err}")

        return {"status": "saved", "job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving manual JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))

