import pytest
from unittest.mock import AsyncMock

from backend.repositories.project_repository import ProjectArchivedError

def test_save_manual_text(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(return_value=True)
    
    response = mock_app_client.put("/api/projects/proj1/jobs/j1/manual", json={"manual_text": "Corrected."})
    assert response.status_code == 200
    assert response.json() == {"status": "saved", "job_id": "j1"}

def test_save_manual_text_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(return_value=False)
    
    response = mock_app_client.put("/api/projects/proj1/jobs/j1/manual", json={"manual_text": "Corrected."})
    assert response.status_code == 404


def test_save_manual_text_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(side_effect=ProjectArchivedError("Project proj1 is archived and read-only"))

    response = mock_app_client.put("/api/projects/proj1/jobs/j1/manual", json={"manual_text": "Corrected."})
    assert response.status_code == 409


