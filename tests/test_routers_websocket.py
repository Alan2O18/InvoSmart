import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi import WebSocketDisconnect
from backend.routers.websocket import get_jobs, websocket_endpoint

@pytest.mark.asyncio
async def test_get_jobs_success():
    with patch("backend.routers.websocket.get_engine") as mock_get_engine:
        mock_engine = mock_get_engine.return_value
        mock_repo = AsyncMock()
        mock_repo.list_jobs.return_value = [{"job_id": "1", "status": "done"}]
        mock_engine.get_job_repo.return_value = mock_repo
        
        jobs = await get_jobs("proj1")
        assert len(jobs) == 1
        assert jobs[0]["status"] == "done"

@pytest.mark.asyncio
async def test_get_jobs_exception():
    with patch("backend.routers.websocket.get_engine") as mock_get_engine:
        mock_get_engine.side_effect = Exception("DB Error")
        jobs = await get_jobs("proj1")
        assert jobs == []

@pytest.mark.asyncio
async def test_websocket_endpoint_sends_data_and_disconnects():
    mock_ws = AsyncMock()
    
    # We want it to loop once, then raise WebSocketDisconnect to exit the while loop
    mock_ws.send_json.side_effect = [None, WebSocketDisconnect()]
    
    with patch("backend.routers.websocket.get_jobs", return_value=[{"job_id": "1"}]) as mock_get_jobs, \
         patch("backend.routers.websocket.get_engine") as mock_get_engine, \
         patch("backend.routers.websocket.asyncio.sleep", new_callable=AsyncMock):
        
        mock_engine = mock_get_engine.return_value
        mock_engine.project_repo.get_project_status.return_value = {"percent": 50}
        
        await websocket_endpoint(mock_ws, "proj1")
        
        mock_ws.accept.assert_called_once()
        # Should have called send_json at least once
        mock_ws.send_json.assert_called_with({"jobs": [{"job_id": "1"}], "progress": {"percent": 50}})

@pytest.mark.asyncio
async def test_websocket_endpoint_handles_general_exception():
    mock_ws = AsyncMock()
    mock_ws.send_json.side_effect = Exception("General error")
    mock_ws.close = AsyncMock()
    
    with patch("backend.routers.websocket.get_jobs", return_value=[]), \
         patch("backend.routers.websocket.get_engine"):
        
        await websocket_endpoint(mock_ws, "proj1")
        
        mock_ws.accept.assert_called_once()
        mock_ws.close.assert_called_once()
