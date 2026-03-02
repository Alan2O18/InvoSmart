import pytest
from unittest.mock import AsyncMock

def test_save_manual_text(mock_app_client, mock_engine_for_api):
    mock_job_repo = AsyncMock()
    mock_job_repo.save_manual_json = AsyncMock(return_value=True)
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo
    
    response = mock_app_client.put("/api/projects/proj1/jobs/j1/manual", json={"manual_text": "Corrected."})
    assert response.status_code == 200
    assert response.json() == {"status": "saved", "job_id": "j1"}

def test_save_manual_text_not_found(mock_app_client, mock_engine_for_api):
    mock_job_repo = AsyncMock()
    mock_job_repo.save_manual_json = AsyncMock(return_value=False)
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo
    
    response = mock_app_client.put("/api/projects/proj1/jobs/j1/manual", json={"manual_text": "Corrected."})
    assert response.status_code == 404


