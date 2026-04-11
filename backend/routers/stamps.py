import base64
import json
import logging
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import core
from backend.database.models import Stamp
from backend.processing.stamp_processor import StampProcessor

logger = logging.getLogger(__name__)
router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STAMPS_RELATIVE_DIR = Path("backend") / "data" / "stamps"
STAMPS_STORAGE_DIR = PROJECT_ROOT / STAMPS_RELATIVE_DIR


class StampSelection(BaseModel):
    x: int
    y: int
    w: int
    h: int
    name: str
    category: str
    group_name: str | None = None


async def get_stamp_db() -> AsyncGenerator[AsyncSession, None]:
    if core.AsyncSessionLocal is None:
        raise HTTPException(status_code=503, detail="Database is not initialized")
    async with core.AsyncSessionLocal() as session:
        yield session


def _ensure_storage_dir() -> Path:
    STAMPS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return STAMPS_STORAGE_DIR


async def _decode_upload_to_image(file: UploadFile) -> np.ndarray:
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    np_bytes = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Cannot decode uploaded image")
    return image


def _stamp_url_from_image_path(image_path: str) -> str:
    filename = Path(image_path).name
    return f"/stamps-static/{filename}"


def _serialize_stamp(stamp: Stamp) -> dict:
    return {
        "id": stamp.id,
        "name": stamp.name,
        "category": stamp.category,
        "group_name": stamp.group_name,
        "image_path": stamp.image_path,
        "image_url": _stamp_url_from_image_path(stamp.image_path),
        "created_at": stamp.created_at,
    }


def _resolve_image_path(image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _build_preview_base64(image: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> str | None:
    preview = image.copy()
    for x, y, w, h in boxes:
        cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 255), 2)
    ok, encoded = cv2.imencode(".png", preview)
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


@router.get("/stamps")
async def list_stamps(db: AsyncSession = Depends(get_stamp_db)):
    result = await db.execute(select(Stamp).order_by(Stamp.created_at.desc()))
    stamps = result.scalars().all()
    return [_serialize_stamp(stamp) for stamp in stamps]


@router.post("/stamps/detect")
async def detect_stamps(
    file: UploadFile = File(...),
    mode: str = Form("red"),
):
    clean_mode = (mode or "red").strip().lower()
    if clean_mode not in {"red", "edge"}:
        raise HTTPException(status_code=400, detail="mode must be 'red' or 'edge'")

    image = await _decode_upload_to_image(file)
    processor = StampProcessor()
    boxes = processor.detect_stamps(image, mode=clean_mode)

    return {
        "mode": clean_mode,
        "image_width": int(image.shape[1]),
        "image_height": int(image.shape[0]),
        "boxes": [{"x": x, "y": y, "w": w, "h": h} for x, y, w, h in boxes],
        "preview_image_base64": _build_preview_base64(image, boxes),
    }


@router.post("/stamps/register")
async def register_stamps(
    file: UploadFile = File(...),
    mode: str = Form("red"),
    selections: str = Form(...),
    db: AsyncSession = Depends(get_stamp_db),
):
    clean_mode = (mode or "red").strip().lower()
    if clean_mode not in {"red", "edge"}:
        raise HTTPException(status_code=400, detail="mode must be 'red' or 'edge'")

    try:
        raw_selections = json.loads(selections)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid selections JSON: {exc}") from exc

    if not isinstance(raw_selections, list) or not raw_selections:
        raise HTTPException(status_code=400, detail="selections must be a non-empty array")

    parsed: list[StampSelection] = []
    for idx, raw_item in enumerate(raw_selections):
        try:
            item = StampSelection.model_validate(raw_item)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Invalid selection at index {idx}: {exc}") from exc

        item.name = item.name.strip()
        item.category = item.category.strip()
        if not item.name or not item.category:
            raise HTTPException(status_code=400, detail=f"Selection {idx} must have name and category")
        if item.group_name is not None:
            item.group_name = item.group_name.strip() or None
        parsed.append(item)

    image = await _decode_upload_to_image(file)
    processor = StampProcessor()
    storage_dir = _ensure_storage_dir()
    written_files: list[Path] = []
    created_entities: list[Stamp] = []

    try:
        for item in parsed:
            crop = processor.crop_and_remove_background(
                image,
                rect=(item.x, item.y, item.w, item.h),
                mode=clean_mode,
            )
            filename = f"stamp_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png"
            output_path = storage_dir / filename
            if not cv2.imwrite(str(output_path), crop):
                raise HTTPException(status_code=500, detail=f"Failed to write stamp image: {filename}")

            written_files.append(output_path)
            try:
                stored_path = str(output_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            except ValueError:
                stored_path = str(output_path)
            record = Stamp(
                name=item.name,
                category=item.category,
                group_name=item.group_name,
                image_path=stored_path,
                created_at=time.time(),
            )
            db.add(record)
            created_entities.append(record)

        await db.commit()
        for record in created_entities:
            await db.refresh(record)
    except HTTPException:
        await db.rollback()
        for file_path in written_files:
            file_path.unlink(missing_ok=True)
        raise
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        for file_path in written_files:
            file_path.unlink(missing_ok=True)
        logger.error("Error registering stamps: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "registered",
        "count": len(created_entities),
        "items": [_serialize_stamp(record) for record in created_entities],
    }


@router.delete("/stamps/{stamp_id}")
async def delete_stamp(stamp_id: int, db: AsyncSession = Depends(get_stamp_db)):
    result = await db.execute(select(Stamp).where(Stamp.id == stamp_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Stamp not found")

    image_path = _resolve_image_path(record.image_path)
    if image_path.exists() and image_path.is_file():
        image_path.unlink(missing_ok=True)

    await db.delete(record)
    await db.commit()
    return {"status": "deleted", "id": stamp_id}
