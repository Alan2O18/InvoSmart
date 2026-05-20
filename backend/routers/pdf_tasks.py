from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

import fitz  # PyMuPDF
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.database.models import Person
from backend.repositories.person_repository import PersonRepository
from backend.repositories.stamp_repository import StampRepository
from backend.utils.stamp_ops import get_rotated_stamp_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PDF_TASKS_ROOT = PROJECT_ROOT / "backend" / "data" / "pdf_tasks"
STAMP_TEMPLATES_ROOT = PROJECT_ROOT / "backend" / "data" / "stamp_templates"
PDF_TASKS_ROOT.mkdir(parents=True, exist_ok=True)
STAMP_TEMPLATES_ROOT.mkdir(parents=True, exist_ok=True)


class PdfTaskUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    template_id: str | None = None
    notes: str | None = None


class StampTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    active: bool = True
    positions: dict[str, dict[str, float]] = Field(default_factory=dict)


class StampTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    positions: dict[str, dict[str, float]] | None = None


class ApplyStampPayload(BaseModel):
    owner_id: int | None = None
    role: str | None = None
    template_id: str | None = None
    mode: Literal["single", "full"] = "single"
    page_index: int = 0


class PageOperationsPayload(BaseModel):
    operation: Literal["delete", "reorder", "add"]
    page_indices: list[int] = Field(default_factory=list)
    page_order: list[int] | None = None
    insert_count: int = 1


def _task_dir(task_id: str) -> Path:
    return PDF_TASKS_ROOT / task_id


def _task_meta_path(task_id: str) -> Path:
    return _task_dir(task_id) / "task.json"


def _task_pdf_path(task_id: str) -> Path:
    return _task_dir(task_id) / "working.pdf"


def _template_dir(template_id: str) -> Path:
    return STAMP_TEMPLATES_ROOT / template_id


def _template_meta_path(template_id: str) -> Path:
    return _template_dir(template_id) / "template.json"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_task(task_id: str) -> dict:
    meta = _read_json(_task_meta_path(task_id))
    if not meta:
        raise HTTPException(status_code=404, detail="PDF task not found")
    pdf_path = _task_pdf_path(task_id)
    if pdf_path.exists():
        try:
            with fitz.open(pdf_path) as doc:
                meta["page_count"] = doc.page_count
        except Exception:  # noqa: BLE001
            meta.setdefault("page_count", 0)
    meta["has_file"] = pdf_path.exists()
    meta["file_url"] = f"/api/pdf-tasks/{task_id}/file"
    return meta


def _load_template(template_id: str) -> dict:
    meta = _read_json(_template_meta_path(template_id))
    if not meta:
        raise HTTPException(status_code=404, detail="Stamp template not found")
    meta["id"] = template_id
    return meta


def _serialize_task(meta: dict) -> dict:
    return {
        "id": meta.get("id"),
        "title": meta.get("title") or meta.get("filename") or meta.get("id"),
        "filename": meta.get("filename"),
        "status": meta.get("status") or "uploaded",
        "notes": meta.get("notes"),
        "template_id": meta.get("template_id"),
        "page_count": meta.get("page_count") or 0,
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "file_url": meta.get("file_url"),
        "has_file": meta.get("has_file", False),
    }


def _serialize_template(meta: dict) -> dict:
    return {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "description": meta.get("description"),
        "active": meta.get("active", True),
        "positions": meta.get("positions") or {},
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
    }


def _list_task_ids() -> list[str]:
    if not PDF_TASKS_ROOT.exists():
        return []
    return sorted(
        [child.name for child in PDF_TASKS_ROOT.iterdir() if child.is_dir()],
        key=lambda task_id: _read_json(_task_meta_path(task_id)).get("updated_at", 0),
        reverse=True,
    )


def _list_template_ids() -> list[str]:
    if not STAMP_TEMPLATES_ROOT.exists():
        return []
    return sorted(
        [child.name for child in STAMP_TEMPLATES_ROOT.iterdir() if child.is_dir()],
        key=lambda template_id: _read_json(_template_meta_path(template_id)).get("updated_at", 0),
        reverse=True,
    )


def _resolve_stamp_image_path(stamp: dict) -> Path:
    image_path = Path(str(stamp.get("image_path") or ""))
    if not image_path:
        raise HTTPException(status_code=404, detail="Stamp image path missing")
    return image_path if image_path.is_absolute() else PROJECT_ROOT / image_path


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


