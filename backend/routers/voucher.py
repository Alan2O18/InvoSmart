from __future__ import annotations

import asyncio
import base64
import functools
import inspect
import io
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_engine, get_db
from backend.engine.core import Engine
from backend.engine.voucher_text_config import (
    _CONFIG_PATH as _TEMPLATE_CONFIG_PATH,
    get_full_template_layout,
    get_voucher_text_config_payload,
)
from backend.engine.voucher_generator import VoucherGenerator
from backend.engine.stamp_service import StampService
from backend.models.voucher_payload import VoucherLayoutPayloadDraft, VoucherLayoutPayloadStrict
from backend.engine.image_codec_adapter import ImageCodecAdapter
from backend.repositories.voucher_layout_repo import VoucherLayoutRepository, sanitize_project_id
from backend.repositories.stamp_repository import StampRepository
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


class _TemplateLayoutPayload(BaseModel):
    """Pydantic model for PUT /config/template-layout."""
    version: str | None = None
    font: dict | None = None
    textFields: dict | None = None
    safeZone: dict | None = None
    blockedZones: list | None = None
    preview: dict | None = None


def get_voucher_settings() -> Dict[str, Any]:
    config = load_config()
    merged = dict(DEFAULT_VOUCHER_SETTINGS)
    merged.update(config.get("voucher_settings", {}))
    return merged


def get_layout_repo() -> VoucherLayoutRepository:
    settings = get_voucher_settings()
    return VoucherLayoutRepository(layout_root=settings["layout_root"])


def _parse_amount_from_result(result: dict[str, Any]) -> int | None:
    raw = result.get("total_amount")
    if raw is None:
        summary = result.get("summary") or {}
        raw = summary.get("total")
    if raw is None:
        raw = result.get("total")
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def _parse_date_to_timestamp(raw: str) -> float | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _normalize_date_to_iso(raw: str) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _derive_purpose_from_results(results: list[dict[str, Any]]) -> str:
    descriptions: list[str] = []
    for result in results:
        for item in result.get("items") or []:
            if not isinstance(item, dict):
                continue
            desc = str(item.get("category") or item.get("description") or item.get("name") or "").strip()
            if desc and desc not in descriptions:
                descriptions.append(desc)
    return "、".join(descriptions)


def _resolve_page_fields(page: dict[str, Any], page_results: list[dict[str, Any]]) -> dict[str, Any]:
    fields = dict(page.get("fields") or {})
    fields["receiptCount"] = str(len(page.get("images") or []))

    amounts = [amount for amount in (_parse_amount_from_result(result) for result in page_results) if amount is not None]
    if amounts:
        fields["amount"] = str(sum(amounts))

    dated_values = []
    for result in page_results:
        raw = str(result.get("date") or (result.get("header") or {}).get("date") or "")
        ts = _parse_date_to_timestamp(raw)
        if ts is not None:
            dated_values.append((ts, raw))
    if dated_values:
        dated_values.sort(key=lambda item: item[0])
        normalized = _normalize_date_to_iso(dated_values[0][1])
        if normalized:
            fields["payDate"] = normalized

    if not bool(fields.get("isManuallyEdited")):
        purpose = _derive_purpose_from_results(page_results)
        if purpose:
            fields["purpose"] = purpose

    return fields


# _template_preview_payload removed - delegated to PdfTaskService


