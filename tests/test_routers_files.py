import pytest
import io
from unittest.mock import AsyncMock

def test_add_files(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.add_project_files = AsyncMock(return_value={"status": "added"})
    files = {"files": ("test.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    data = {"type": "raw"}
    
    response = mock_app_client.post("/api/projects/proj1/add_files", data=data, files=files)
    assert response.status_code == 200
    assert response.json() == {"status": "added"}
    mock_engine_for_api.add_project_files.assert_called_once()

def test_rotate_image(mock_app_client, mock_engine_for_api):
    # rotate_image is a sync method calling sync backend
    mock_engine_for_api.rotate_image.return_value = {"status": "rotated"}
    response = mock_app_client.post("/api/projects/proj1/rotate/f1.jpg?angle=90")
    assert response.status_code == 200

def test_get_raw_files(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.get_raw_files = AsyncMock(return_value=["f1.jpg", "f2.jpg"])
    response = mock_app_client.get("/api/projects/proj1/raw_files")
    assert response.status_code == 200
    assert response.json() == ["f1.jpg", "f2.jpg"]

def test_delete_raw_file(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_raw_file.return_value = {"status": "deleted"}
    response = mock_app_client.delete("/api/projects/proj1/raw_files/f1.jpg")
    assert response.status_code == 200
