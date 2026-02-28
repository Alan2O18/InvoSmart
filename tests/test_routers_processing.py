import pytest
import io
from unittest.mock import AsyncMock

def test_run_processing(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_processing = AsyncMock(return_value={"status": "queued"})
    response = mock_app_client.post("/api/projects/proj1/run_processing")
    assert response.status_code == 200
    assert response.json() == {"status": "queued"}

def test_run_splitting(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_splitting = AsyncMock(return_value={"status": "splitting"})
    response = mock_app_client.post("/api/projects/proj1/run_split")
    assert response.status_code == 200
    assert response.json() == {"status": "splitting"}

def test_run_split_single(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_split_single = AsyncMock(return_value={"status": "splitting single"})
    response = mock_app_client.post("/api/projects/proj1/split/f1.jpg")
    assert response.status_code == 200

def test_run_excel(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_excel = AsyncMock(return_value={"status": "excel generated"})
    response = mock_app_client.post("/api/projects/proj1/run_export")
    assert response.status_code == 200

def test_archive_project(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.archive_project = AsyncMock(return_value={"status": "archived"})
    response = mock_app_client.post("/api/projects/proj1/run_archive")
    assert response.status_code == 200

def test_regenerate_excel(mock_app_client, mock_engine_for_api):
    mock_export_handler = AsyncMock()
    mock_export_handler.run_word = AsyncMock(return_value="fake_path.docx")
    mock_engine_for_api.export_handler = mock_export_handler
    
    from unittest.mock import patch
    with patch("backend.routers.processing.os.path.exists", return_value=True), \
         patch("backend.routers.processing.FileResponse", return_value={"status": "word generated"}):
        files = {"file": ("test.xlsx", io.BytesIO(b"fake excel"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        response = mock_app_client.post("/api/projects/proj1/run_word_export")
        assert response.status_code == 200
        mock_export_handler.run_word.assert_called_once()
