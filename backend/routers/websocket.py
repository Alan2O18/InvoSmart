from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from backend.dependencies import get_engine

router = APIRouter()


def get_jobs(project_id: str):
    """Get jobs for a project (called from websocket, uses global engine)."""
    try:
        engine = get_engine()
        job_repo = engine.get_job_repo(project_id)
        return job_repo.list_jobs()
    except Exception:
        return []


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    try:
        while True:
            jobs = get_jobs(project_id)
            try:
                engine = get_engine()
                progress = engine.project_repo.get_project_status(project_id)
            except:
                progress = {}
            
            await websocket.send_json({
                "jobs": jobs,
                "progress": progress
            })
            
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error for {project_id}: {e}")
        try:
            await websocket.close()
        except:
            pass
