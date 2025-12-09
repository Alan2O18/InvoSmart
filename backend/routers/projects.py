import shutil
import os
import tempfile
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from backend.engine import engine

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

class ProjectCreate(BaseModel):
    project_id: str
    metadata: Optional[dict] = None

@router.get("/")
def list_projects():
    return engine.project_manager.list_projects()

@router.post("/")
def create_project(
    project_id: str = Form(...),
    metadata: str = Form(None), # JSON string
    files: List[UploadFile] = File(...)
):
    # Create a temp directory to store uploaded files
    temp_dir = tempfile.mkdtemp()
    saved_file_paths = []
    
    try:
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_file_paths.append(file_path)
        
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except:
                pass

        # Create the project (without starting pipeline)
        result = engine.create_project(project_id, saved_file_paths, metadata=meta_dict)
        return result
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp dir
        shutil.rmtree(temp_dir, ignore_errors=True)

@router.put("/{project_id}")
def update_project(project_id: str, metadata: dict):
    try:
        return engine.project_manager.update_metadata(project_id, metadata)
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}")
def delete_project(project_id: str):
    try:
        return engine.project_manager.delete_project(project_id)
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}")
def get_project_status(project_id: str):
    try:
        return engine.project_manager.get_project_status(project_id)
    except Exception as e:
        logger.error(f"Error getting status for {project_id}: {e}")
        raise HTTPException(status_code=404, detail="Project not found")

@router.post("/{project_id}/add_files")
def add_files(
    project_id: str,
    type: str = Form(...), # 'raw' or 'split'
    files: List[UploadFile] = File(...)
):
    logger.info(f"Received add_files request for {project_id}, type={type}, files={len(files)}")
    temp_dir = tempfile.mkdtemp()
    saved_file_paths = []
    try:
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            logger.info(f"Saving temp file to {file_path}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_file_paths.append(file_path)
        
        logger.info(f"Calling engine.add_project_files with {saved_file_paths}")
        return engine.add_project_files(project_id, saved_file_paths, type=type)
    except Exception as e:
        logger.error(f"Error in add_files: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@router.post("/{project_id}/rotate/{filename}")
def rotate_image(project_id: str, filename: str, angle: int = 90):
    try:
        return engine.rotate_image(project_id, filename, angle)
    except Exception as e:
        logger.error(f"Error rotating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/run_split")
def run_split(project_id: str):
    try:
        return engine.run_splitting(project_id)
    except Exception as e:
        logger.error(f"Error running split for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/split/{filename}")
def run_split_single(project_id: str, filename: str):
    try:
        return engine.run_split_single(project_id, filename)
    except Exception as e:
        logger.error(f"Error running split single for {project_id}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/raw_files")
def get_raw_files(project_id: str):
    try:
        return engine.get_raw_files(project_id)
    except Exception as e:
        logger.error(f"Error getting raw files for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/run_ocr")
def run_ocr(project_id: str):
    try:
        return engine.run_ocr(project_id)
    except Exception as e:
        logger.error(f"Error running OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/run_llm")
def run_llm(project_id: str):
    try:
        return engine.run_llm(project_id)
    except Exception as e:
        logger.error(f"Error running LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/run_export")
def run_export(project_id: str):
    try:
        return engine.run_excel(project_id)
    except Exception as e:
        logger.error(f"Error exporting excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/run_archive")
def run_archive(project_id: str):
    try:
        return engine.archive_project(project_id)
    except Exception as e:
        logger.error(f"Error archiving project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/jobs/{job_id}/ocr")
def run_single_ocr(project_id: str, job_id: str):
    try:
        return engine.run_single_ocr(project_id, job_id)
    except Exception as e:
        logger.error(f"Error running single OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/jobs/{job_id}/llm")
def run_single_llm(project_id: str, job_id: str):
    try:
        return engine.run_single_llm(project_id, job_id)
    except Exception as e:
        logger.error(f"Error running single LLM: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}/jobs/{job_id}")
def delete_job(project_id: str, job_id: str):
    try:
        return engine.delete_job(project_id, job_id)
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}/raw_files/{filename}")
def delete_raw_file(project_id: str, filename: str):
    try:
        return engine.delete_raw_file(project_id, filename)
    except Exception as e:
        logger.error(f"Error deleting raw file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/activity_info")
def update_activity_info(project_id: str, info: dict):
    try:
        return engine.project_manager.update_activity_info(project_id, info)
    except Exception as e:
        logger.error(f"Error updating activity info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/regenerate")
def regenerate_project(project_id: str, excel_path: str = Form(...)):
    try:
        return engine.regenerate_project(project_id, excel_path)
    except Exception as e:
        logger.error(f"Error regenerating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Group Endpoints ---

@router.get("/groups/list") # Changed to avoid conflict with project_id if root level
def list_groups():
    try:
        return engine.project_manager.list_groups()
    except Exception as e:
        logger.error(f"Error listing groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class GroupCreate(BaseModel):
    group_name: str
    leader_name: str

@router.post("/groups")
def upsert_group(group: GroupCreate):
    try:
        engine.project_manager.upsert_group(group.group_name, group.leader_name)
        return {"status": "success", "group": group.model_dump()}
    except Exception as e:
        logger.error(f"Error upserting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/groups/{group_name}")
def delete_group(group_name: str):
    try:
        engine.project_manager.delete_group(group_name)
        return {"status": "deleted", "group_name": group_name}
    except Exception as e:
        logger.error(f"Error deleting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/jobs")
def get_project_jobs(project_id: str):
    # We need to query jobs.db for this project
    # ProjectManager doesn't expose this directly, but we can access the db
    try:
        root = engine.project_manager._project_root(project_id)
        db_path = root / "jobs.db"
        if not db_path.exists():
             return []
        
        import sqlite3
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

# --- Manual Correction Endpoints ---

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

