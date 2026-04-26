# Files Router - 檔案操作端點
import logging
import os
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError
from backend.utils.utils import handle_upload_files

logger = logging.getLogger(__name__)
router = APIRouter()


class SubRect(BaseModel):
    points: List[List[float]]


class ApplyRawResplitRequest(BaseModel):
    sub_rects: List[SubRect]

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


@router.post("/{project_id}/raw_files/{filename}/detect-sub-rects")
async def detect_raw_sub_rects(project_id: str, filename: str, engine: Engine = Depends(get_engine)):
    """Detect potential sub-rectangles for a specific raw file."""
    try:
        rects = await engine.detect_raw_sub_rects(project_id, filename)
        return {
            "status": "ok",
            "filename": filename,
            "rects": rects,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting raw sub-rects for {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/raw_files/{filename}/apply-resplit")
async def apply_raw_resplit(
    project_id: str,
    filename: str,
    request: ApplyRawResplitRequest,
    engine: Engine = Depends(get_engine),
):
    """Apply manual sub-rectangles to a raw image and replace related split jobs."""
    try:
        payload = [rect.model_dump() if hasattr(rect, "model_dump") else rect.dict() for rect in request.sub_rects]
        return await engine.apply_raw_resplit(project_id, filename, payload)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying raw resplit for {filename}: {e}")
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
        preview = await engine.cache_service.ensure_preview_cache(
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
    raw_dir = root / "原始輸入"
    token = Path(filename).name
    image_path = raw_dir / token
    if not image_path.exists() and raw_dir.exists():
        stem = Path(token).stem
        candidates = [
            item
            for item in raw_dir.iterdir()
            if item.is_file() and (
                item.name == token
                or item.stem == token
                or item.stem == stem
            )
        ]
        if candidates:
            candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            image_path = candidates[0]

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        preview = await engine.cache_service.ensure_preview_cache(
            project_id, str(image_path), max_width=800,
        )
        if preview and os.path.exists(preview["path"]):
            return FileResponse(path=preview["path"], media_type=preview["media_type"])
    except Exception as e:
        logger.warning(f"Preview cache generation failed for {filename}: {e}")

    return FileResponse(path=str(image_path))

