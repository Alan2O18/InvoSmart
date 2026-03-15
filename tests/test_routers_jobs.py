import pytest
from unittest.mock import AsyncMock

from backend.repositories.project_repository import ProjectArchivedError

def test_get_project_jobs(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.sync_status_to_db = AsyncMock()
    mock_job_repo = AsyncMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "j1", "status": "done", "image_path": ""}])
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo
    
    response = mock_app_client.get("/api/projects/proj1/jobs")
    assert response.status_code == 200
    assert response.json() == [{"job_id": "j1", "status": "done", "image_path": ""}]

def test_get_job_details(mock_app_client, mock_engine_for_api):
    mock_job_repo = AsyncMock()
    # Mocking get_job_details dict
    mock_job_repo.get_job_details = AsyncMock(return_value={"job_id": "j1", "details": "yes"})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo
    
    response = mock_app_client.get("/api/projects/proj1/jobs/j1/details")
    assert response.status_code == 200
    assert response.json() == {"job_id": "j1", "details": "yes"}

def test_get_job_details_not_found(mock_app_client, mock_engine_for_api):
    mock_job_repo = AsyncMock()
    mock_job_repo.get_job_details = AsyncMock(return_value=None)
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo
    
    response = mock_app_client.get("/api/projects/proj1/jobs/j1/details")
    assert response.status_code == 404

def test_delete_job(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_job = AsyncMock(return_value={"status": "deleted"})
    response = mock_app_client.delete("/api/projects/proj1/jobs/j1")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}

def test_run_single_processing(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_single_processing = AsyncMock(return_value={"status": "queued"})
    response = mock_app_client.post("/api/projects/proj1/jobs/j1/process")
    assert response.status_code == 200
    assert response.json() == {"status": "queued"}

def test_save_manual_json_success(mock_app_client, mock_engine_for_api, monkeypatch):
    mock_engine_for_api.save_manual_json = AsyncMock(return_value=True)
    
    import sys
    
    mock_sugg_repo_class = AsyncMock()
    mock_instance = AsyncMock()
    mock_instance.extract_from_manual_json = AsyncMock(return_value=1)
    mock_sugg_repo_class.return_value = mock_instance
    
    mock_module = type(sys)("backend.repositories.suggestion_repository")
    mock_module.SuggestionRepository = mock_sugg_repo_class
    sys.modules["backend.repositories.suggestion_repository"] = mock_module
    
    try:
        response = mock_app_client.put("/api/projects/proj1/jobs/j1/json", json={"json_data": {"header": {"buyer": "TEST"}}})
        assert response.status_code == 200
        assert response.json() == {"status": "saved", "job_id": "j1"}
    finally:
        del sys.modules["backend.repositories.suggestion_repository"]

def test_save_manual_json_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(return_value=False)
    
    response = mock_app_client.put("/api/projects/proj1/jobs/j1/json", json={"json_data": {}})
    assert response.status_code == 404


def test_save_manual_json_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(side_effect=ProjectArchivedError("Project proj1 is archived and read-only"))

    response = mock_app_client.put("/api/projects/proj1/jobs/j1/json", json={"json_data": {}})
    assert response.status_code == 409
