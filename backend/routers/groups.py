# Groups Router - 群組管理端點
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


class GroupCreate(BaseModel):
    group_name: str
    leader_name: str


@router.get("/groups/list")
def list_groups(engine: Engine = Depends(get_engine)):
    try:
        return engine.project_manager.list_groups()
    except Exception as e:
        logger.error(f"Error listing groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/groups")
def upsert_group(group: GroupCreate, engine: Engine = Depends(get_engine)):
    try:
        engine.project_manager.upsert_group(group.group_name, group.leader_name)
        return {"status": "success", "group": group.model_dump()}
    except Exception as e:
        logger.error(f"Error upserting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/groups/{group_name}")
def delete_group(group_name: str, engine: Engine = Depends(get_engine)):
    try:
        engine.project_manager.delete_group(group_name)
        return {"status": "deleted", "group_name": group_name}
    except Exception as e:
        logger.error(f"Error deleting group: {e}")
        raise HTTPException(status_code=500, detail=str(e))
