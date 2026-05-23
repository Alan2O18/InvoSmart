from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import numpy as np

from backend.engine.image_service import ImageService


def _make_service(tmp_path):
    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={}, file_service=None)
    service = ImageService(project_repo, MagicMock(), engine)
    return service, project_repo, engine


def test_cache_service_missing_raises_runtime_error(tmp_path):
    service, _, _ = _make_service(tmp_path)
    with pytest.raises(RuntimeError, match="CacheService is not configured"):
        service._cache_service()


@pytest.mark.asyncio
async def test_preview_delegate_and_cleanup_delegate(tmp_path):
    service, _, engine = _make_service(tmp_path)
    cache = MagicMock()
    cache.ensure_preview_cache = AsyncMock(return_value={"path": "x", "media_type": "image/jpeg"})
    cache.cleanup_project_cache = AsyncMock(return_value={"deleted_files": 1})
    cache.cleanup_all_projects_cache = AsyncMock(return_value={"status": "completed"})
    cache.invalidate_preview_cache = MagicMock()
    engine.cache_service = cache

    preview = await service.ensure_preview_cache("p", "img.jpg", max_width=200)
    cleanup_one = await service.cleanup_project_cache("p", max_age_hours=2)
    cleanup_all = await service.cleanup_all_projects_cache(max_age_hours=3)
    service.invalidate_preview_cache("p", "img.jpg")

    assert preview["path"] == "x"
    assert cleanup_one["deleted_files"] == 1
    assert cleanup_all["status"] == "completed"
    cache.invalidate_preview_cache.assert_called_once()


def test_engine_config_and_thumb_width(tmp_path):
    service, _, engine = _make_service(tmp_path)
    assert service._engine_config() == {}
    assert service._thumb_max_width() == 800

    engine.config = {"voucher_settings": {"thumb_max_width": 1234}}
    assert service._thumb_max_width() == 1234


def test_deferred_gc_queue_initialization_and_reuse(tmp_path):
    service, _, engine = _make_service(tmp_path)

    queue1 = service._deferred_gc_queue()
    queue2 = service._deferred_gc_queue()

    assert isinstance(queue1, list)
    assert queue1 is queue2
    assert getattr(engine, "_deferred_file_gc") is queue1


def test_resolve_project_path_with_file_service(tmp_path):
    service, _, engine = _make_service(tmp_path)
    fake_file_service = MagicMock()
    fake_file_service._resolve_project_path.return_value = tmp_path / "a.jpg"
    engine.file_service = fake_file_service

    out = service._resolve_project_path(tmp_path, "a.jpg", preferred_dir="分割發票")
    assert out == tmp_path / "a.jpg"


def test_resolve_project_path_without_file_service(tmp_path):
    service, _, _ = _make_service(tmp_path)
    rel_file = tmp_path / "分割發票"
    rel_file.mkdir(parents=True, exist_ok=True)
    expected = rel_file / "x.jpg"
    expected.write_bytes(b"x")

    out = service._resolve_project_path(tmp_path, "x.jpg", preferred_dir="分割發票")
    assert out.resolve(strict=False) == expected.resolve(strict=False)

    fallback = service._resolve_project_path(tmp_path, "missing.jpg", preferred_dir="分割發票")
    assert fallback is not None


def test_is_within_root_and_safe_delete_file(tmp_path):
    service, _, _ = _make_service(tmp_path)

    inside = tmp_path / "f.txt"
    inside.write_text("ok", encoding="utf-8")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("out", encoding="utf-8")

    assert service._is_within_root(tmp_path, inside)
    assert not service._is_within_root(tmp_path, outside)

    deleted_files, missing_files = [], []
    service._safe_delete_file(tmp_path, inside, deleted_files, missing_files)
    assert not inside.exists()
    assert deleted_files

    deleted_files, missing_files = [], []
    service._safe_delete_file(tmp_path, tmp_path / "none.txt", deleted_files, missing_files)
    assert missing_files


@pytest.mark.asyncio
async def test_flush_deferred_gc_empty_queue(tmp_path):
    service, _, _ = _make_service(tmp_path)
    result = await service.flush_deferred_gc("proj")
    assert result == {"deleted_files": [], "missing_files": [], "kept_referenced": []}


@pytest.mark.asyncio
async def test_flush_deferred_gc_mixed_referenced_and_deleted(tmp_path):
    service, _, engine = _make_service(tmp_path)

    split_dir = tmp_path / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    kept = split_dir / "kept.jpg"
    gone = split_dir / "gone.jpg"
    kept.write_bytes(b"k")
    gone.write_bytes(b"g")

    engine._deferred_file_gc = [
        {"project_id": "proj", "path": str(kept.resolve(strict=False))},
        {"project_id": "proj", "path": str(gone.resolve(strict=False))},
    ]

    job_repo = MagicMock()
    job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "j1", "image_path": str(kept)}])
    engine.get_job_repo = MagicMock(return_value=job_repo)

    result = await service.flush_deferred_gc("proj")

    assert str(kept.resolve(strict=False)) in result["kept_referenced"]
    assert str(gone.resolve(strict=False)) in result["deleted_files"]
    assert not gone.exists()


@pytest.mark.asyncio
async def test_delete_job_files_job_not_found(tmp_path):
    service, _, engine = _make_service(tmp_path)
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value=None)
    engine.get_job_repo = MagicMock(return_value=job_repo)

    result = await service.delete_job_files("proj", "missing")
    assert result["job_found"] is False


@pytest.mark.asyncio
async def test_optimize_jxl_storage_no_jobs(tmp_path):
    service, _, engine = _make_service(tmp_path)
    job_repo = MagicMock()
    job_repo.list_jobs = AsyncMock(return_value=[])
    engine.get_job_repo = MagicMock(return_value=job_repo)

    result = await service.optimize_jxl_storage("proj")
    assert result["optimized_jobs"] == 0
    assert result["skipped_jobs"] == 0


