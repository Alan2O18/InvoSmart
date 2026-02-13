"""
archive_handler.py 與 regeneration_handler.py 單元測試
"""
import pytest
import json
import tempfile
import sqlite3
import time
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.engine.archive_handler import ArchiveHandler


# ============================================================================
# ArchiveHandler 測試
# ============================================================================

@pytest.fixture
def mock_archive_repo(tmp_path):
    """建立帶有模擬專案目錄的 mock repo"""
    repo = MagicMock()
    project_root = tmp_path / "my_project"
    project_root.mkdir()

    # 建立一些模擬檔案
    (project_root / "原始輸入").mkdir()
    (project_root / "原始輸入" / "scan.jpg").write_bytes(b"fake_image_data")
    (project_root / "jobs.db").write_text("fake db")
    (project_root / "output").mkdir()
    (project_root / "output" / "result.json").write_text('{"ok": true}')

    repo._project_root.return_value = project_root
    repo.workspace_root = tmp_path
    return repo


class TestArchiveHandler:
    """測試專案封存"""

    @patch("shutil.which", return_value=None)  # 強制使用 zip fallback
    def test_seal_project_zip(self, mock_which, mock_archive_repo):
        """無 7z 時回退到 zip"""
        handler = ArchiveHandler(mock_archive_repo)
        result = handler.seal_project("my_project")

        assert result["success"] is True
        assert result["method"] == "zip"
        assert Path(result["archive_path"]).exists()

        # 驗證 zip 內容
        import zipfile
        with zipfile.ZipFile(result["archive_path"], "r") as z:
            names = z.namelist()
            assert any("jobs.db" in n for n in names)
            assert any("result.json" in n for n in names)

    @patch("shutil.which", return_value=None)
    def test_seal_project_excludes_raw(self, mock_which, mock_archive_repo):
        """exclude_raw=False 時排除原始輸入"""
        handler = ArchiveHandler(mock_archive_repo)
        result = handler.seal_project("my_project", include_raw=False)

        assert result["success"] is True
        import zipfile
        with zipfile.ZipFile(result["archive_path"], "r") as z:
            names = z.namelist()
            assert not any("原始輸入" in n for n in names)

    def test_seal_nonexistent_project(self, mock_archive_repo):
        """不存在的專案 → FileNotFoundError"""
        nonexistent = mock_archive_repo._project_root.return_value / "ghost"
        mock_archive_repo._project_root.return_value = nonexistent

        handler = ArchiveHandler(mock_archive_repo)
        with pytest.raises(FileNotFoundError):
            handler.seal_project("ghost_project")

    @patch("shutil.which", return_value=None)
    def test_seal_with_debug(self, mock_which, mock_archive_repo):
        """debug=True 時返回 debug 資訊"""
        handler = ArchiveHandler(mock_archive_repo)
        result = handler.seal_project("my_project", debug=True)

        assert result["success"] is True
        assert result["debug"] is not None

    @patch("shutil.which", return_value=None)
    def test_seal_updates_status(self, mock_which, mock_archive_repo):
        """封存成功後更新專案狀態為 SEALED"""
        handler = ArchiveHandler(mock_archive_repo)
        handler.seal_project("my_project")

        mock_archive_repo.update_project_status.assert_called_once_with(
            "my_project", "SEALED"
        )
