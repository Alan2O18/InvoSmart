# Files Router - 檔案操作端點
import logging
import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import FileResponse
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError
from backend.utils.utils import handle_upload_files

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/{project_id}/add_files")
async def add_files(
    project_id: str,
    type: str = Form(...),
    files: List[UploadFile] = File(...),
    engine: Engine = Depends(get_engine)
):
    """Add files to project."""
    logger.info(f"Received add_files request for {project_id}, type={type}, files={len(files)}")
    try:
        async with handle_upload_files(files) as saved_file_paths:
            logger.info(f"Calling engine.add_project_files with {saved_file_paths}")
            return await engine.add_project_files(project_id, saved_file_paths, type=type)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error in add_files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/{project_id}/rotate/{filename}")
async def rotate_image(project_id: str, filename: str, angle: int = 90, engine: Engine = Depends(get_engine)):
    """Rotate an image by specified angle."""
    try:
        return await engine.rotate_image(project_id, filename, angle)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error rotating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/raw_files")
async def get_raw_files(project_id: str, engine: Engine = Depends(get_engine)):
    """Get list of raw files in project."""
    try:
        return await engine.get_raw_files(project_id)
    except Exception as e:
        logger.error(f"Error getting raw files for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}/raw_files/{filename}")
async def delete_raw_file(project_id: str, filename: str, engine: Engine = Depends(get_engine)):
    """Delete a raw file from project."""
    try:
        return await engine.delete_raw_file(project_id, filename)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting raw file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/preview/split/{filename}")
async def get_split_preview(
    project_id: str,
    filename: str,
    engine: Engine = Depends(get_engine),
):
    """Serve a browser-compatible preview (AVIF/WebP/JPEG) of a split image."""
    root = engine.project_repo._project_root(project_id)
    image_path = root / "分割發票" / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        preview = await engine.file_ops.ensure_preview_cache(
            project_id, str(image_path), max_width=800,
        )
        if preview and os.path.exists(preview["path"]):
            return FileResponse(path=preview["path"], media_type=preview["media_type"])
    except Exception as e:
        logger.warning(f"Preview cache generation failed for {filename}: {e}")

    # Fallback: serve original file (works for jpg/png/webp, not jxl)
    return FileResponse(path=str(image_path))


@router.get("/{project_id}/preview/raw/{filename}")
async def get_raw_preview(
    project_id: str,
    filename: str,
    engine: Engine = Depends(get_engine),
):
    """Serve a browser-compatible preview of a raw input image."""
    root = engine.project_repo._project_root(project_id)
    image_path = root / "原始輸入" / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        preview = await engine.file_ops.ensure_preview_cache(
            project_id, str(image_path), max_width=800,
        )
        if preview and os.path.exists(preview["path"]):
            return FileResponse(path=preview["path"], media_type=preview["media_type"])
    except Exception as e:
        logger.warning(f"Preview cache generation failed for {filename}: {e}")

    return FileResponse(path=str(image_path))

