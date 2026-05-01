import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.engine.stamp_service import StampService
from backend.repositories.stamp_repository import StampRepository
from backend.repositories.person_repository import PersonRepository

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
    owner_id: int  # Changed from name/group_name


def get_stamp_service() -> StampService:
    return StampService(project_root=PROJECT_ROOT, storage_relative_dir=STAMPS_STORAGE_DIR)


def get_stamp_repo(db: AsyncSession = Depends(get_db)) -> StampRepository:
    return StampRepository(db)


def get_person_repo(db: AsyncSession = Depends(get_db)) -> PersonRepository:
    return PersonRepository(db)


def _stamp_url_from_image_path(image_path: str) -> str:
    filename = Path(image_path).name
    return f"/stamps-static/{filename}"


def _serialize_stamp(stamp: dict) -> dict:
    payload = dict(stamp)
    payload["image_url"] = _stamp_url_from_image_path(str(payload.get("image_path") or ""))
    return payload


def _resolve_image_path(image_path: str) -> Path:
    path = Path(image_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@router.get("/stamps")
async def list_stamps(repo: StampRepository = Depends(get_stamp_repo)):
    rows = await repo.list_stamps()
    return [_serialize_stamp(row) for row in rows]


@router.get("/stamps/by-role/{role}")
async def list_stamps_by_role(role: str, repo: StampRepository = Depends(get_stamp_repo)):
    """List all stamps for a given role."""
    rows = await repo.list_stamps_by_role(role)
    return [_serialize_stamp(row) for row in rows]


@router.get("/stamps/by-owner/{owner_id}")
async def list_stamps_by_owner(owner_id: int, repo: StampRepository = Depends(get_stamp_repo)):
    """List all stamps for a given owner (Person ID)."""
    rows = await repo.list_stamps_by_owner(owner_id)
    return [_serialize_stamp(row) for row in rows]


@router.post("/stamps/register")
async def register_stamps(
    file: UploadFile = File(...),
    mode: str = Form("red"),
    owner_id: str = Form(...),
    selections: str = Form(...),
    repo: StampRepository = Depends(get_stamp_repo),
    service: StampService = Depends(get_stamp_service),
):
    """Register stamps for a specific owner (Person)."""
    clean_mode = (mode or "red").strip().lower()
    if clean_mode not in {"red", "edge"}:
        raise HTTPException(status_code=400, detail="mode must be 'red' or 'edge'")

    try:
        owner_id_int = int(owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="owner_id must be an integer") from exc

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

        # Validate owner_id matches
        if item.owner_id != owner_id_int:
            raise HTTPException(status_code=400, detail=f"Selection {idx} owner_id mismatch")
        parsed.append(item)

    raw_bytes = await file.read()
    try:
        created_rows = await service.register_stamps(
            raw_bytes=raw_bytes,
            selections=[item.model_dump() for item in parsed],
            mode=clean_mode,
            owner_id=owner_id_int,
            repo=repo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Error registering stamps: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "registered",
        "count": len(created_rows),
        "items": [_serialize_stamp(row) for row in created_rows],
    }


@router.delete("/stamps/{stamp_id}")
async def delete_stamp(stamp_id: int, repo: StampRepository = Depends(get_stamp_repo)):
    record = await repo.get_stamp(stamp_id)
    if not record:
        raise HTTPException(status_code=404, detail="Stamp not found")

    image_path = _resolve_image_path(str(record.get("image_path") or ""))
    if await asyncio.to_thread(image_path.exists) and await asyncio.to_thread(image_path.is_file):
        await asyncio.to_thread(image_path.unlink, missing_ok=True)

    await repo.delete_stamp(stamp_id)
    return {"status": "deleted", "id": stamp_id}