def _load_image_bytes(image_path: str, thumb: bool, max_width: int) -> tuple[bytes, str]:
    image = ImageCodecAdapter().read_image_pil(image_path)
    if thumb and image.width > max_width:
        new_height = int((max_width / image.width) * image.height)
        image = image.resize((max_width, max(1, new_height)), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    if thumb:
        image.save(buffer, format="WEBP", quality=85)
        return buffer.getvalue(), "image/webp"
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue(), "image/jpeg"


@router.get("/fonts/kaiu.ttf")
async def get_kaiu_font():
    settings = get_voucher_settings()
    font_path = settings["font_ttf_path"]

    if not os.path.exists(font_path):
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher font not found"})

    return FileResponse(path=font_path, media_type="font/ttf")


@router.get("/text-config")
async def get_voucher_text_config():
    return get_voucher_text_config_payload()


@router.get("/config/template-layout")
async def get_template_layout():
    """Return the full voucher template layout (text field coords + safe zone + blocked zones)."""
    return get_full_template_layout()


@router.put("/config/template-layout")
async def save_template_layout(payload: _TemplateLayoutPayload):
    """Persist template layout changes to JSON config file."""
    config_path = _TEMPLATE_CONFIG_PATH
    await asyncio.to_thread(config_path.parent.mkdir, parents=True, exist_ok=True)

    def _read_json(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload if isinstance(payload, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    current = await asyncio.to_thread(_read_json, config_path)
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    current.update(update)

    await asyncio.to_thread(
        lambda: config_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    )
    return {"status": "saved"}


@router.get("/config/template-preview")
async def get_template_preview(engine: Engine = Depends(get_engine)):
    """Return the voucher template PNG as base64 (lightweight, no project data)."""
    settings = get_voucher_settings()
    template_path = settings["template_pdf_path"]
    if not os.path.exists(template_path):
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher template not found"})
    return await asyncio.to_thread(engine.pdf_task_service.get_template_preview_payload, template_path)


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

    preview_payload = await asyncio.to_thread(engine.pdf_task_service.get_template_preview_payload, template_path)

    metadata = project.get("metadata") or {}
    budget_item = metadata.get("group") or metadata.get("group_name") or ""

    return {
        "templatePng": preview_payload["templatePng"],
        "pageWidth": preview_payload["pageWidth"],
        "pageHeight": preview_payload["pageHeight"],
        "previewPixelWidth": preview_payload["previewPixelWidth"],
        "previewPixelHeight": preview_payload["previewPixelHeight"],
        "projectMeta": {
            "id": project.get("project_id"),
            "name": project.get("name") or project.get("project_id"),
            "createdAt": project.get("created_at"),
            "budgetItem": budget_item,
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
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "detail": "Invoice job not found"})

    image_path = job.get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")

    if thumb:
        try:
            preview = await engine.image_service.ensure_preview_cache(project_id, image_path, max_width=max_width)
            if preview and os.path.exists(preview["path"]):
                return FileResponse(path=preview["path"], media_type=preview["media_type"])
        except Exception as preview_err:  # noqa: BLE001
            logger.warning("Voucher image preview cache fallback triggered: %s", preview_err)

    content, content_type = await asyncio.to_thread(
        _load_image_bytes,
        image_path=image_path,
        thumb=thumb,
        max_width=max_width,
    )
    return Response(content=content, media_type=content_type)


@router.get("/{project_id}/layout")
async def get_layout(project_id: str):
    repo = get_layout_repo()
    return repo.load_layout(project_id)


@router.post("/{project_id}/layout")
async def save_layout(project_id: str, payload: VoucherLayoutPayloadDraft):
    repo = get_layout_repo()
    return repo.save_layout(project_id, payload.model_dump())


@router.post("/{project_id}/generate")
async def generate_voucher_pdf(
    project_id: str,
    payload: VoucherLayoutPayloadStrict,
    engine: Engine = Depends(get_engine),
    db: AsyncSession = Depends(get_db),
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
    job_result_map: Dict[str, Dict[str, Any]] = {}
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
        display_result = await job_repo.get_display_result(job_id)
        job_result_map[job_id] = display_result if isinstance(display_result, dict) else {}

    resolved_pages: List[Dict[str, Any]] = []
    for page in payload.model_dump().get("pages", []):
        page_images = page.get("images") or []
        page_results = [job_result_map.get(image.get("jobId", ""), {}) for image in page_images]
        resolved_fields = _resolve_page_fields(page, page_results)

        payload_fields = page.get("fields") or {}
        if str(payload_fields.get("amount") or "") != str(resolved_fields.get("amount") or ""):
            logger.warning(
                "Voucher amount mismatch (payload->db truth) project=%s page=%s payload=%s resolved=%s",
                project_id,
                page.get("pageIndex"),
                payload_fields.get("amount"),
                resolved_fields.get("amount"),
            )

        resolved_pages.append(
            {
                **page,
                "fields": resolved_fields,
            }
        )

    safe_project_id = sanitize_project_id(project_id)
    output_dir = Path(settings["layout_root"]) / safe_project_id / "outputs"
    await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
    filename = f"voucher_{int(time.time())}.pdf"
    output_path = output_dir / filename

    try:
        # --- 收集印章 (在 generate_from_layout 之前) ---
        stamp_repo = StampRepository(db)
        stamp_service = StampService()
        
        # 所有需要收集的角色
        all_stamp_roles = [
            "handler", "activity_general_affairs", "general_affairs_head",
            "president", "advisor", "club_seal", "fin_original", "fin_audited"
        ]
        
        stamp_paths: Dict[str, str | None] = {}
        for role in all_stamp_roles:
            stamp_image_path = await stamp_service.get_random_stamp_by_role(role, stamp_repo)
            stamp_paths[role] = stamp_image_path
            if stamp_image_path:
                logger.info(f"[Stamps] 角色 '{role}' 已找到印章: {stamp_image_path}")
            else:
                logger.warning(f"[Stamps] 角色 '{role}' 無可用印章")
        
        # 特殊處理: 若 handler 無印章，回退到 president 的章
        if not stamp_paths.get("handler") and stamp_paths.get("president"):
            logger.info("[Stamps] handler 無印章，使用 president 的章替代")
            stamp_paths["handler"] = stamp_paths["president"]
        
        generator = VoucherGenerator(template_path=template_path, font_path=settings.get("font_ttf_path", ""))
        await asyncio.to_thread(
            generator.generate_from_layout,
            resolved_pages,
            job_image_map=job_image_map,
            output_path=str(output_path),
            stamps=stamp_paths,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "VALIDATION_ERROR",
                "detail": str(exc),
            },
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Voucher generation failed")
        raise HTTPException(status_code=500, detail={"error": "INTERNAL_ERROR", "detail": "Voucher generation failed"})

    return FileResponse(path=output_path, filename=filename, media_type="application/pdf")
