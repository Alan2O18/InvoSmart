# backend/routers/pdf.py
import os
import shutil
import tempfile
import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Depends
from fastapi.responses import FileResponse
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/{project_id}/upload_pdf")
async def upload_pdf(
    project_id: str,
    files: List[UploadFile] = File(...),
    engine: Engine = Depends(get_engine)
):
    """上傳 PDF 檔案，將會抽取第一頁轉成圖片進行 VLM 辨識"""
    logger.info(f"Received PDF upload request for {project_id}, files={len(files)}")
    temp_dir = tempfile.mkdtemp()
    saved_file_paths = []
    try:
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
                
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_file_paths.append(file_path)
        
        logger.info(f"Calling engine.add_pdf_files with {saved_file_paths}")
        # this will enqueue the jobs too
        return await engine.add_pdf_files(project_id, saved_file_paths)
    except Exception as e:
        logger.error(f"Error in upload_pdf: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"PDF Upload failed: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@router.post("/{project_id}/{job_id}/commands")
async def execute_pdf_commands(
    project_id: str,
    job_id: str,
    commands: dict = Body(...),
    engine: Engine = Depends(get_engine)
):
    """
    前端傳送編輯指令 (頁面重排、圖片印章座標) 交由後端非同步重組與壓縮 PDF
    commands = {
        "page_order": [0, 1],
        "stamps": [...],
        "texts": [...]
    }
    """
    logger.info(f"Received PDF commands for {project_id}/{job_id}: {commands}")
    try:
        # Enqueue the job for the dedicated PDF worker
        await engine.enqueue_pdf_job(project_id, job_id, commands)
        return {"status": "processing", "job_id": job_id}
    except Exception as e:
        logger.error(f"Error executing pdf commands: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue PDF commands: {str(e)}")

@router.get("/{project_id}/{job_id}/download")
async def download_processed_pdf(
    project_id: str,
    job_id: str,
    engine: Engine = Depends(get_engine)
):
    """下載處理/壓縮完畢後的 PDF 檔"""
    try:
        job_repo = engine.get_job_repo(project_id)
        job = await job_repo.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        compressed_pdf_path = job.get("compressed_pdf_path")
        source_pdf_path = job.get("source_pdf_path")
        
        # 優先回傳處理後的，若尚未處理則回傳原始版本
        if compressed_pdf_path and os.path.exists(compressed_pdf_path):
            return FileResponse(
                path=compressed_pdf_path, 
                filename=os.path.basename(compressed_pdf_path),
                media_type="application/pdf"
            )
        elif source_pdf_path and os.path.exists(source_pdf_path):
            return FileResponse(
                path=source_pdf_path,
                filename=os.path.basename(source_pdf_path),
                media_type="application/pdf"
            )
        else:
            raise HTTPException(status_code=404, detail="PDF files not found on disk")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading PDF for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download PDF: {str(e)}")
