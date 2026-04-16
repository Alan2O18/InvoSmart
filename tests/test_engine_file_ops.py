import pytest
import cv2
import numpy as np
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
from backend.engine.file_ops import FileOps
from backend.engine.file_service import FileService
from backend.utils import utils

@pytest.fixture
def mock_dependencies(tmp_path):
    project_repo = MagicMock()
    project_root = tmp_path / "proj1"
    project_root.mkdir()
    project_repo._project_root.return_value = project_root
    project_repo.update_project_status = AsyncMock()
    project_repo.list_projects = AsyncMock(return_value=[{"project_id": "proj1"}])
    
    receipt_splitter = MagicMock()
    # Mock splitting returns two dummy image arrays
    dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
    receipt_splitter.split.return_value = [dummy_img, dummy_img]
    
    engine_ref = AsyncMock()
    engine_ref.enqueue_job = AsyncMock()
    engine_ref.delete_job = AsyncMock(return_value={"status": "deleted"})
    job_repo = AsyncMock()
    job_repo.list_jobs = AsyncMock(return_value=[])
    job_repo.update_job = AsyncMock(return_value=True)
    engine_ref.get_job_repo = MagicMock(return_value=job_repo)
    engine_ref.file_service = FileService(project_repo)
    
    return project_repo, receipt_splitter, engine_ref, project_root

@pytest.fixture
def file_ops(mock_dependencies):
    repo, splitter, engine, root = mock_dependencies
    return FileOps(repo, splitter, engine)

@pytest.mark.asyncio
async def test_run_splitting_creates_files(file_ops, mock_dependencies):
    repo, splitter, engine, root = mock_dependencies
    
    # Setup raw files
    raw_dir = root / "原始輸入"
    raw_dir.mkdir()
    (raw_dir / "test.jpg").touch()
    
    # Mock OpenCV utils
    with patch("backend.engine.file_ops.utils.cv_imread_chinese") as mock_imread, \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese") as mock_imwrite:
        
        mock_imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        
        result = await file_ops.run_splitting("proj1")
        
        assert result["status"] == "split_completed"
        repo.update_project_status.assert_called_once_with("proj1", "SPLIT")
        assert mock_imwrite.call_count == 2
        assert engine.enqueue_job.call_count == 2

@pytest.mark.asyncio
async def test_run_splitting_missing_folder(file_ops):
    # Tests early return when 原始輸入 is missing
    result = await file_ops.run_splitting("proj1")
    assert result["status"] == "split_completed"

def test_get_raw_files(file_ops, mock_dependencies):
    _, _, _, root = mock_dependencies
    raw_dir = root / "原始輸入"
    raw_dir.mkdir()
    (raw_dir / "test1.jpg").touch()
    (raw_dir / "ignore.txt").touch()
    
    split_dir = root / "分割發票"
    split_dir.mkdir()
    (split_dir / "test1_split_0_123.jpg").touch()
    
    files = file_ops.get_raw_files("proj1")
    
    assert len(files) == 1
    assert files[0]["filename"] == "test1.jpg"
    assert files[0]["split_count"] == 1

def test_get_raw_files_missing_folder(file_ops):
    files = file_ops.get_raw_files("proj1")
    assert files == []

@pytest.mark.asyncio
async def test_add_project_files_raw(file_ops, mock_dependencies, tmp_path):
    repo, _, _, root = mock_dependencies
    upload_file = tmp_path / "upload.jpg"
    upload_file.touch()

    dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
    dest_path = root / "原始輸入" / "upload.jxl"

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=dummy_img), \
         patch("backend.engine.file_ops.asyncio.to_thread", side_effect=fake_to_thread), \
         patch.object(file_ops, '_codec_adapter') as mock_codec_factory:
        mock_codec = MagicMock()
        mock_codec.build_archival_path.return_value = dest_path
        mock_codec.write_archival_image.return_value = dest_path
        mock_codec_factory.return_value = mock_codec

        result = await file_ops.add_project_files("proj1", [str(upload_file)], type="raw")

    assert result["status"] == "added"
    assert (root / "原始輸入").exists()
    repo.set_conversion_total.assert_called_once()
    repo.inc_conversion_progress.assert_called_once()

