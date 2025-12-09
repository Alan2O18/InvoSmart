# Jobs Router - Job 管理端點
import logging
import sqlite3
from fastapi import APIRouter, HTTPException
from backend.engine import engine

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{project_id}/jobs")
def get_project_jobs(project_id: str):
    """Get all jobs for a project."""
    try:
        root = engine.project_manager._project_root(project_id)
        db_path = root / "jobs.db"
        if not db_path.exists():
            return []
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs ORDER BY created_at")
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/jobs/{job_id}/details")
def get_job_details(project_id: str, job_id: str):
    """Get full job details for the editor view."""
    try:
        tm = engine.get_task_manager(project_id)
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
def delete_job(project_id: str, job_id: str):
    """Delete a job."""
    try:
        return engine.delete_job(project_id, job_id)
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/ocr")
def run_single_ocr(project_id: str, job_id: str):
    """Run OCR for a single job."""
    try:
        return engine.run_single_ocr(project_id, job_id)
    except Exception as e:
        logger.error(f"Error running single OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/jobs/{job_id}/llm")
def run_single_llm(project_id: str, job_id: str):
    """Run LLM for a single job."""
    try:
        return engine.run_single_llm(project_id, job_id)
    except Exception as e:
        logger.error(f"Error running single LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
