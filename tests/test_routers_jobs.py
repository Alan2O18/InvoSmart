import pytest
from unittest.mock import AsyncMock

from backend.repositories.project_repository import ProjectArchivedError
from backend.main import app
from backend.routers.suggestions import get_suggestion_repo

def test_get_project_jobs(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.sync_status_to_db = AsyncMock()
    mock_job_repo = AsyncMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "j1", "status": "done", "image_path": ""}])
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo
    
    response = mock_app_client.get("/api/projects/proj1/jobs")
    assert response.status_code == 200
    assert response.json() == [{"job_id": "j1", "status": "done", "image_path": ""}]


def test_get_project_jobs_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.sync_status_to_db = AsyncMock(side_effect=RuntimeError("sync failed"))

    response = mock_app_client.get("/api/projects/proj1/jobs")
    assert response.status_code == 500

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


def test_delete_job_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_job = AsyncMock(side_effect=ProjectArchivedError("archived"))

    response = mock_app_client.delete("/api/projects/proj1/jobs/j1")
    assert response.status_code == 409


def test_delete_job_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_job = AsyncMock(side_effect=RuntimeError("boom"))

    response = mock_app_client.delete("/api/projects/proj1/jobs/j1")
    assert response.status_code == 500

def test_run_single_processing(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_single_processing = AsyncMock(return_value={"status": "queued"})
    response = mock_app_client.post("/api/projects/proj1/jobs/j1/process")
    assert response.status_code == 200
    assert response.json() == {"status": "queued"}


def test_run_single_processing_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_single_processing = AsyncMock(side_effect=ProjectArchivedError("archived"))

    response = mock_app_client.post("/api/projects/proj1/jobs/j1/process")
    assert response.status_code == 409


def test_run_single_processing_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_single_processing = AsyncMock(side_effect=RuntimeError("processing error"))

    response = mock_app_client.post("/api/projects/proj1/jobs/j1/process")
    assert response.status_code == 500

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


def test_save_manual_json_feedback_error_does_not_break(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(return_value=True)

    fake_suggestion_repo = AsyncMock()
    fake_suggestion_repo.extract_from_manual_json = AsyncMock(side_effect=RuntimeError("feedback down"))

    app.dependency_overrides[get_suggestion_repo] = lambda: fake_suggestion_repo
    try:
        response = mock_app_client.put(
            "/api/projects/proj1/jobs/j1/json",
            json={"json_data": {"header": {"buyer": "TEST"}}},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "saved", "job_id": "j1"}
    finally:
        app.dependency_overrides.pop(get_suggestion_repo, None)

def test_save_manual_json_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(return_value=False)
    
    response = mock_app_client.put("/api/projects/proj1/jobs/j1/json", json={"json_data": {}})
    assert response.status_code == 404


def test_save_manual_json_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(side_effect=ProjectArchivedError("Project proj1 is archived and read-only"))

    response = mock_app_client.put("/api/projects/proj1/jobs/j1/json", json={"json_data": {}})
    assert response.status_code == 409


def test_save_manual_json_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.save_manual_json = AsyncMock(side_effect=RuntimeError("save error"))

    response = mock_app_client.put("/api/projects/proj1/jobs/j1/json", json={"json_data": {}})
    assert response.status_code == 500


def test_detect_sub_rects_success(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_job_sub_rects = AsyncMock(return_value=[{"points": [[0, 0], [10, 0], [10, 10], [0, 10]], "area": 100.0}])

    response = mock_app_client.post("/api/projects/proj1/jobs/j1/detect-sub-rects")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(payload["rects"]) == 1


def test_detect_sub_rects_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_job_sub_rects = AsyncMock(side_effect=FileNotFoundError("missing"))

    response = mock_app_client.post("/api/projects/proj1/jobs/j1/detect-sub-rects")
    assert response.status_code == 404


def test_detect_sub_rects_bad_request(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_job_sub_rects = AsyncMock(side_effect=ValueError("bad rect"))

    response = mock_app_client.post("/api/projects/proj1/jobs/j1/detect-sub-rects")
    assert response.status_code == 400


def test_detect_sub_rects_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_job_sub_rects = AsyncMock(side_effect=RuntimeError("oops"))

    response = mock_app_client.post("/api/projects/proj1/jobs/j1/detect-sub-rects")
    assert response.status_code == 500


def test_apply_resplit_success(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_job_resplit = AsyncMock(return_value={"status": "resplit_applied", "new_job_ids": ["n1"]})

    response = mock_app_client.post(
        "/api/projects/proj1/jobs/j1/apply-resplit",
        json={
            "sub_rects": [
                {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resplit_applied"


def test_apply_resplit_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_job_resplit = AsyncMock(side_effect=ProjectArchivedError("locked"))

    response = mock_app_client.post(
        "/api/projects/proj1/jobs/j1/apply-resplit",
        json={
            "sub_rects": [
                {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
            ]
        },
    )
    assert response.status_code == 409


def test_apply_resplit_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_job_resplit = AsyncMock(side_effect=FileNotFoundError("missing"))

    response = mock_app_client.post(
        "/api/projects/proj1/jobs/j1/apply-resplit",
        json={"sub_rects": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
    )
    assert response.status_code == 404


def test_apply_resplit_bad_request(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_job_resplit = AsyncMock(side_effect=ValueError("invalid"))

    response = mock_app_client.post(
        "/api/projects/proj1/jobs/j1/apply-resplit",
        json={"sub_rects": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
    )
    assert response.status_code == 400


def test_apply_resplit_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_job_resplit = AsyncMock(side_effect=RuntimeError("unexpected"))

    response = mock_app_client.post(
        "/api/projects/proj1/jobs/j1/apply-resplit",
        json={"sub_rects": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
    )
    assert response.status_code == 500