@pytest.mark.asyncio
async def test_add_project_files_split_enqueues(file_ops, mock_dependencies, tmp_path):
    _, _, engine, root = mock_dependencies
    upload_file = tmp_path / "split_upload.jpg"
    upload_file.touch()

    dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
    dest_path = root / "分割發票" / "split_upload_split_manual_123_abc.jxl"

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=dummy_img), \
         patch("backend.engine.file_ops.asyncio.to_thread", side_effect=fake_to_thread), \
         patch.object(file_ops, '_codec_adapter') as mock_codec_factory:
        mock_codec = MagicMock()
        mock_codec.build_archival_path.return_value = dest_path
        mock_codec.write_archival_image.return_value = dest_path
        mock_codec_factory.return_value = mock_codec

        result = await file_ops.add_project_files("proj1", [str(upload_file)], type="split")

    assert result["status"] == "added"
    engine.enqueue_job.assert_called_once()

@pytest.mark.asyncio
async def test_rotate_image(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    split_dir = root / "分割發票"
    split_dir.mkdir()
    (split_dir / "sample.jpg").touch()

    image_abs = str((split_dir / "sample.jpg").resolve())
    engine.get_job_repo.return_value.list_jobs = AsyncMock(return_value=[
        {"job_id": "job-1", "image_path": image_abs},
    ])
    
    dummy_img = np.zeros((10, 20, 3), dtype=np.uint8)
    
    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=dummy_img), \
         patch("backend.engine.file_ops.cv2.rotate", return_value=dummy_img) as mock_rotate, \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese") as mock_imwrite:
        
        result = await file_ops.rotate_image("proj1", "sample.jpg", angle=90)
        
        assert result["status"] == "rotated"
        assert result["reset_jobs"] == ["job-1"]
        mock_rotate.assert_called_once_with(dummy_img, cv2.ROTATE_90_CLOCKWISE)
        mock_imwrite.assert_called_once()
        engine.get_job_repo.return_value.update_job.assert_called_once_with(
            "job-1",
            status="ready",
            vlm_result_json=None,
            manual_json_text=None,
            validation_json=None,
            vlm_stats=None,
            qr_verified=0,
        )


