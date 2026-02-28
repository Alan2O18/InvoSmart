import pytest
from unittest.mock import AsyncMock

def test_list_groups(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.list_groups = AsyncMock(return_value=[{"group_name": "g1"}])
    response = mock_app_client.get("/api/projects/groups/list")
    assert response.status_code == 200
    assert response.json() == [{"group_name": "g1"}]

def test_upsert_group(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.upsert_group = AsyncMock()
    response = mock_app_client.post("/api/projects/groups", json={"group_name": "g1", "leader_name": "l1"})
    assert response.status_code == 200

def test_delete_group(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.delete_group = AsyncMock()
    response = mock_app_client.delete("/api/projects/groups/g1")
    assert response.status_code == 200
