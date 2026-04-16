from unittest.mock import MagicMock

from backend.engine.file_service import FileService


def test_get_raw_files_counts_splits(tmp_path):
    project_root = tmp_path / "proj1"
    project_root.mkdir(parents=True, exist_ok=True)

    raw_dir = project_root / "原始輸入"
    split_dir = project_root / "分割發票"
    raw_dir.mkdir(parents=True, exist_ok=True)
    split_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / "receipt.v1.jpg").touch()
    (raw_dir / "ignore.txt").touch()
    (split_dir / "receipt.v1_split_0_aaa.jpg").touch()
    (split_dir / "receipt.v1_split_1_bbb.jpg").touch()

    project_repo = MagicMock()
    project_repo._project_root.return_value = project_root
    service = FileService(project_repo)

    rows = service.get_raw_files("proj1")
    assert len(rows) == 1
    assert rows[0]["filename"] == "receipt.v1.jpg"
    assert rows[0]["split_count"] == 2


def test_delete_raw_file_uses_safe_filename(tmp_path):
    project_root = tmp_path / "proj1"
    project_root.mkdir(parents=True, exist_ok=True)

    raw_dir = project_root / "原始輸入"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target = raw_dir / "safe.jpg"
    target.touch()

    project_repo = MagicMock()
    project_repo._project_root.return_value = project_root
    service = FileService(project_repo)

    result = service.delete_raw_file("proj1", "../safe.jpg")
    assert result["status"] == "deleted"
    assert not target.exists()


def test_get_raw_files_returns_empty_on_exception():
    project_repo = MagicMock()
    project_repo._project_root.side_effect = RuntimeError("boom")
    service = FileService(project_repo)

    assert service.get_raw_files("proj1") == []
