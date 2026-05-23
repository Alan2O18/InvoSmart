from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import numpy as np

from backend.engine.image_service import ImageService
from backend.engine.resplit_service import ResplitService


def _make_service(tmp_path):
    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={}, file_service=None)
    image_service = ImageService(project_repo, MagicMock(), engine)
    resplit_service = ResplitService(project_repo, MagicMock(), engine, image_service)
    return resplit_service, project_repo, engine, image_service


@pytest.mark.asyncio
async def test_detect_job_sub_rects_job_not_found(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value=None)
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with pytest.raises(ValueError, match="Job not found"):
        await service.detect_job_sub_rects("proj", "j0")


@pytest.mark.asyncio
async def test_detect_raw_sub_rects_not_found(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=None):
        with pytest.raises(FileNotFoundError):
            await service.detect_raw_sub_rects("proj", "no.jpg")


@pytest.mark.asyncio
async def test_apply_job_resplit_empty_sub_rects(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError, match="sub_rects cannot be empty"):
        await service.apply_job_resplit("proj", "j1", [])


@pytest.mark.asyncio
async def test_apply_raw_resplit_empty_sub_rects(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    with pytest.raises(ValueError, match="sub_rects cannot be empty"):
        await service.apply_raw_resplit("proj", "raw.jpg", [])


@pytest.mark.asyncio
async def test_detect_job_sub_rects_source_missing(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "x.jpg"})
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=None):
        with pytest.raises(FileNotFoundError):
            await service.detect_job_sub_rects("proj", "j1")


@pytest.mark.asyncio
async def test_detect_job_sub_rects_read_fail(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")

    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": str(src)})
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value=None
    ):
        with pytest.raises(ValueError):
            await service.detect_job_sub_rects("proj", "j1")


@pytest.mark.asyncio
async def test_detect_job_sub_rects_success(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")

    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": str(src)})
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service.receipt_splitter.detect_only = MagicMock(return_value=[{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value="img"
    ):
        out = await service.detect_job_sub_rects("proj", "j1")

    assert len(out) == 1


@pytest.mark.asyncio
async def test_detect_raw_sub_rects_read_fail(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"x")

    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value=None
    ):
        with pytest.raises(ValueError):
            await service.detect_raw_sub_rects("proj", "raw.jpg")


@pytest.mark.asyncio
async def test_detect_raw_sub_rects_success(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"x")
    service.receipt_splitter.detect_only = MagicMock(return_value=[{"ok": True}])

    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value=np.zeros((100, 100, 3), dtype=np.uint8)
    ):
        out = await service.detect_raw_sub_rects("proj", "raw.jpg")

    assert out == {"rects": [{"ok": True}], "full_width": 100, "full_height": 100}


@pytest.mark.asyncio
async def test_apply_job_resplit_job_not_found(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value=None)
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with pytest.raises(ValueError, match="Job not found"):
        await service.apply_job_resplit("proj", "j1", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_job_resplit_source_missing(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "x.jpg"})
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=None):
        with pytest.raises(FileNotFoundError):
            await service.apply_job_resplit("proj", "j1", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_job_resplit_read_fail(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": str(src)})
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value=None
    ):
        with pytest.raises(ValueError):
            await service.apply_job_resplit("proj", "j1", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_job_resplit_no_generated_jobs(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": str(src)})
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service._create_resplit_jobs_from_source = AsyncMock(return_value=([], []))

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value="img"
    ):
        with pytest.raises(ValueError, match="No valid sub-rect"):
            await service.apply_job_resplit("proj", "j1", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_job_resplit_success(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": str(src)})
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service._create_resplit_jobs_from_source = AsyncMock(return_value=(["n1"], ["p1"]))
    engine.delete_job = AsyncMock(return_value={"status": "deleted"})

    with patch("backend.engine.resplit_service.resolve_resplit_raw_source", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value="img"
    ):
        out = await service.apply_job_resplit("proj", "j1", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])

    assert out["status"] == "resplit_applied"
    assert out["new_job_ids"] == ["n1"]


@pytest.mark.asyncio
async def test_apply_raw_resplit_source_missing(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=None):
        with pytest.raises(FileNotFoundError):
            await service.apply_raw_resplit("proj", "raw.jpg", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_raw_resplit_read_fail(tmp_path):
    service, _, _, _ = _make_service(tmp_path)
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"x")

    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value=None
    ):
        with pytest.raises(ValueError):
            await service.apply_raw_resplit("proj", "raw.jpg", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_raw_resplit_no_generated_jobs(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"x")
    job_repo = MagicMock()
    job_repo.list_jobs = AsyncMock(return_value=[])
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service._create_resplit_jobs_from_source = AsyncMock(return_value=([], []))

    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value="img"
    ):
        with pytest.raises(ValueError, match="No valid sub-rect"):
            await service.apply_raw_resplit("proj", "raw.jpg", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])


@pytest.mark.asyncio
async def test_apply_raw_resplit_success(tmp_path):
    service, _, engine, _ = _make_service(tmp_path)
    src = tmp_path / "raw.jpg"
    src.write_bytes(b"x")
    job_repo = MagicMock()
    job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "o1", "image_path": "raw.jpg"}])
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service._create_resplit_jobs_from_source = AsyncMock(return_value=(["n1"], ["p1"]))
    engine.delete_job = AsyncMock(return_value={"status": "deleted"})

    with patch("backend.engine.resplit_service.resolve_raw_source_by_filename", return_value=src), patch(
        "backend.engine.resplit_service.utils.cv_imread_chinese", return_value="img"
    ), patch("backend.engine.resplit_service.job_matches_raw_filename", return_value=True):
        out = await service.apply_raw_resplit("proj", "raw.jpg", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])

    assert out["status"] == "resplit_applied"
    assert out["new_job_ids"] == ["n1"]
