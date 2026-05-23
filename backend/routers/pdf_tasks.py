from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, get_engine
from backend.engine.core import Engine
from backend.repositories.pdf_task_repo import PdfTaskRepository
from backend.repositories.stamp_template_repo import StampTemplateRepository
from backend.engine.pdf_task_service import PdfTaskService
from backend.repositories.stamp_repository import StampRepository

logger = logging.getLogger(__name__)
router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def _load_task(task_id: str, repo: PdfTaskRepository, service: PdfTaskService) -> dict:
    meta = repo.read_meta(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="PDF task not found")
    pdf_path = repo._task_pdf_path(task_id)
    if pdf_path.exists():
        try:
            meta["page_count"] = service.get_pdf_page_count(pdf_path)
        except Exception:
            meta.setdefault("page_count", 0)
    meta["has_file"] = pdf_path.exists()
    meta["file_url"] = f"/api/pdf-tasks/{task_id}/file"
    return meta


def _load_template(template_id: str, repo: StampTemplateRepository) -> dict:
    meta = repo.read_meta(template_id)
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


def _resolve_stamp_image_path(stamp: dict) -> Path:
    image_path = Path(str(stamp.get("image_path") or ""))
    if not image_path:
        raise HTTPException(status_code=404, detail="Stamp image path missing")
    return image_path if image_path.is_absolute() else PROJECT_ROOT / image_path


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


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


@router.get("/pdf-tasks")
async def list_pdf_tasks(engine: Engine = Depends(get_engine)) -> list[dict]:
    return [
        _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))
        for task_id in engine.pdf_task_repo.list_task_ids()
    ]


@router.post("/pdf-tasks")
async def create_pdf_task(
    file: UploadFile = File(...),
    title: str = Form(""),
    engine: Engine = Depends(get_engine),
):
    task_id = uuid4().hex
    filename = Path(file.filename or "uploaded.pdf").name
    content = await file.read()

    pdf_path = engine.pdf_task_repo.write_pdf_content(task_id, content)
    page_count = engine.pdf_task_service.get_pdf_page_count(pdf_path)

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
    engine.pdf_task_repo.write_meta(task_id, meta)
    return _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))


@router.get("/pdf-tasks/{task_id}")
async def get_pdf_task(task_id: str, engine: Engine = Depends(get_engine)) -> dict:
    return _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))


@router.get("/pdf-tasks/{task_id}/file")
async def get_pdf_task_file(task_id: str, engine: Engine = Depends(get_engine)):
    pdf_path = engine.pdf_task_repo._task_pdf_path(task_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="inline",
    )


@router.put("/pdf-tasks/{task_id}")
async def update_pdf_task(task_id: str, payload: PdfTaskUpdate, engine: Engine = Depends(get_engine)):
    meta = _load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service)
    for key, value in payload.model_dump(exclude_none=True).items():
        meta[key] = value
    meta["updated_at"] = time.time()
    engine.pdf_task_repo.write_meta(task_id, meta)
    return _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))


@router.delete("/pdf-tasks/{task_id}")
async def delete_pdf_task(task_id: str, engine: Engine = Depends(get_engine)):
    success = engine.pdf_task_repo.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="PDF task not found")
    return {"status": "deleted", "id": task_id}


@router.post("/pdf-tasks/{task_id}/apply-stamp")
async def apply_stamp_to_pdf_task(
    task_id: str,
    payload: ApplyStampPayload,
    db: AsyncSession = Depends(get_db_session),
    engine: Engine = Depends(get_engine),
):
    meta = _load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service)
    stamp_path = await _get_stamp_image_path(db, payload.owner_id, payload.role)

    template = _load_template(payload.template_id, engine.stamp_template_repo) if payload.template_id else None
    positions = (template or {}).get("positions") or {}
    role_key = payload.role or "default"
    rect_data = positions.get(role_key) or positions.get("default") or {}

    try:
        engine.pdf_task_service.apply_stamp(
            task_id=task_id,
            stamp_path=stamp_path,
            rect_data=rect_data,
            mode=payload.mode,
            page_index=payload.page_index,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    meta["status"] = "stamped"
    meta["updated_at"] = time.time()
    meta["template_id"] = payload.template_id or meta.get("template_id")
    engine.pdf_task_repo.write_meta(task_id, meta)
    return _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))


@router.post("/pdf-tasks/{task_id}/compress")
async def compress_pdf_task(task_id: str, engine: Engine = Depends(get_engine)):
    meta = _load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service)
    try:
        engine.pdf_task_service.compress_pdf(task_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    meta["status"] = "compressed"
    meta["updated_at"] = time.time()
    engine.pdf_task_repo.write_meta(task_id, meta)
    return _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))


@router.post("/pdf-tasks/{task_id}/page-operations")
async def page_operations(
    task_id: str,
    payload: PageOperationsPayload,
    engine: Engine = Depends(get_engine),
):
    meta = _load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service)
    try:
        engine.pdf_task_service.execute_page_operations(
            task_id=task_id,
            operation=payload.operation,
            page_indices=payload.page_indices,
            page_order=payload.page_order,
            insert_count=payload.insert_count,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    meta["status"] = "edited"
    meta["updated_at"] = time.time()
    engine.pdf_task_repo.write_meta(task_id, meta)
    return _serialize_task(_load_task(task_id, engine.pdf_task_repo, engine.pdf_task_service))


@router.get("/stamp-templates")
async def list_stamp_templates(engine: Engine = Depends(get_engine)) -> list[dict]:
    return [
        _serialize_template(_load_template(template_id, engine.stamp_template_repo))
        for template_id in engine.stamp_template_repo.list_template_ids()
    ]


@router.post("/stamp-templates")
async def create_stamp_template(payload: StampTemplateCreate, engine: Engine = Depends(get_engine)):
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
    engine.stamp_template_repo.write_meta(template_id, meta)
    return _serialize_template(meta)


@router.get("/stamp-templates/{template_id}")
async def get_stamp_template(template_id: str, engine: Engine = Depends(get_engine)) -> dict:
    return _serialize_template(_load_template(template_id, engine.stamp_template_repo))


@router.put("/stamp-templates/{template_id}")
async def update_stamp_template(
    template_id: str,
    payload: StampTemplateUpdate,
    engine: Engine = Depends(get_engine),
):
    meta = _load_template(template_id, engine.stamp_template_repo)
    for key, value in payload.model_dump(exclude_none=True).items():
        meta[key] = value
    meta["updated_at"] = time.time()
    engine.stamp_template_repo.write_meta(template_id, meta)
    return _serialize_template(_load_template(template_id, engine.stamp_template_repo))


@router.delete("/stamp-templates/{template_id}")
async def delete_stamp_template(template_id: str, engine: Engine = Depends(get_engine)):
    success = engine.stamp_template_repo.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stamp template not found")
    return {"status": "deleted", "id": template_id}
