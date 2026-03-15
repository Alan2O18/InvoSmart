import pytest
import os
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from backend.engine.archive_handler import ArchiveHandler

@pytest.fixture
def mock_project_repo(tmp_path):
    repo = MagicMock()
    # Mock project root to a temporary directory
    proj_root = tmp_path / "proj1"
    proj_root.mkdir()
    
    # Create some dummy files
    (proj_root / "file1.txt").write_text("hello")
    (proj_root / "原始輸入").mkdir()
    (proj_root / "原始輸入" / "raw.txt").write_text("raw_data")
    
    repo._project_root.return_value = proj_root
    repo.workspace_root = tmp_path / "workspace"
    repo.update_project_status = AsyncMock()
    return repo

@pytest.mark.asyncio
@patch('backend.engine.archive_handler.shutil.which')
@patch('backend.engine.archive_handler.subprocess.run')
async def test_seal_project_7z_success(mock_sub_run, mock_which, mock_project_repo):
    # Pretend 7z is installed
    mock_which.return_value = "/usr/bin/7z"
    
    # Mock subprocess success
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "7z success"
    mock_proc.stderr = ""
    mock_sub_run.return_value = mock_proc
    
    handler = ArchiveHandler(mock_project_repo)
    result = await handler.seal_project("proj1", include_raw=True)
    
    assert result["success"] is True
    assert result["method"] == "7z"
    assert "proj1.7z" in result["archive_path"]
    mock_project_repo.update_project_status.assert_called_once_with("proj1", "ARCHIVED")
    mock_sub_run.assert_called_once()

@pytest.mark.asyncio
@patch('backend.engine.archive_handler.shutil.which')
@patch('backend.engine.archive_handler.subprocess.run')
async def test_seal_project_7z_exclude_raw(mock_sub_run, mock_which, mock_project_repo):
    # Pretend 7z is installed
    mock_which.return_value = "/usr/bin/7z"
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_sub_run.return_value = mock_proc
    
    handler = ArchiveHandler(mock_project_repo)
    result = await handler.seal_project("proj1", include_raw=False)
    
    assert result["success"] is True
    # The subprocess call should point to a temporary folder instead of the root
    called_cmd = mock_sub_run.call_args[0][0]
    target_dir = called_cmd[-1]
    assert "pm_seal_" in target_dir

@pytest.mark.asyncio
@patch('backend.engine.archive_handler.shutil.which')
async def test_seal_project_zip_fallback(mock_which, mock_project_repo):
    # Pretend 7z is NOT installed
    mock_which.return_value = None
    
    handler = ArchiveHandler(mock_project_repo)
    result = await handler.seal_project("proj1", include_raw=False)
    
    assert result["success"] is True
    assert result["method"] == "zip"
    assert "proj1.zip" in result["archive_path"]
    
    # Verify zip was created and contains file1.txt but not raw.txt
    import zipfile
    with zipfile.ZipFile(result["archive_path"], 'r') as zf:
        names = zf.namelist()
        # file1.txt should be in the relative path 'proj1/file1.txt'
        assert any("file1.txt" in n for n in names)
        assert not any("原始輸入" in n for n in names)

@pytest.mark.asyncio
async def test_seal_project_not_found():
    repo = MagicMock()
    repo._project_root.return_value = Path("/nonexistent/path/for/test")
    
    handler = ArchiveHandler(repo)
    with pytest.raises(FileNotFoundError):
        await handler.seal_project("nonexistent_proj")

@pytest.mark.asyncio
@patch('backend.engine.archive_handler.shutil.which')
@patch('backend.engine.archive_handler.zipfile.ZipFile')
async def test_seal_project_zip_exception(mock_zip, mock_which, mock_project_repo):
    mock_which.return_value = None
    mock_zip.side_effect = Exception("Zip Failed")
    
    handler = ArchiveHandler(mock_project_repo)
    result = await handler.seal_project("proj1", debug=True)
    
    assert result["success"] is False
    assert result["method"] == "zip"
    assert "Zip Failed" in result["debug"]