@pytest.mark.asyncio
async def test_optimize_jxl_storage_jxl_unavailable(tmp_path):
    service, _, engine = _make_service(tmp_path)
    engine.config = {"processing_settings": {}}
    job_repo = MagicMock()
    job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "j1", "image_path": "a.jpg"}])
    engine.get_job_repo = MagicMock(return_value=job_repo)

    with patch("backend.engine.image_service.ImageCodecAdapter.resolve_archival_extension", return_value="jpg"):
        result = await service.optimize_jxl_storage("proj")

    assert result["reason"] == "jxl_unavailable"
    assert result["skipped_jobs"] == 1





@pytest.mark.asyncio
async def test_rotate_image_missing_file(tmp_path):
    service, _, _ = _make_service(tmp_path)

    with pytest.raises(FileNotFoundError):
        await service.rotate_image("proj", "missing.jpg", angle=90)


@pytest.mark.asyncio
async def test_rotate_image_read_fail(tmp_path):
    service, _, _ = _make_service(tmp_path)
    split_dir = tmp_path / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    img_path = split_dir / "a.jpg"
    img_path.write_bytes(b"x")

    with patch("backend.engine.image_service.utils.cv_imread_chinese", return_value=None):
        with pytest.raises(ValueError, match="Failed to read image"):
            await service.rotate_image("proj", "a.jpg", angle=90)


@pytest.mark.asyncio
async def test_rotate_image_write_fail(tmp_path):
    service, _, _ = _make_service(tmp_path)
    split_dir = tmp_path / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    img_path = split_dir / "a.jpg"
    img_path.write_bytes(b"x")

    with patch("backend.engine.image_service.utils.cv_imread_chinese", return_value="img"), patch(
        "backend.engine.image_service.cv2.rotate", return_value="img_rot"
    ), patch("backend.engine.image_service.utils.cv_imwrite_chinese", return_value=False):
        with pytest.raises(OSError):
            await service.rotate_image("proj", "a.jpg", angle=90)


@pytest.mark.asyncio
async def test_rotate_image_success_resets_matching_jobs(tmp_path):
    service, _, engine = _make_service(tmp_path)
    split_dir = tmp_path / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    img_path = split_dir / "a.jpg"
    img_path.write_bytes(b"x")

    job_repo = MagicMock()
    job_repo.list_jobs = AsyncMock(
        return_value=[
            {"job_id": "j1", "image_path": str(img_path)},
            {"job_id": "j2", "image_path": str(split_dir / "other.jpg")},
        ]
    )
    job_repo.delete_invoice_items = AsyncMock()
    job_repo.update_job = AsyncMock()
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service.invalidate_preview_cache = MagicMock()
    service.ensure_preview_cache = AsyncMock(side_effect=RuntimeError("preview fail"))

    with patch("backend.engine.image_service.utils.cv_imread_chinese", return_value="img"), patch(
        "backend.engine.image_service.cv2.rotate", return_value="img_rot"
    ), patch("backend.engine.image_service.utils.cv_imwrite_chinese", return_value=True):
        out = await service.rotate_image("proj", "a.jpg", angle=90)

    assert out["status"] == "rotated"
    assert out["reset_jobs"] == ["j1"]
    job_repo.delete_invoice_items.assert_awaited_once_with("j1")
    job_repo.update_job.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_job_files_handles_shared_image(tmp_path):
    service, _, engine = _make_service(tmp_path)
    split_dir = tmp_path / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    shared = split_dir / "shared.jpg"
    shared.write_bytes(b"x")

    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(
        return_value={
            "job_id": "j1",
            "image_path": str(shared),
            "source_pdf_path": None,
            "compressed_pdf_path": None,
            "preview_cache_path": None,
        }
    )
    job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "j2", "image_path": str(shared)}])
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service.invalidate_preview_cache = MagicMock()

    out = await service.delete_job_files("proj", "j1")

    assert out["job_found"] is True
    assert out["skipped_shared_files"]
    service.invalidate_preview_cache.assert_not_called()


@pytest.mark.asyncio
async def test_delete_job_files_deletes_non_shared_extra_files(tmp_path):
    service, _, engine = _make_service(tmp_path)
    split_dir = tmp_path / "分割發票"
    raw_dir = tmp_path / "原始輸入"
    out_dir = tmp_path / "輸出結果"
    split_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    image = split_dir / "img.jpg"
    source_pdf = raw_dir / "s.pdf"
    compressed_pdf = out_dir / "c.pdf"
    image.write_bytes(b"x")
    source_pdf.write_bytes(b"x")
    compressed_pdf.write_bytes(b"x")

    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(
        return_value={
            "job_id": "j1",
            "image_path": str(image),
            "source_pdf_path": str(source_pdf),
            "compressed_pdf_path": str(compressed_pdf),
            "preview_cache_path": None,
        }
    )
    job_repo.list_jobs = AsyncMock(return_value=[])
    engine.get_job_repo = MagicMock(return_value=job_repo)
    service.invalidate_preview_cache = MagicMock()

    out = await service.delete_job_files("proj", "j1")

    assert out["job_found"] is True
    assert out["deferred_files"]
    assert out["deleted_files"]
    assert not source_pdf.exists()
    assert not compressed_pdf.exists()


@pytest.mark.asyncio
async def test_add_project_files_invalid_type_raises_value_error(tmp_path):
    service, _, _ = _make_service(tmp_path)

    with pytest.raises(ValueError, match="Invalid type"):
        await service.add_project_files("proj", [], type="unknown")
