import pytest
from unittest.mock import AsyncMock
import io

def test_list_projects(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.list_projects = AsyncMock(return_value=[{"project_id": "test1"}])
    response = mock_app_client.get("/api/projects/")
    assert response.status_code == 200
    assert response.json() == [{"project_id": "test1"}]

def test_create_project(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.create_project = AsyncMock(return_value={"status": "created"})
    files = {"files": ("test.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    data = {"project_id": "proj1", "metadata": '{"name": "test_act"}'}
    
    response = mock_app_client.post("/api/projects/", data=data, files=files)
    assert response.status_code == 200
    assert response.json() == {"status": "created"}
    mock_engine_for_api.create_project.assert_called_once()

def test_update_project(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.update_project_metadata = AsyncMock()
    mock_engine_for_api.project_repo.get_project = AsyncMock(return_value={"id": "proj1"})
    
    response = mock_app_client.put("/api/projects/proj1", json={"name": "new_name"})
    assert response.status_code == 200
    assert response.json() == {"id": "proj1"}

def test_delete_project(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.delete_project = AsyncMock(return_value={"status": "deleted"})
    response = mock_app_client.delete("/api/projects/proj1")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}

def test_get_project_status(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.sync_status_to_db = AsyncMock()
    mock_engine_for_api.project_repo.get_project_status = AsyncMock(return_value={"status": "done"})
    
    response = mock_app_client.get("/api/projects/proj1")
    assert response.status_code == 200
    assert response.json() == {"status": "done"}

def test_update_activity_info(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.update_activity_info = AsyncMock()
    mock_engine_for_api.project_repo.get_project = AsyncMock(return_value={"info": "updated"})
    
    response = mock_app_client.post("/api/projects/proj1/activity_info", json={"key": "val"})
    assert response.status_code == 200
    assert response.json() == {"info": "updated"}


