import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app, lifespan

@pytest.fixture
def test_client():
    # Start the test client which inherently calls the lifespan
    # But since we want to unit test the lifespan separately, we just return the client
    # Actually, Starlette's TestClient uses lifespan by default.
    # We should mock init_db and recover_pending_tasks globally for safe client creation
    with patch("backend.database.core.init_db", new_callable=AsyncMock), \
         patch("backend.dependencies.get_engine") as mock_get_engine, \
         patch("backend.dependencies.reset_engine"):
        
        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine
        
        with TestClient(app) as client:
            yield client

def test_read_root(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "AI Agent Lab Backend is running"}

@pytest.mark.asyncio
async def test_lifespan_events():
    # Directly test the async context manager
    with patch("backend.database.core.init_db", new_callable=AsyncMock) as mock_init_db, \
         patch("backend.dependencies.get_engine") as mock_get_engine, \
         patch("backend.dependencies.reset_engine") as mock_reset_engine:
        
        mock_engine = MagicMock()
        mock_engine.recover_pending_tasks = AsyncMock()
        mock_get_engine.return_value = mock_engine
        
        async with lifespan(app):
            # Assertions within the context (Startup)
            mock_init_db.assert_called_once()
            mock_get_engine.assert_called_once()
            mock_engine.recover_pending_tasks.assert_called_once()
            
        # Assertions after context exit (Shutdown)
        mock_reset_engine.assert_called_once()

def test_cors_and_static_mounts():
    # Verify that the static mount is present
    routes = [route.name for route in app.routes]
    assert "static" in routes
