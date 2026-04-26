from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def test_list_groups(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.workspace_root = Path(".")
    mock_engine_for_api.project_repo.list_groups = AsyncMock(return_value=[{"group_name": "g1", "leader_names": ["l1"]}])
    response = mock_app_client.get("/api/projects/groups/list")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["group_name"] == "g1"
    assert data[0]["leader_names"] == ["l1"]
    assert "leaders" in data[0]


def test_list_groups_with_stamp_payload(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    stamp_dir = tmp_path / "_group_stamps" / "g1" / "l1"
    stamp_dir.mkdir(parents=True, exist_ok=True)
    (stamp_dir / "seal.png").write_bytes(b"img")

    mock_engine_for_api.project_repo.list_groups = AsyncMock(return_value=[{"group_name": "g1", "leader_names": ["l1"]}])
    response = mock_app_client.get("/api/projects/groups/list")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["leaders"][0]["name"] == "l1"
    assert payload[0]["leaders"][0]["stamps"][0]["filename"] == "seal.png"


def test_list_groups_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.workspace_root = Path(".")
    mock_engine_for_api.project_repo.list_groups = AsyncMock(side_effect=RuntimeError("db down"))

    response = mock_app_client.get("/api/projects/groups/list")
    assert response.status_code == 500


def test_upsert_group(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.upsert_group = AsyncMock()
    response = mock_app_client.post("/api/projects/groups", json={"group_name": "g1", "leader_name": "l1"})
    assert response.status_code == 200


def test_upsert_group_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.upsert_group = AsyncMock(side_effect=RuntimeError("write failed"))

    response = mock_app_client.post("/api/projects/groups", json={"group_name": "g1", "leader_name": "l1"})
    assert response.status_code == 500


def test_delete_group(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.workspace_root = Path(".")
    mock_engine_for_api.project_repo.delete_group = AsyncMock()
    response = mock_app_client.delete("/api/projects/groups/g1")
    assert response.status_code == 200


def test_delete_group_removes_stamp_tree(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    mock_engine_for_api.project_repo.delete_group = AsyncMock()

    stamp_root = tmp_path / "_group_stamps" / "g1" / "leader_a"
    stamp_root.mkdir(parents=True, exist_ok=True)
    (stamp_root / "x.png").write_bytes(b"x")

    response = mock_app_client.delete("/api/projects/groups/g1")
    assert response.status_code == 200
    assert not (tmp_path / "_group_stamps" / "g1").exists()


def test_delete_group_leader(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.project_repo.workspace_root = Path(".")
    mock_engine_for_api.project_repo.remove_group_leader = AsyncMock()
    response = mock_app_client.delete("/api/projects/groups/g1/leaders/l1")
    assert response.status_code == 200


def test_delete_group_leader_removes_stamp_tree(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    mock_engine_for_api.project_repo.remove_group_leader = AsyncMock()

    stamp_dir = tmp_path / "_group_stamps" / "g1" / "l1"
    stamp_dir.mkdir(parents=True, exist_ok=True)
    (stamp_dir / "y.png").write_bytes(b"y")

    response = mock_app_client.delete("/api/projects/groups/g1/leaders/l1")
    assert response.status_code == 200
    assert not stamp_dir.exists()


def test_upload_leader_stamps_success(mock_app_client, mock_engine_for_api, tmp_path, monkeypatch):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    mock_engine_for_api.project_repo.upsert_group = AsyncMock()
    monkeypatch.setattr("backend.routers.groups.time.time", lambda: 1710000000.123)

    response = mock_app_client.post(
        "/api/projects/groups/g1/leaders/l1/stamps",
        files=[("files", ("stamp.png", b"pngdata", "image/png"))],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert len(payload["files"]) == 1

    stamp_dir = tmp_path / "_group_stamps" / "g1" / "l1"
    assert stamp_dir.exists()
    assert len(list(stamp_dir.glob("*.png"))) == 1


def test_upload_leader_stamps_rejects_non_image(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    mock_engine_for_api.project_repo.upsert_group = AsyncMock()

    response = mock_app_client.post(
        "/api/projects/groups/g1/leaders/l1/stamps",
        files=[("files", ("note.txt", b"text", "text/plain"))],
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_list_leader_stamps_invalid_component_returns_400(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path

    response = mock_app_client.get("/api/projects/groups/bad..group/leaders/l1/stamps")
    assert response.status_code == 400


def test_get_leader_stamp_file_success(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    stamp_path = tmp_path / "_group_stamps" / "g1" / "l1"
    stamp_path.mkdir(parents=True, exist_ok=True)
    expected = stamp_path / "seal.png"
    expected.write_bytes(b"abc")

    response = mock_app_client.get("/api/projects/groups/g1/leaders/l1/stamps/seal.png")
    assert response.status_code == 200
    assert response.content == b"abc"


def test_get_leader_stamp_file_not_found(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    response = mock_app_client.get("/api/projects/groups/g1/leaders/l1/stamps/missing.png")
    assert response.status_code == 404


def test_delete_leader_stamp_file_success(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    stamp_dir = tmp_path / "_group_stamps" / "g1" / "l1"
    stamp_dir.mkdir(parents=True, exist_ok=True)
    target = stamp_dir / "seal.png"
    target.write_bytes(b"abc")

    response = mock_app_client.delete("/api/projects/groups/g1/leaders/l1/stamps/seal.png")
    assert response.status_code == 200
    assert not target.exists()


def test_delete_leader_stamp_file_not_found(mock_app_client, mock_engine_for_api, tmp_path):
    mock_engine_for_api.project_repo.workspace_root = tmp_path
    response = mock_app_client.delete("/api/projects/groups/g1/leaders/l1/stamps/none.png")
    assert response.status_code == 404