@pytest.mark.asyncio
async def test_rotate_image_raises_when_write_fails(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    split_dir = root / "分割發票"
    split_dir.mkdir()
    (split_dir / "sample.jpg").touch()

    image_abs = str((split_dir / "sample.jpg").resolve())
    engine.get_job_repo.return_value.list_jobs = AsyncMock(return_value=[
        {"job_id": "job-1", "image_path": image_abs},
    ])

    dummy_img = np.zeros((10, 20, 3), dtype=np.uint8)
    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=dummy_img), \
         patch("backend.engine.file_ops.cv2.rotate", return_value=dummy_img), \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese", return_value=False):
        with pytest.raises(IOError, match="Failed to write rotated image"):
            await file_ops.rotate_image("proj1", "sample.jpg", angle=90)

    engine.get_job_repo.return_value.update_job.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_preview_cache_creates_file(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    engine.config = {
        "processing_settings": {"preview_formats": ["webp"]},
        "voucher_settings": {"thumb_max_width": 120},
    }

    split_dir = root / "分割發票"
    split_dir.mkdir(exist_ok=True)
    img_path = split_dir / "preview_test.jpg"
    image = np.full((80, 160, 3), 200, dtype=np.uint8)
    utils.cv_imwrite_chinese(str(img_path), image)

    preview = await file_ops.ensure_preview_cache("proj1", str(img_path), max_width=120)

    assert preview is not None
    assert preview["media_type"] in ("image/webp", "image/avif", "image/jpeg")
    assert Path(preview["path"]).exists()


@pytest.mark.asyncio
async def test_rotate_image_rebuilds_preview_cache(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    engine.config = {
        "processing_settings": {"preview_formats": ["webp"]},
        "voucher_settings": {"thumb_max_width": 120},
    }

    split_dir = root / "分割發票"
    split_dir.mkdir(exist_ok=True)
    img_path = split_dir / "rotate_preview.jpg"
    utils.cv_imwrite_chinese(str(img_path), np.zeros((40, 40, 3), dtype=np.uint8))

    preview_before = await file_ops.ensure_preview_cache("proj1", str(img_path), max_width=120)
    assert preview_before is not None
    assert Path(preview_before["path"]).exists()

    image_abs = str(img_path.resolve())
    engine.get_job_repo.return_value.list_jobs = AsyncMock(return_value=[
        {"job_id": "job-1", "image_path": image_abs},
    ])

    dummy_img = np.zeros((40, 40, 3), dtype=np.uint8)
    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=dummy_img), \
         patch("backend.engine.file_ops.cv2.rotate", return_value=dummy_img), \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese"):
        result = await file_ops.rotate_image("proj1", "rotate_preview.jpg", angle=90)

    assert result["status"] == "rotated"
    preview_after = await file_ops.ensure_preview_cache("proj1", str(img_path), max_width=120)
    assert preview_after is not None
    assert Path(preview_after["path"]).exists()


@pytest.mark.asyncio
async def test_split_stores_asset_metadata_on_job(file_ops, mock_dependencies):
    """_prepare_tasks must call update_job with source_format and preview_cache_path."""
    repo, splitter, engine, root = mock_dependencies
    engine.config = {
        "processing_settings": {"archival_format": "jpg"},
        "voucher_settings": {"thumb_max_width": 120},
    }
    engine.enqueue_job = AsyncMock(return_value="job-meta-1")

    raw_dir = root / "原始輸入"
    raw_dir.mkdir()
    (raw_dir / "test.jpg").touch()

    with patch("backend.engine.file_ops.utils.cv_imread_chinese") as mock_imread, \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese", return_value=True):
        mock_imread.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        await file_ops.run_splitting("proj1")

    job_repo = engine.get_job_repo.return_value
    calls = job_repo.update_job.call_args_list
    # Should have been called for each split image (2 from the fixture splitter)
    assert len(calls) >= 2
    for call in calls:
        kwargs = call.kwargs if call.kwargs else {}
        # update_job(job_id, source_format=..., preview_cache_path=...)
        assert "source_format" in kwargs, f"source_format missing in call: {call}"
        assert "preview_cache_path" in kwargs, f"preview_cache_path missing in call: {call}"
        assert kwargs["source_format"] in ("jpg", "jpeg", "png", "webp", "jxl")


@pytest.mark.asyncio
async def test_run_splitting_uses_unique_output_names_for_same_stem(file_ops, mock_dependencies):
    """Ensure split output names do not collide when raw files share the same stem."""
    _, splitter, engine, root = mock_dependencies
    splitter.split.return_value = [np.zeros((10, 10, 3), dtype=np.uint8)]

    raw_dir = root / "原始輸入"
    raw_dir.mkdir()
    (raw_dir / "dup.jpg").touch()
    (raw_dir / "dup.png").touch()

    written_paths = []

    def _capture_write(path, _image):
        written_paths.append(Path(path).name)
        return True

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=np.zeros((50, 50, 3), dtype=np.uint8)), \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese", side_effect=_capture_write), \
         patch("backend.engine.file_ops.time.time_ns", return_value=1234567890), \
         patch("backend.engine.file_ops.uuid.uuid4") as mock_uuid4:
        mock_uuid4.side_effect = [
            MagicMock(hex="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            MagicMock(hex="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"),
        ]
        await file_ops.run_splitting("proj1")

    # One archival write for each raw file. Paths must remain unique even with fixed timestamp.
    archival_writes = [name for name in written_paths if "_split_" in name]
    assert len(archival_writes) == 2
    assert len(set(archival_writes)) == 2


@pytest.mark.asyncio
async def test_run_splitting_accepts_jxl_sources(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies

    raw_dir = root / "原始輸入"
    raw_dir.mkdir()
    (raw_dir / "receipt.jxl").touch()

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=np.zeros((32, 32, 3), dtype=np.uint8)) as mock_imread, \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese", return_value=True):
        result = await file_ops.run_splitting("proj1")

    assert result["status"] == "split_completed"
    assert any(Path(call.args[0]).suffix.lower() == ".jxl" for call in mock_imread.call_args_list)
    assert engine.enqueue_job.call_count == 2


def test_render_preview_uses_codec_adapter_for_jxl(tmp_path):
    source = tmp_path / "preview.jxl"
    source.write_bytes(b"fake-jxl")
    cache = tmp_path / "preview.jpg"

    with patch(
        "backend.engine.file_ops.ImageCodecAdapter.read_image_pil",
        return_value=Image.new("RGB", (200, 100), color=(150, 150, 150)),
    ) as mock_read:
        FileOps._render_preview(str(source), str(cache), "JPEG", 120)

    mock_read.assert_called_once_with(str(source))
    assert cache.exists()


@pytest.mark.asyncio
async def test_cleanup_project_cache_removes_stale_files(file_ops, mock_dependencies):
    _, _, _, root = mock_dependencies
    cache_file = root / "快取影像" / "voucher_preview" / "stale.webp"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"old")

    stale_ts = 1
    os.utime(cache_file, (stale_ts, stale_ts))

    result = await file_ops.cleanup_project_cache("proj1", max_age_hours=24)

    assert result["deleted_files"] == 1
    assert not cache_file.exists()


