# Groups Router - 群組管理端點
import logging
from pathlib import Path
import shutil
import time
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


class GroupCreate(BaseModel):
    group_name: str
    leader_name: str


def _assert_safe_component(value: str, field_name: str) -> str:
    text = (value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{field_name} cannot be empty")
    if "/" in text or "\\" in text or ".." in text:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}")
    return text


def _stamp_root(engine: Engine) -> Path:
    root = engine.project_repo.workspace_root / "_group_stamps"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _leader_stamp_dir(engine: Engine, group_name: str, leader_name: str, create: bool = False) -> Path:
    group = _assert_safe_component(group_name, "group_name")
    leader = _assert_safe_component(leader_name, "leader_name")
    path = _stamp_root(engine) / group / leader
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _build_stamp_payload(group_name: str, leader_name: str, stamp_file: Path) -> dict:
    rel_url = (
        "/api/projects/groups/"
        f"{quote(group_name)}/leaders/{quote(leader_name)}/stamps/{quote(stamp_file.name)}"
    )
    return {
        "filename": stamp_file.name,
        "size": stamp_file.stat().st_size,
        "url": rel_url,
        "updated_at": stamp_file.stat().st_mtime,
    }


def _list_stamps_for_leader(engine: Engine, group_name: str, leader_name: str) -> list[dict]:
    stamp_dir = _leader_stamp_dir(engine, group_name, leader_name, create=False)
    if not stamp_dir.exists() or not stamp_dir.is_dir():
        return []
    stamps = []
    for file_path in sorted(stamp_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not file_path.is_file():
            continue
        stamps.append(_build_stamp_payload(group_name, leader_name, file_path))
    return stamps


@router.get("/groups/list")
async def list_groups(engine: Engine = Depends(get_engine)):
    try:
        groups = await engine.project_repo.list_groups()
        enriched = []
        for item in groups:
            leader_names = item.get("leader_names") or []
            leaders = []
            for leader_name in leader_names:
                leaders.append(
                    {
                        "name": leader_name,
                        "stamps": _list_stamps_for_leader(engine, item["group_name"], leader_name),
                    }
                )
            enriched.append({**item, "leaders": leaders})
        return enriched
    except Exception as e:
        logger.error(f"Error listing groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups")
async def upsert_group(group: GroupCreate, engine: Engine = Depends(get_engine)):
    try:
        await engine.project_repo.upsert_group(group.group_name, group.leader_name)
        return {"status": "success", "group": group.model_dump()}
    except Exception as e:
        logger.error(f"Error upserting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/groups/{group_name}")
async def delete_group(group_name: str, engine: Engine = Depends(get_engine)):
    try:
        await engine.project_repo.delete_group(group_name)
        stamp_dir = _stamp_root(engine) / _assert_safe_component(group_name, "group_name")
        if stamp_dir.exists() and stamp_dir.is_dir():
            shutil.rmtree(stamp_dir, ignore_errors=True)
        return {"status": "deleted", "group_name": group_name}
    except Exception as e:
        logger.error(f"Error deleting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/groups/{group_name}/leaders/{leader_name}")
async def delete_group_leader(group_name: str, leader_name: str, engine: Engine = Depends(get_engine)):
    try:
        await engine.project_repo.remove_group_leader(group_name, leader_name)
        stamp_dir = _stamp_root(engine) / _assert_safe_component(group_name, "group_name") / _assert_safe_component(leader_name, "leader_name")
        if stamp_dir.exists() and stamp_dir.is_dir():
            shutil.rmtree(stamp_dir, ignore_errors=True)
        return {"status": "deleted", "group_name": group_name, "leader_name": leader_name}
    except Exception as e:
        logger.error(f"Error deleting group leader: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups/{group_name}/leaders/{leader_name}/stamps")
async def upload_leader_stamps(
    group_name: str,
    leader_name: str,
    files: list[UploadFile] = File(...),
    engine: Engine = Depends(get_engine),
):
    try:
        clean_group = _assert_safe_component(group_name, "group_name")
        clean_leader = _assert_safe_component(leader_name, "leader_name")
        await engine.project_repo.upsert_group(clean_group, clean_leader)
        target_dir = _leader_stamp_dir(engine, clean_group, clean_leader, create=True)

        written = []
        for upload in files:
            content_type = upload.content_type or ""
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {upload.filename}")

            src_name = Path(upload.filename or "stamp.png").name
            stem = Path(src_name).stem or "stamp"
            suffix = Path(src_name).suffix or ".png"
            safe_name = f"{stem}_{int(time.time() * 1000)}{suffix}"
            dest_path = target_dir / safe_name

            with open(dest_path, "wb") as out:
                out.write(await upload.read())
            written.append(_build_stamp_payload(clean_group, clean_leader, dest_path))

        return {
            "status": "uploaded",
            "group_name": clean_group,
            "leader_name": clean_leader,
            "files": written,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading leader stamps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{group_name}/leaders/{leader_name}/stamps")
async def list_leader_stamps(group_name: str, leader_name: str, engine: Engine = Depends(get_engine)):
    try:
        clean_group = _assert_safe_component(group_name, "group_name")
        clean_leader = _assert_safe_component(leader_name, "leader_name")
        return {
            "group_name": clean_group,
            "leader_name": clean_leader,
            "files": _list_stamps_for_leader(engine, clean_group, clean_leader),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing leader stamps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups/{group_name}/leaders/{leader_name}/stamps/{filename}")
async def get_leader_stamp_file(group_name: str, leader_name: str, filename: str, engine: Engine = Depends(get_engine)):
    try:
        clean_group = _assert_safe_component(group_name, "group_name")
        clean_leader = _assert_safe_component(leader_name, "leader_name")
        clean_filename = _assert_safe_component(filename, "filename")
        stamp_path = _leader_stamp_dir(engine, clean_group, clean_leader, create=False) / clean_filename
        if not stamp_path.exists() or not stamp_path.is_file():
            raise HTTPException(status_code=404, detail="Stamp file not found")
        return FileResponse(path=str(stamp_path))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading leader stamp file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/groups/{group_name}/leaders/{leader_name}/stamps/{filename}")
async def delete_leader_stamp_file(group_name: str, leader_name: str, filename: str, engine: Engine = Depends(get_engine)):
    try:
        clean_group = _assert_safe_component(group_name, "group_name")
        clean_leader = _assert_safe_component(leader_name, "leader_name")
        clean_filename = _assert_safe_component(filename, "filename")
        stamp_path = _leader_stamp_dir(engine, clean_group, clean_leader, create=False) / clean_filename
        if not stamp_path.exists() or not stamp_path.is_file():
            raise HTTPException(status_code=404, detail="Stamp file not found")
        stamp_path.unlink(missing_ok=True)
        return {
            "status": "deleted",
            "group_name": clean_group,
            "leader_name": clean_leader,
            "filename": clean_filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting leader stamp file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
