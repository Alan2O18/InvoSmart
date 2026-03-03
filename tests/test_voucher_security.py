from unittest.mock import AsyncMock

from backend.repositories.voucher_layout_repo import sanitize_project_id


def test_sanitize_project_id_blocks_path_traversal_chars():
    assert sanitize_project_id("../../evil\\proj") == "____evil_proj"
    assert sanitize_project_id("a/b/c") == "a_b_c"


def test_voucher_image_forbidden_response_shape(mock_app_client, mock_engine_for_api):
    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value=None)
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.get("/api/voucher/proj1/image/foreign-job?thumb=true")
    assert response.status_code == 403
    payload = response.json()["detail"]
    assert payload["error"] == "FORBIDDEN"
