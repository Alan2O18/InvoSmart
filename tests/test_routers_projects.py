from unittest.mock import AsyncMock
import io

from backend.repositories.project_repository import ProjectArchivedError


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


def test_get_project_detail(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.get_project = AsyncMock(return_value={
        "project_id": "proj1",
        "metadata": {"budgetExpense": [{"name": "交通費"}]},
    })

    response = mock_app_client.get("/api/projects/proj1/detail")
    assert response.status_code == 200
    assert response.json()["project_id"] == "proj1"
    assert "metadata" in response.json()


def test_get_project_detail_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.get_project = AsyncMock(return_value=None)

    response = mock_app_client.get("/api/projects/proj1/detail")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_update_activity_info(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.update_activity_info = AsyncMock()
    mock_engine_for_api.project_repo.get_project = AsyncMock(return_value={"info": "updated"})
    
    response = mock_app_client.post("/api/projects/proj1/activity_info", json={"key": "val"})
    assert response.status_code == 200
    assert response.json() == {"info": "updated"}


def test_create_project_metadata_parse_error(mock_app_client, mock_engine_for_api):
    """Test create project with unparseable metadata."""
    mock_engine_for_api.create_project = AsyncMock(return_value={"status": "created"})
    files = {"files": ("test.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    data = {"project_id": "proj1", "metadata": 'invalid json {'}
    
    response = mock_app_client.post("/api/projects/", data=data, files=files)
    assert response.status_code == 200  # Should still succeed with empty metadata


def test_update_project_error(mock_app_client, mock_engine_for_api):
    """Test update project exception handling."""
    mock_engine_for_api.project_repo.update_project_metadata = AsyncMock(side_effect=Exception("DB error"))
    
    response = mock_app_client.put("/api/projects/proj1", json={"name": "new"})
    assert response.status_code == 500


def test_delete_project_error(mock_app_client, mock_engine_for_api):
    """Test delete project exception handling."""
    mock_engine_for_api.project_repo.delete_project = AsyncMock(side_effect=Exception("Delete failed"))
    
    response = mock_app_client.delete("/api/projects/proj1")
    assert response.status_code == 500


def test_get_project_status_not_found(mock_app_client, mock_engine_for_api):
    """Test get project status when project doesn't exist."""
    mock_engine_for_api.project_repo.sync_status_to_db = AsyncMock()
    mock_engine_for_api.project_repo.get_project_status = AsyncMock(side_effect=FileNotFoundError("Not found"))
    
    response = mock_app_client.get("/api/projects/nonexistent")
    assert response.status_code == 404


def test_update_activity_info_error(mock_app_client, mock_engine_for_api):
    """Test update activity info exception handling."""
    mock_engine_for_api.project_repo.update_activity_info = AsyncMock(side_effect=Exception("Update failed"))
    
    response = mock_app_client.post("/api/projects/proj1/activity_info", json={"key": "val"})
    assert response.status_code == 500


def test_update_project_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.update_project_metadata = AsyncMock(side_effect=ProjectArchivedError("Project proj1 is archived and read-only"))

    response = mock_app_client.put("/api/projects/proj1", json={"name": "new_name"})
    assert response.status_code == 409


def test_collect_project_option_suggestions_supports_people_and_budget_options():
    from backend.routers.projects import _collect_project_option_suggestions

    metadata = {
        "group": "服務組",
        "leader": "王大明、李小華",
        "coordinator": "陳小美",
        "generalAffairs": "李小華",
        "budgetIncome": [
            {"name": "社團預算"},
            {"name": "系辦補助"},
        ],
        "budgetExpense": [
            {"name": "茶水費"},
            {"name": "文具費"},
        ],
    }

    collected = _collect_project_option_suggestions(metadata)

    assert set(collected["group_name"]) == {"服務組"}
    assert set(collected["person_name"]) == {"王大明", "李小華", "陳小美"}
    assert set(collected["budget_income_item"]) == {"社團預算", "系辦補助"}
    assert set(collected["expense_category"]) == {"茶水費", "文具費"}


