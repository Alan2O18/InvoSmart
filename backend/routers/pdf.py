# backend/routers/pdf.py
import os
import shutil
import tempfile
import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File, Body, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()

from backend.utils.utils import handle_upload_files

@router.post("/{project_id}/pdf")
async def upload_pdf(
    project_id: str,
    files: List[UploadFile] = File(...),
    engine: Engine = Depends(get_engine)
):
    """
    上傳 PDF 檔案並非同步執行轉換與辨識
    
    1. 接收 PDF 檔案
    2. 轉換為圖片
    3. 加入 Project
    4. 背景執行 VLM 辨識
    """
    try:
        async with handle_upload_files(files) as saved_file_paths:
            pdf_paths = [fp for fp in saved_file_paths if fp.lower().endswith('.pdf')]
            
            if not pdf_paths:
                raise ValueError("未找到有效的 PDF 檔案")
                
            return await engine.file_ops.add_pdf_files(project_id, pdf_paths)
            
    except Exception as e:
        logger.error(f"Error processing PDF upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
