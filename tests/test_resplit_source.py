from pathlib import Path
from unittest.mock import MagicMock

from backend.engine.resplit_source import (
    derive_raw_stem_from_split_filename,
    job_matches_raw_filename,
    resolve_raw_source_by_filename,
    resolve_resplit_raw_source,
)


def test_derive_raw_stem_from_split_filename_supports_known_markers():
    assert derive_raw_stem_from_split_filename("a_split_0_123.jpg") == "a"
    assert derive_raw_stem_from_split_filename("b_split_manual_1_456.jpg") == "b"
    assert derive_raw_stem_from_split_filename("c_resplit_2_789.jpg") == "c"
    assert derive_raw_stem_from_split_filename("plain.jpg") == "plain"


def test_resolve_raw_source_by_filename_supports_dotted_stem(tmp_path):
    raw_dir = tmp_path / "原始輸入"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / "receipt.v1.jpg"
    target.touch()

    resolved = resolve_raw_source_by_filename(tmp_path, "receipt.v1")
    assert resolved is not None
    assert Path(resolved).resolve() == target.resolve()


def test_resolve_resplit_raw_source_falls_back_to_split_when_raw_missing(tmp_path):
    split_dir = tmp_path / "分割發票"
    split_dir.mkdir(parents=True, exist_ok=True)
    split_path = split_dir / "receipt_split_0_abc.jpg"
    split_path.touch()

    def fake_resolve_project_path(root, raw_path, preferred_dir=None):
        if raw_path and "split" in str(raw_path):
            return split_path
        return None

    logger = MagicMock()
    resolved = resolve_resplit_raw_source(
        root=tmp_path,
        job={"job_id": "j1", "image_path": str(split_path)},
        resolve_project_path=fake_resolve_project_path,
        logger=logger,
    )

    assert resolved is not None
    assert Path(resolved).resolve() == split_path.resolve()
    logger.warning.assert_called_once()


def test_resolve_resplit_raw_source_uses_explicit_raw_path(tmp_path):
    raw_dir = tmp_path / "原始輸入"
    raw_dir.mkdir(parents=True, exist_ok=True)
    explicit_raw = raw_dir / "explicit.jpg"
    explicit_raw.touch()

    def fake_resolve_project_path(_root, raw_path, preferred_dir=None):
        if preferred_dir == "原始輸入" and raw_path:
            return explicit_raw
        return None

    resolved = resolve_resplit_raw_source(
        root=tmp_path,
        job={"job_id": "j2", "raw_image_path": str(explicit_raw)},
        resolve_project_path=fake_resolve_project_path,
        logger=None,
    )

    assert resolved is not None
    assert Path(resolved).resolve() == explicit_raw.resolve()


def test_resolve_resplit_raw_source_returns_none_when_no_candidates(tmp_path):
    def fake_resolve_project_path(_root, _raw_path, _preferred_dir=None):
        return None

    resolved = resolve_resplit_raw_source(
        root=tmp_path,
        job={"job_id": "j3", "image_path": "missing_split.jpg"},
        resolve_project_path=fake_resolve_project_path,
        logger=None,
    )

    assert resolved is None


def test_resolve_raw_source_by_filename_returns_none_when_dir_missing(tmp_path):
    assert resolve_raw_source_by_filename(tmp_path, "missing.jpg") is None


def test_job_matches_raw_filename_by_split_stem():
    assert job_matches_raw_filename({"image_path": "abc_split_0_x.jpg"}, "abc.jpg") is True
    assert job_matches_raw_filename({"image_path": "abc_split_0_x.jpg"}, "def.jpg") is False
    assert job_matches_raw_filename({"image_path": ""}, "abc.jpg") is False
