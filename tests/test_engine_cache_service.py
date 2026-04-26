import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.engine.cache_service import CacheService


@pytest.mark.asyncio
async def test_ensure_preview_cache_returns_none_for_missing_source(tmp_path):
    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={})
    service = CacheService(project_repo, engine)

    result = await service.ensure_preview_cache("proj", str(tmp_path / "missing.jpg"))
    assert result is None


@pytest.mark.asyncio
async def test_ensure_preview_cache_generates_then_hits_cache(tmp_path):
    source = tmp_path / "sample.jpg"
    Image.new("RGB", (120, 60), color=(100, 100, 100)).save(source)

    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={})
    service = CacheService(project_repo, engine)

    def fake_render(src, dst, pil_format, max_width):
        Image.new("RGB", (50, 25), color=(1, 2, 3)).save(dst, format="JPEG")

    with patch.object(service, "_get_preview_format", return_value=("JPEG", "jpg", "image/jpeg")), patch.object(
        CacheService, "_render_preview", side_effect=fake_render
    ):
        first = await service.ensure_preview_cache("proj", str(source), max_width=90)
        second = await service.ensure_preview_cache("proj", str(source), max_width=90)

    assert first["cache_hit"] is False
    assert os.path.exists(first["path"])
    assert second["cache_hit"] is True
    assert second["path"] == first["path"]


def test_get_preview_format_falls_back_to_jpeg_when_avif_webp_unavailable():
    project_repo = MagicMock()
    engine = SimpleNamespace(config={"processing_settings": {"preview_formats": ["avif", "webp"]}})
    service = CacheService(project_repo, engine)

    with patch("backend.engine.cache_service.features.check", return_value=False):
        result = service._get_preview_format()

    assert result == ("JPEG", "jpg", "image/jpeg")


def test_invalidate_preview_cache_removes_matching_stem(tmp_path):
    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={})
    service = CacheService(project_repo, engine)

    cache_dir = tmp_path / "快取影像" / "voucher_preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    a = cache_dir / "invoice_123.jpg"
    b = cache_dir / "invoice_456.jpg"
    c = cache_dir / "other_789.jpg"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    c.write_bytes(b"c")

    service.invalidate_preview_cache("proj", str(tmp_path / "invoice.png"))

    assert not a.exists()
    assert not b.exists()
    assert c.exists()


@pytest.mark.asyncio
async def test_cleanup_project_cache_handles_missing_cache_root(tmp_path):
    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={})
    service = CacheService(project_repo, engine)

    result = await service.cleanup_project_cache("proj", max_age_hours=1)

    assert result["missing_cache_root"] is True
    assert result["deleted_files"] == 0


@pytest.mark.asyncio
async def test_cleanup_project_cache_deletes_old_files_only(tmp_path):
    project_repo = MagicMock()
    project_repo._project_root.return_value = tmp_path
    engine = SimpleNamespace(config={})
    service = CacheService(project_repo, engine)

    cache_root = tmp_path / "快取影像" / "voucher_preview"
    cache_root.mkdir(parents=True, exist_ok=True)
    old_file = cache_root / "old.jpg"
    new_file = cache_root / "new.jpg"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    now = time.time()
    os.utime(old_file, (now - 10 * 3600, now - 10 * 3600))
    os.utime(new_file, (now, now))

    result = await service.cleanup_project_cache("proj", max_age_hours=1)

    assert result["missing_cache_root"] is False
    assert result["deleted_files"] == 1
    assert not old_file.exists()
    assert new_file.exists()


@pytest.mark.asyncio
async def test_cleanup_all_projects_cache_aggregates_results(tmp_path):
    project_repo = MagicMock()
    project_repo.list_projects = AsyncMock(
        return_value=[
            {"project_id": "p1"},
            {"id": "p2"},
            {"name": "skip_no_id"},
        ]
    )
    engine = SimpleNamespace(config={})
    service = CacheService(project_repo, engine)

    service.cleanup_project_cache = AsyncMock(side_effect=[
        {"project_id": "p1", "deleted_files": 2},
        {"project_id": "p2", "deleted_files": 3},
    ])

    result = await service.cleanup_all_projects_cache(max_age_hours=2)

    assert result["status"] == "completed"
    assert result["projects"] == 2
    assert result["deleted_files"] == 5
    assert len(result["details"]) == 2
