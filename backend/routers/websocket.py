from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import sqlite3
from backend.dependencies import get_engine

router = APIRouter()


def get_jobs(project_id: str):
    """Get jobs for a project (called from websocket, uses global engine)."""
    try:
        engine = get_engine()
        root = engine.project_manager._project_root(project_id)
        db_path = root / "jobs.db"
        if not db_path.exists():
             return []
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs ORDER BY created_at")
            rows = cur.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
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
                progress = engine.project_manager.get_project_status(project_id)
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
