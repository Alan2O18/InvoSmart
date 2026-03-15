"""Tests for scripts/migrate_images_to_jxl_avif.py"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg(path: Path):
    """Write a minimal valid JPEG so PIL can open it."""
    img = Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8))
    img.save(path, format="JPEG")


def _make_args(workspace_root: str, **overrides) -> argparse.Namespace:
    defaults = dict(
        workspace_root=workspace_root,
        checkpoint=str(Path(workspace_root) / ".test_checkpoint.json"),
        dry_run=False,
        resume=False,
        archival_format="jpg",
        preview_format="jpeg",
        preview_max_width=64,
        checkpoint_interval=1000,
        canary_limit=0,
        report_path=None,
        verbose=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Import the script as a module
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.migrate_images_to_jxl_avif import run  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_run_basic_generates_preview(tmp_path):
    """run() should create a preview file for each input image."""
    proj = tmp_path / "proj1"
    split = proj / "分割發票"
    split.mkdir(parents=True)
    _make_jpeg(split / "receipt.jpg")

    args = _make_args(str(tmp_path))
    rc = run(args)

    assert rc == 0
    previews = list((proj / "快取影像" / "voucher_preview").glob("*.jpeg"))
    assert len(previews) == 1


def test_canary_limit_stops_early(tmp_path):
    """--canary-limit should stop after N images regardless of project count."""
    for i in range(3):
        split = tmp_path / f"proj{i}" / "分割發票"
        split.mkdir(parents=True)
        _make_jpeg(split / f"r{i}.jpg")

    args = _make_args(str(tmp_path), canary_limit=2)
    rc = run(args)

    assert rc == 0
    # Only 2 previews should have been generated across all projects
    all_previews = list(tmp_path.rglob("voucher_preview/*.jpeg"))
    assert len(all_previews) == 2


def test_report_written_with_correct_keys(tmp_path):
    """--report-path should produce a JSON file with required summary keys."""
    split = tmp_path / "projA" / "分割發票"
    split.mkdir(parents=True)
    _make_jpeg(split / "item.jpg")

    report_file = tmp_path / "report.json"
    args = _make_args(str(tmp_path), report_path=str(report_file))
    rc = run(args)

    assert rc == 0
    assert report_file.exists()
    report = json.loads(report_file.read_text(encoding="utf-8"))
    for key in ("migrated", "skipped", "errors", "dry_run", "timestamp"):
        assert key in report, f"Missing key '{key}' in report"
    assert report["migrated"] == 1


def test_rollback_list_written(tmp_path):
    """A rollback file listing generated cache files should be created."""
    split = tmp_path / "projB" / "分割發票"
    split.mkdir(parents=True)
    _make_jpeg(split / "item.jpg")

    checkpoint = tmp_path / ".ckpt.json"
    args = _make_args(str(tmp_path), checkpoint=str(checkpoint))
    run(args)

    rollback_file = checkpoint.with_suffix(".rollback.json")
    assert rollback_file.exists()
    data = json.loads(rollback_file.read_text(encoding="utf-8"))
    assert "generated_files" in data
    assert len(data["generated_files"]) == 1


def test_dry_run_writes_no_files(tmp_path):
    """--dry-run must not write any preview files."""
    split = tmp_path / "projC" / "分割發票"
    split.mkdir(parents=True)
    _make_jpeg(split / "r.jpg")

    args = _make_args(str(tmp_path), dry_run=True)
    rc = run(args)

    assert rc == 0
    previews = list(tmp_path.rglob("voucher_preview/*.jpg"))
    assert len(previews) == 0


def test_resume_skips_processed(tmp_path):
    """--resume should skip images already recorded in the checkpoint."""
    split = tmp_path / "projD" / "分割發票"
    split.mkdir(parents=True)
    img = split / "ri.jpg"
    _make_jpeg(img)

    ckpt = tmp_path / ".ckpt.json"
    ckpt.write_text(
        json.dumps({"processed": [str(img.resolve())], "updated_at": 0}),
        encoding="utf-8",
    )
    args = _make_args(str(tmp_path), checkpoint=str(ckpt), resume=True)
    rc = run(args)

    assert rc == 0
    previews = list(tmp_path.rglob("voucher_preview/*.jpg"))
    assert len(previews) == 0


def test_jxl_archival_invokes_encoder_when_available(tmp_path):
    split = tmp_path / "projJ" / "分割發票"
    split.mkdir(parents=True)
    source = split / "r.jpg"
    _make_jpeg(source)

    def _fake_encode(src: str, out: str, quality: int = 85):
        out_path = Path(out)
        out_path.write_bytes(b"jxl")
        return out_path

    args = _make_args(str(tmp_path), archival_format="jxl")
    with patch("scripts.migrate_images_to_jxl_avif.is_jxl_available", return_value=True), patch(
        "scripts.migrate_images_to_jxl_avif.encode_to_jxl", side_effect=_fake_encode
    ) as mock_encode:
        rc = run(args)

    assert rc == 0
    mock_encode.assert_called_once()
    assert source.with_suffix(".jxl").exists()


def test_jxl_archival_skips_when_encoder_unavailable(tmp_path):
    split = tmp_path / "projK" / "分割發票"
    split.mkdir(parents=True)
    source = split / "r.jpg"
    _make_jpeg(source)

    args = _make_args(str(tmp_path), archival_format="jxl")
    with patch("scripts.migrate_images_to_jxl_avif.is_jxl_available", return_value=False):
        rc = run(args)

    assert rc == 0
    assert not source.with_suffix(".jxl").exists()
