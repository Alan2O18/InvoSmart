import io
from unittest.mock import AsyncMock

from backend.repositories.project_repository import ProjectArchivedError


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


def test_run_processing_error(mock_app_client, mock_engine_for_api):
    """Test run processing exception handling."""
    mock_engine_for_api.run_processing = AsyncMock(side_effect=Exception("Processing failed"))
    response = mock_app_client.post("/api/projects/proj1/run_processing")
    assert response.status_code == 500


def test_run_splitting_error(mock_app_client, mock_engine_for_api):
    """Test run splitting exception handling."""
    mock_engine_for_api.run_splitting = AsyncMock(side_effect=Exception("Split failed"))
    response = mock_app_client.post("/api/projects/proj1/run_split")
    assert response.status_code == 500


def test_run_split_single_error(mock_app_client, mock_engine_for_api):
    """Test run split single exception handling."""
    mock_engine_for_api.run_split_single = AsyncMock(side_effect=Exception("Split failed"))
    response = mock_app_client.post("/api/projects/proj1/split/f1.jpg")
    assert response.status_code == 500


def test_run_processing_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_processing = AsyncMock(side_effect=ProjectArchivedError("Project proj1 is archived and read-only"))
    response = mock_app_client.post("/api/projects/proj1/run_processing")
    assert response.status_code == 409