@pytest.mark.asyncio
async def test_delete_job_files_removes_assets(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    split_file = root / "分割發票" / "to_delete.jpg"
    split_file.parent.mkdir(parents=True, exist_ok=True)
    split_file.write_bytes(b"img")

    preview_file = root / "快取影像" / "voucher_preview" / "to_delete_cache.jpg"
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    preview_file.write_bytes(b"preview")

    engine.get_job_repo.return_value.get_job = AsyncMock(
        return_value={
            "job_id": "job-1",
            "image_path": str(split_file),
            "preview_cache_path": str(preview_file),
            "source_pdf_path": None,
            "compressed_pdf_path": None,
        }
    )

    result = await file_ops.delete_job_files("proj1", "job-1")

    assert result["job_found"] is True
    assert result["deferred_files"]
    assert split_file.exists()
    assert not preview_file.exists()

    gc_result = await file_ops.flush_deferred_gc("proj1")
    assert gc_result["deleted_files"]
    assert not split_file.exists()


@pytest.mark.asyncio
async def test_delete_job_files_skips_shared_image_path(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    split_file = root / "分割發票" / "shared.jpg"
    split_file.parent.mkdir(parents=True, exist_ok=True)
    split_file.write_bytes(b"img")

    engine.get_job_repo.return_value.get_job = AsyncMock(
        return_value={
            "job_id": "job-1",
            "image_path": str(split_file),
            "preview_cache_path": None,
            "source_pdf_path": None,
            "compressed_pdf_path": None,
        }
    )
    engine.get_job_repo.return_value.list_jobs = AsyncMock(
        return_value=[
            {"job_id": "job-1", "image_path": str(split_file)},
            {"job_id": "job-2", "image_path": str(split_file)},
        ]
    )

    result = await file_ops.delete_job_files("proj1", "job-1")

    assert result["deferred_files"]
    assert result["skipped_shared_files"]
    assert split_file.exists()

    kept = await file_ops.flush_deferred_gc("proj1")
    assert kept["kept_referenced"]
    assert split_file.exists()

    engine.get_job_repo.return_value.list_jobs = AsyncMock(return_value=[])
    deleted = await file_ops.flush_deferred_gc("proj1")
    assert deleted["deleted_files"]
    assert not split_file.exists()


@pytest.mark.asyncio
async def test_detect_job_sub_rects_delegates_to_splitter(file_ops, mock_dependencies):
    _, splitter, engine, root = mock_dependencies
    img_path = root / "分割發票" / "target.jpg"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img_path.write_bytes(b"dummy")

    splitter.detect_only.return_value = [{"points": [[0, 0], [10, 0], [10, 10], [0, 10]], "area": 100.0}]
    engine.get_job_repo.return_value.get_job = AsyncMock(return_value={"job_id": "job-1", "image_path": str(img_path)})

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=np.zeros((20, 20, 3), dtype=np.uint8)):
        result = await file_ops.detect_job_sub_rects("proj1", "job-1")

    assert len(result) == 1
    splitter.detect_only.assert_called_once()


@pytest.mark.asyncio
async def test_detect_job_sub_rects_prefers_raw_source_by_split_stem(file_ops, mock_dependencies):
    _, splitter, engine, root = mock_dependencies
    split_path = root / "分割發票" / "receiptA_split_0_123456_abcd12.jpg"
    raw_path = root / "原始輸入" / "receiptA.png"
    split_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    split_path.write_bytes(b"split")
    raw_path.write_bytes(b"raw")

    splitter.detect_only.return_value = [{"points": [[0, 0], [8, 0], [8, 8], [0, 8]], "area": 64.0}]
    engine.get_job_repo.return_value.get_job = AsyncMock(return_value={"job_id": "job-raw", "image_path": str(split_path)})

    captured = {}

    def fake_read(path):
        captured["path"] = path
        return np.zeros((20, 20, 3), dtype=np.uint8)

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", side_effect=fake_read):
        result = await file_ops.detect_job_sub_rects("proj1", "job-raw")

    assert len(result) == 1
    assert Path(captured["path"]).resolve() == raw_path.resolve()


@pytest.mark.asyncio
async def test_apply_job_resplit_creates_new_jobs(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    src_path = root / "分割發票" / "source.jpg"
    src_path.parent.mkdir(parents=True, exist_ok=True)
    utils.cv_imwrite_chinese(str(src_path), np.full((240, 160, 3), 200, dtype=np.uint8))

    engine.get_job_repo.return_value.get_job = AsyncMock(return_value={"job_id": "old-job", "image_path": str(src_path)})
    engine.enqueue_job = AsyncMock(side_effect=["new-job-1", "new-job-2"])

    with patch.object(file_ops, "ensure_preview_cache", AsyncMock(return_value=None)):
        result = await file_ops.apply_job_resplit(
            "proj1",
            "old-job",
            [
                {"points": [[10, 10], [150, 10], [150, 110], [10, 110]]},
                {"points": [[10, 120], [150, 120], [150, 220], [10, 220]]},
            ],
        )

    assert result["status"] == "resplit_applied"
    assert len(result["new_job_ids"]) == 2
    engine.delete_job.assert_called_once_with("proj1", "old-job")


@pytest.mark.asyncio
async def test_apply_job_resplit_prefers_raw_source_by_split_stem(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    split_path = root / "分割發票" / "receiptB_split_0_999999_abcd12.jpg"
    raw_path = root / "原始輸入" / "receiptB.jpg"
    split_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    utils.cv_imwrite_chinese(str(split_path), np.full((80, 80, 3), 180, dtype=np.uint8))
    utils.cv_imwrite_chinese(str(raw_path), np.full((260, 180, 3), 200, dtype=np.uint8))

    engine.get_job_repo.return_value.get_job = AsyncMock(return_value={"job_id": "old-job", "image_path": str(split_path)})
    engine.enqueue_job = AsyncMock(return_value="new-job")

    captured = {}

    def fake_read(path):
        captured["path"] = path
        return np.full((260, 180, 3), 200, dtype=np.uint8)

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", side_effect=fake_read), \
         patch.object(file_ops, "ensure_preview_cache", AsyncMock(return_value=None)):
        result = await file_ops.apply_job_resplit(
            "proj1",
            "old-job",
            [{"points": [[10, 10], [170, 10], [170, 210], [10, 210]]}],
        )

    assert result["status"] == "resplit_applied"
    assert Path(captured["path"]).resolve() == raw_path.resolve()


@pytest.mark.asyncio
async def test_detect_raw_sub_rects_supports_dotted_stem_lookup(file_ops, mock_dependencies):
    _, splitter, _, root = mock_dependencies
    raw_path = root / "原始輸入" / "receipt.v2.jpg"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"raw")

    splitter.detect_only.return_value = [{"points": [[0, 0], [8, 0], [8, 8], [0, 8]], "area": 64.0}]
    captured = {}

    def fake_read(path):
        captured["path"] = path
        return np.zeros((24, 24, 3), dtype=np.uint8)

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", side_effect=fake_read):
        result = await file_ops.detect_raw_sub_rects("proj1", "receipt.v2")

    assert len(result) == 1
    assert Path(captured["path"]).resolve() == raw_path.resolve()


@pytest.mark.asyncio
async def test_apply_raw_resplit_replaces_related_jobs(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    raw_path = root / "原始輸入" / "receipt.v2.jpg"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    utils.cv_imwrite_chinese(str(raw_path), np.full((260, 180, 3), 200, dtype=np.uint8))

    split_dir = root / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    engine.get_job_repo.return_value.list_jobs = AsyncMock(return_value=[
        {"job_id": "old-1", "image_path": str(split_dir / "receipt.v2_split_0_old.jpg")},
        {"job_id": "old-2", "image_path": str(split_dir / "receipt.v2_split_1_old.jpg")},
        {"job_id": "other", "image_path": str(split_dir / "other_split_0_old.jpg")},
    ])
    engine.enqueue_job = AsyncMock(return_value="new-job")

    with patch.object(file_ops, "ensure_preview_cache", AsyncMock(return_value=None)):
        result = await file_ops.apply_raw_resplit(
            "proj1",
            "receipt.v2.jpg",
            [{"points": [[10, 10], [170, 10], [170, 210], [10, 210]]}],
        )

    assert result["status"] == "resplit_applied"
    assert result["replaced_job_ids"] == ["old-1", "old-2"]
    assert result["new_job_ids"] == ["new-job"]
    assert engine.delete_job.call_count == 2
    engine.delete_job.assert_any_call("proj1", "old-1")
    engine.delete_job.assert_any_call("proj1", "old-2")


@pytest.mark.asyncio
async def test_optimize_jxl_storage_updates_job_path(file_ops, mock_dependencies):
    _, _, engine, root = mock_dependencies
    src_path = root / "分割發票" / "legacy.jpg"
    src_path.parent.mkdir(parents=True, exist_ok=True)
    utils.cv_imwrite_chinese(str(src_path), np.full((80, 80, 3), 128, dtype=np.uint8))

    engine.get_job_repo.return_value.list_jobs = AsyncMock(return_value=[
        {"job_id": "legacy-job", "image_path": str(src_path)},
    ])

    def fake_write(output_path, _image, *_args, **_kwargs):
        output = Path(output_path)
        output.write_bytes(b"fake-jxl")
        return output

    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=np.zeros((80, 80, 3), dtype=np.uint8)), \
         patch("backend.engine.file_ops.ImageCodecAdapter.resolve_archival_extension", return_value="jxl"), \
         patch("backend.engine.file_ops.ImageCodecAdapter.write_archival_image", side_effect=fake_write), \
         patch.object(file_ops, "ensure_preview_cache", AsyncMock(return_value={"path": "cache.jpg"})):
        summary = await file_ops.optimize_jxl_storage("proj1", force=False)

    assert summary["optimized_jobs"] == 1
    assert summary["failed_jobs"] == 0
    update_kwargs = engine.get_job_repo.return_value.update_job.call_args.kwargs
    assert update_kwargs["source_format"] == "jxl"
    assert update_kwargs["image_path"].endswith(".jxl")

