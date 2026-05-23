import pytest
import io
from pathlib import Path
from unittest.mock import AsyncMock

from backend.repositories.project_repository import ProjectArchivedError

def test_add_files(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.add_project_files = AsyncMock(return_value={"status": "added"})
    files = {"files": ("test.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    data = {"type": "raw"}
    
    response = mock_app_client.post("/api/projects/proj1/add_files", data=data, files=files)
    assert response.status_code == 200
    assert response.json() == {"status": "added"}
    mock_engine_for_api.add_project_files.assert_called_once()

def test_rotate_image(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.rotate_image = AsyncMock(return_value={"status": "rotated"})
    response = mock_app_client.post("/api/projects/proj1/rotate/f1.jpg?angle=90")
    assert response.status_code == 200


def test_rotate_image_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.rotate_image = AsyncMock(side_effect=ProjectArchivedError("locked"))
    response = mock_app_client.post("/api/projects/proj1/rotate/f1.jpg?angle=90")
    assert response.status_code == 409


def test_rotate_image_exception(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.rotate_image = AsyncMock(side_effect=RuntimeError("boom"))
    response = mock_app_client.post("/api/projects/proj1/rotate/f1.jpg?angle=90")
    assert response.status_code == 500

def test_get_raw_files(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.get_raw_files = AsyncMock(return_value=["f1.jpg", "f2.jpg"])
    response = mock_app_client.get("/api/projects/proj1/raw_files")
    assert response.status_code == 200
    assert response.json() == ["f1.jpg", "f2.jpg"]


def test_get_raw_files_exception(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.get_raw_files = AsyncMock(side_effect=RuntimeError("boom"))
    response = mock_app_client.get("/api/projects/proj1/raw_files")
    assert response.status_code == 500

def test_delete_raw_file(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_raw_file = AsyncMock(return_value={"status": "deleted"})
    response = mock_app_client.delete("/api/projects/proj1/raw_files/f1.jpg")
    assert response.status_code == 200


def test_delete_raw_file_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_raw_file = AsyncMock(side_effect=ProjectArchivedError("locked"))
    response = mock_app_client.delete("/api/projects/proj1/raw_files/f1.jpg")
    assert response.status_code == 409


def test_delete_raw_file_exception(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.delete_raw_file = AsyncMock(side_effect=RuntimeError("boom"))
    response = mock_app_client.delete("/api/projects/proj1/raw_files/f1.jpg")
    assert response.status_code == 500


def test_detect_raw_sub_rects_success(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_raw_sub_rects = AsyncMock(
        return_value=[{"points": [[0, 0], [10, 0], [10, 10], [0, 10]], "area": 100.0}]
    )

    response = mock_app_client.post("/api/projects/proj1/raw_files/raw_1.jpg/detect-sub-rects")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["filename"] == "raw_1.jpg"
    assert len(payload["rects"]) == 1


def test_detect_raw_sub_rects_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_raw_sub_rects = AsyncMock(side_effect=FileNotFoundError("missing"))
    response = mock_app_client.post("/api/projects/proj1/raw_files/raw_1.jpg/detect-sub-rects")
    assert response.status_code == 404


def test_detect_raw_sub_rects_bad_request(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_raw_sub_rects = AsyncMock(side_effect=ValueError("bad"))
    response = mock_app_client.post("/api/projects/proj1/raw_files/raw_1.jpg/detect-sub-rects")
    assert response.status_code == 400


def test_detect_raw_sub_rects_exception(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.detect_raw_sub_rects = AsyncMock(side_effect=RuntimeError("boom"))
    response = mock_app_client.post("/api/projects/proj1/raw_files/raw_1.jpg/detect-sub-rects")
    assert response.status_code == 500


def test_apply_raw_resplit_success(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_raw_resplit = AsyncMock(
        return_value={"status": "resplit_applied", "new_job_ids": ["n1"]}
    )

    response = mock_app_client.post(
        "/api/projects/proj1/raw_files/raw_1.jpg/apply-resplit",
        json={
            "sub_rects": [
                {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resplit_applied"


def test_apply_raw_resplit_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_raw_resplit = AsyncMock(side_effect=ProjectArchivedError("locked"))

    response = mock_app_client.post(
        "/api/projects/proj1/raw_files/raw_1.jpg/apply-resplit",
        json={
            "sub_rects": [
                {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
            ]
        },
    )
    assert response.status_code == 409


def test_apply_raw_resplit_not_found(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_raw_resplit = AsyncMock(side_effect=FileNotFoundError("missing"))
    response = mock_app_client.post(
        "/api/projects/proj1/raw_files/raw_1.jpg/apply-resplit",
        json={"sub_rects": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
    )
    assert response.status_code == 404


def test_apply_raw_resplit_bad_request(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_raw_resplit = AsyncMock(side_effect=ValueError("bad"))
    response = mock_app_client.post(
        "/api/projects/proj1/raw_files/raw_1.jpg/apply-resplit",
        json={"sub_rects": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
    )
    assert response.status_code == 400


def test_apply_raw_resplit_exception(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.apply_raw_resplit = AsyncMock(side_effect=RuntimeError("boom"))
    response = mock_app_client.post(
        "/api/projects/proj1/raw_files/raw_1.jpg/apply-resplit",
        json={"sub_rects": [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}]},
    )
    assert response.status_code == 500


def test_get_raw_preview_matches_dotted_stem_without_extension(mock_app_client, mock_engine_for_api, tmp_path):
    project_root = tmp_path / "proj1"
    raw_dir = project_root / "原始輸入"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / "receipt.v1.jpg"
    raw_file.write_bytes(b"raw-bytes")

    mock_engine_for_api.project_repo._project_root.return_value = Path(project_root)
    mock_engine_for_api.cache_service.ensure_preview_cache = AsyncMock(return_value=None)

    response = mock_app_client.get("/api/projects/proj1/preview/raw/receipt.v1")
    assert response.status_code == 200


def test_get_split_preview_not_found(mock_app_client, mock_engine_for_api, tmp_path):
    project_root = tmp_path / "proj1"
    project_root.mkdir(parents=True, exist_ok=True)
    mock_engine_for_api.project_repo._project_root.return_value = Path(project_root)
    response = mock_app_client.get("/api/projects/proj1/preview/split/missing.jpg")
    assert response.status_code == 404


def test_get_raw_preview_not_found(mock_app_client, mock_engine_for_api, tmp_path):
    project_root = tmp_path / "proj1"
    (project_root / "原始輸入").mkdir(parents=True, exist_ok=True)
    mock_engine_for_api.project_repo._project_root.return_value = Path(project_root)
    response = mock_app_client.get("/api/projects/proj1/preview/raw/missing.jpg")
    assert response.status_code == 404


def test_get_split_preview_prefers_cache(mock_app_client, mock_engine_for_api, tmp_path):
    project_root = tmp_path / "proj1"
    split_dir = project_root / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    split_file = split_dir / "item.jpg"
    split_file.write_bytes(b"img")

    cache_file = project_root / "cache.jpg"
    cache_file.write_bytes(b"cache")

    mock_engine_for_api.project_repo._project_root.return_value = Path(project_root)
    mock_engine_for_api.cache_service.ensure_preview_cache = AsyncMock(
        return_value={"path": str(cache_file), "media_type": "image/jpeg"}
    )

    response = mock_app_client.get("/api/projects/proj1/preview/split/item.jpg")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/jpeg")


def test_get_raw_preview_prefers_cache(mock_app_client, mock_engine_for_api, tmp_path):
    project_root = tmp_path / "proj1"
    raw_dir = project_root / "原始輸入"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_file = raw_dir / "item.jpg"
    raw_file.write_bytes(b"img")

    cache_file = project_root / "cache_raw.jpg"
    cache_file.write_bytes(b"cache")

    mock_engine_for_api.project_repo._project_root.return_value = Path(project_root)
    mock_engine_for_api.cache_service.ensure_preview_cache = AsyncMock(
        return_value={"path": str(cache_file), "media_type": "image/jpeg"}
    )

    response = mock_app_client.get("/api/projects/proj1/preview/raw/item.jpg")
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/jpeg")


def test_add_files_archived(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.add_project_files = AsyncMock(side_effect=ProjectArchivedError("Project proj1 is archived and read-only"))
    files = {"files": ("test.jpg", io.BytesIO(b"fake image data"), "image/jpeg")}
    data = {"type": "raw"}

    response = mock_app_client.post("/api/projects/proj1/add_files", data=data, files=files)
    assert response.status_code == 409