def _pick_stamp_by_owner(stamps_repo: StampRepository, owner_id: int) -> dict:
    return asyncio_run_coroutine(stamps_repo.list_stamps_by_owner(owner_id))


async def asyncio_run_coroutine(coro):
    return await coro


async def _get_stamp_image_path(
    db: AsyncSession,
    owner_id: int | None,
    role: str | None,
) -> Path:
    stamp_repo = StampRepository(db)
    stamp_rows: list[dict] = []
    if owner_id is not None:
        stamp_rows = await stamp_repo.list_stamps_by_owner(owner_id)
    elif role:
        stamp_rows = await stamp_repo.list_stamps_by_role(role)

    if not stamp_rows:
        raise HTTPException(status_code=404, detail="No stamp found for the given owner/role")

    stamp_path = _resolve_stamp_image_path(stamp_rows[0])
    if not stamp_path.exists():
        raise HTTPException(status_code=404, detail="Stamp file missing on disk")
    return stamp_path


async def _open_pdf(task_id: str) -> fitz.Document:
    pdf_path = _task_pdf_path(task_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    try:
        return fitz.open(pdf_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to open PDF: {exc}") from exc


@router.get("/pdf-tasks")
async def list_pdf_tasks() -> list[dict]:
    return [_serialize_task(_load_task(task_id)) for task_id in _list_task_ids()]


@router.post("/pdf-tasks")
async def create_pdf_task(
    file: UploadFile = File(...),
    title: str = Form(""),
):
    task_id = uuid4().hex
    task_dir = _task_dir(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.pdf").name
    pdf_path = _task_pdf_path(task_id)
    content = await file.read()
    pdf_path.write_bytes(content)

    page_count = 0
    try:
        with fitz.open(stream=content, filetype="pdf") as doc:
            page_count = doc.page_count
    except Exception:  # noqa: BLE001
        page_count = 0

    now = time.time()
    meta = {
        "id": task_id,
        "title": title.strip() or filename,
        "filename": filename,
        "status": "uploaded",
        "notes": "",
        "template_id": None,
        "page_count": page_count,
        "created_at": now,
        "updated_at": now,
    }
    _write_json(_task_meta_path(task_id), meta)
    return _serialize_task(_load_task(task_id))


@router.get("/pdf-tasks/{task_id}")
async def get_pdf_task(task_id: str) -> dict:
    return _serialize_task(_load_task(task_id))


@router.get("/pdf-tasks/{task_id}/file")
async def get_pdf_task_file(task_id: str):
    pdf_path = _task_pdf_path(task_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="inline",
    )


@router.put("/pdf-tasks/{task_id}")
async def update_pdf_task(task_id: str, payload: PdfTaskUpdate):
    meta = _load_task(task_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        meta[key] = value
    meta["updated_at"] = time.time()
    _write_json(_task_meta_path(task_id), meta)
    return _serialize_task(_load_task(task_id))


@router.delete("/pdf-tasks/{task_id}")
async def delete_pdf_task(task_id: str):
    task_dir = _task_dir(task_id)
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="PDF task not found")
    shutil.rmtree(task_dir, ignore_errors=True)
    return {"status": "deleted", "id": task_id}


@router.post("/pdf-tasks/{task_id}/apply-stamp")
async def apply_stamp_to_pdf_task(
    task_id: str,
    payload: ApplyStampPayload,
    db: AsyncSession = Depends(get_db_session),
):
    meta = _load_task(task_id)
    pdf_doc = await _open_pdf(task_id)
    try:
        stamp_path = await _get_stamp_image_path(db, payload.owner_id, payload.role)
        template = _load_template(payload.template_id) if payload.template_id else None
        positions = (template or {}).get("positions") or {}
        role_key = payload.role or "default"
        rect_data = positions.get(role_key) or positions.get("default") or {}

        if payload.mode == "full":
            page_indices = range(pdf_doc.page_count)
        else:
            page_indices = [max(0, min(payload.page_index, pdf_doc.page_count - 1))]

        for page_index in page_indices:
            page = pdf_doc[page_index]
            rect = fitz.Rect(
                float(rect_data.get("x", page.rect.width * 0.68)),
                float(rect_data.get("y", page.rect.height * 0.72)),
                float(rect_data.get("x", page.rect.width * 0.68)) + float(rect_data.get("w", page.rect.width * 0.22)),
                float(rect_data.get("y", page.rect.height * 0.72)) + float(rect_data.get("h", page.rect.height * 0.18)),
            )
            stamp_bytes = get_rotated_stamp_bytes(str(stamp_path))
            page.insert_image(rect, stream=stamp_bytes, keep_proportion=True, overlay=True)

        pdf_doc.save(_task_pdf_path(task_id), deflate=True, garbage=4, clean=True)
        meta["status"] = "stamped"
        meta["updated_at"] = time.time()
        meta["template_id"] = payload.template_id or meta.get("template_id")
        _write_json(_task_meta_path(task_id), meta)
        return _serialize_task(_load_task(task_id))
    finally:
        pdf_doc.close()


@router.post("/pdf-tasks/{task_id}/compress")
async def compress_pdf_task(task_id: str):
    meta = _load_task(task_id)
    pdf_doc = await _open_pdf(task_id)
    try:
        pdf_doc.save(_task_pdf_path(task_id), deflate=True, garbage=4, clean=True)
        meta["status"] = "compressed"
        meta["updated_at"] = time.time()
        _write_json(_task_meta_path(task_id), meta)
        return _serialize_task(_load_task(task_id))
    finally:
        pdf_doc.close()


@router.post("/pdf-tasks/{task_id}/page-operations")
async def page_operations(task_id: str, payload: PageOperationsPayload):
    meta = _load_task(task_id)
    pdf_doc = await _open_pdf(task_id)
    try:
        if payload.operation == "delete":
            for page_index in sorted(set(payload.page_indices), reverse=True):
                if 0 <= page_index < pdf_doc.page_count:
                    pdf_doc.delete_page(page_index)
        elif payload.operation == "reorder":
            order = payload.page_order or []
            if sorted(order) != list(range(pdf_doc.page_count)):
                raise HTTPException(status_code=400, detail="page_order must contain each page index exactly once")
            reordered = fitz.open()
            for page_index in order:
                reordered.insert_pdf(pdf_doc, from_page=page_index, to_page=page_index)
            pdf_doc.close()
            pdf_doc = reordered
        elif payload.operation == "add":
            for _ in range(max(1, payload.insert_count)):
                pdf_doc.new_page(-1)
        else:
            raise HTTPException(status_code=400, detail="Unsupported page operation")

        pdf_doc.save(_task_pdf_path(task_id), deflate=True, garbage=4, clean=True)
        meta["status"] = "edited"
        meta["updated_at"] = time.time()
        _write_json(_task_meta_path(task_id), meta)
        return _serialize_task(_load_task(task_id))
    finally:
        pdf_doc.close()


@router.get("/stamp-templates")
async def list_stamp_templates() -> list[dict]:
    return [_serialize_template(_load_template(template_id)) for template_id in _list_template_ids()]


@router.post("/stamp-templates")
async def create_stamp_template(payload: StampTemplateCreate):
    template_id = uuid4().hex
    now = time.time()
    meta = {
        "id": template_id,
        "name": payload.name,
        "description": payload.description,
        "active": payload.active,
        "positions": payload.positions,
        "created_at": now,
        "updated_at": now,
    }
    _write_json(_template_meta_path(template_id), meta)
    return _serialize_template(meta)


@router.get("/stamp-templates/{template_id}")
async def get_stamp_template(template_id: str) -> dict:
    return _serialize_template(_load_template(template_id))


@router.put("/stamp-templates/{template_id}")
async def update_stamp_template(template_id: str, payload: StampTemplateUpdate):
    meta = _load_template(template_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        meta[key] = value
    meta["updated_at"] = time.time()
    _write_json(_template_meta_path(template_id), meta)
    return _serialize_template(_load_template(template_id))


@router.delete("/stamp-templates/{template_id}")
async def delete_stamp_template(template_id: str):
    template_dir = _template_dir(template_id)
    if not template_dir.exists():
        raise HTTPException(status_code=404, detail="Stamp template not found")
    shutil.rmtree(template_dir, ignore_errors=True)
    return {"status": "deleted", "id": template_id}
