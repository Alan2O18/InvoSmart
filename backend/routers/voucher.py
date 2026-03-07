from __future__ import annotations

import base64
import functools
import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import fitz
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from PIL import Image

from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.engine.voucher_generator import VoucherGenerator
from backend.models.voucher_payload import VoucherLayoutPayloadDraft, VoucherLayoutPayloadStrict
from backend.repositories.voucher_layout_repo import VoucherLayoutRepository, sanitize_project_id
from backend.utils.config import load_config

logger = logging.getLogger(__name__)

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VOUCHER_SETTINGS = {
    "template_pdf_path": str(PROJECT_ROOT / "backend" / "assets" / "templates" / "憑證黏貼用紙.pdf"),
    "font_ttf_path": str(PROJECT_ROOT / "backend" / "assets" / "fonts" / "kaiu.ttf"),
    "layout_root": str(PROJECT_ROOT / "backend" / "data" / "projects"),
    "max_pages": 10,
    "autosave_interval_sec": 30,
    "thumb_max_width": 800,
}


def get_voucher_settings() -> Dict[str, Any]:
    config = load_config()
    merged = dict(DEFAULT_VOUCHER_SETTINGS)
    merged.update(config.get("voucher_settings", {}))
    return merged


def get_layout_repo() -> VoucherLayoutRepository:
    settings = get_voucher_settings()
    return VoucherLayoutRepository(layout_root=settings["layout_root"])


@functools.lru_cache(maxsize=8)
def _template_png_base64(template_path: str, mtime: float) -> str:
    with fitz.open(template_path) as doc:
        page = doc[0]
        pix = page.get_pixmap(dpi=144)
        return base64.b64encode(pix.tobytes("png")).decode("utf-8")


def _load_image_bytes(image_path: str, thumb: bool, max_width: int) -> tuple[bytes, str]:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        if thumb and image.width > max_width:
            new_height = int((max_width / image.width) * image.height)
            image = image.resize((max_width, max(1, new_height)), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        if thumb:
            image.save(buffer, format="WEBP", quality=85)
            return buffer.getvalue(), "image/webp"
        image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue(), "image/jpeg"


@router.get("/{project_id}/template")
async def get_template(project_id: str, engine: Engine = Depends(get_engine)):
    settings = get_voucher_settings()
    template_path = settings["template_pdf_path"]

    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher template PDF not found"})

    project = await engine.project_repo.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job_repo = engine.get_job_repo(project_id)
    jobs = await job_repo.list_jobs(status="done")

    invoices: List[Dict[str, Any]] = []
    for job in jobs:
        job_id = job["job_id"]
        result = await job_repo.get_display_result(job_id) or {}
        invoices.append(
            {
                "jobId": job_id,
                "imageUrl": f"/api/voucher/{project_id}/image/{job_id}?thumb=true",
                "status": "done",
                "result": result,
            }
        )

    template_png = _template_png_base64(template_path, os.path.getmtime(template_path))

    return {
        "templatePng": template_png,
        "projectMeta": {
            "id": project.get("project_id"),
            "name": project.get("name") or project.get("project_id"),
            "createdAt": project.get("created_at"),
        },
        "invoices": invoices,
    }


@router.get("/{project_id}/image/{job_id}")
async def get_voucher_image(
    project_id: str,
    job_id: str,
    thumb: bool = Query(default=False),
    engine: Engine = Depends(get_engine),
):
    settings = get_voucher_settings()
    max_width = int(settings.get("thumb_max_width", 800))

    job_repo = engine.get_job_repo(project_id)
    job = await job_repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "detail": "Unauthorized invoice access"})

    image_path = job.get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    content, content_type = _load_image_bytes(image_path=image_path, thumb=thumb, max_width=max_width)
    return Response(content=content, media_type=content_type)


@router.get("/fonts/kaiu.ttf")
async def get_kaiu_font():
    settings = get_voucher_settings()
    font_path = settings["font_ttf_path"]

    if not os.path.exists(font_path):
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher font not found"})

    return FileResponse(path=font_path, media_type="font/ttf")


@router.get("/{project_id}/layout")
async def get_layout(project_id: str):
    repo = get_layout_repo()
    return repo.load_layout(project_id)


@router.post("/{project_id}/layout")
async def save_layout(project_id: str, payload: VoucherLayoutPayloadDraft):
    repo = get_layout_repo()
    return repo.save_layout(project_id, payload.model_dump())

@router.get("/fonts/kaiu.ttf")
async def get_kaiu_font():
    settings = get_voucher_settings()
    font_path = settings["font_ttf_path"]
    if not os.path.exists(font_path):
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Font file not found"})
    return Response(content=open(font_path, "rb").read(), media_type="font/ttf")


@router.post("/{project_id}/generate")
async def generate_voucher_pdf(
    project_id: str,
    payload: VoucherLayoutPayloadStrict,
    engine: Engine = Depends(get_engine),
):
    settings = get_voucher_settings()
    template_path = settings["template_pdf_path"]

    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher generation failed"})

    job_repo = engine.get_job_repo(project_id)
    all_job_ids = {
        image.jobId
        for page in payload.pages
        for image in page.images
    }

    job_image_map: Dict[str, str] = {}
    for job_id in all_job_ids:
        job = await job_repo.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "detail": f"Contains unauthorized invoice jobId: {job_id}",
                },
            )
        job_image_map[job_id] = job.get("image_path", "")

    safe_project_id = sanitize_project_id(project_id)
    output_dir = Path(settings["layout_root"]) / safe_project_id / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"voucher_{int(time.time())}.pdf"
    output_path = output_dir / filename

    try:
        generator = VoucherGenerator(template_path=template_path, font_path=settings.get("font_ttf_path", ""))
        generator.generate_from_layout(payload.model_dump().get("pages", []), job_image_map=job_image_map, output_path=str(output_path))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Voucher generation failed")
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher generation failed"})

    return FileResponse(path=output_path, filename=filename, media_type="application/pdf")
