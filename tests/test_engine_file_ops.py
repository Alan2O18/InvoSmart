import pytest
import cv2
import numpy as np
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from backend.engine.file_ops import FileOps

@pytest.fixture
def mock_dependencies(tmp_path):
    project_repo = MagicMock()
    project_root = tmp_path / "proj1"
    project_root.mkdir()
    project_repo._project_root.return_value = project_root
    project_repo.update_project_status = AsyncMock()
    
    receipt_splitter = MagicMock()
    # Mock splitting returns two dummy image arrays
    dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
    receipt_splitter.split.return_value = [dummy_img, dummy_img]
    
    engine_ref = AsyncMock()
    engine_ref.enqueue_job = AsyncMock()
    
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
    _, _, _, root = mock_dependencies
    upload_file = tmp_path / "upload.jpg"
    upload_file.touch()
    
    with patch("backend.engine.file_ops.shutil.copy"):
        result = await file_ops.add_project_files("proj1", [str(upload_file)], type="raw")
        
    assert result["status"] == "added"
    assert (root / "原始輸入").exists()

@pytest.mark.asyncio
async def test_add_project_files_split_enqueues(file_ops, mock_dependencies, tmp_path):
    _, _, engine, root = mock_dependencies
    upload_file = tmp_path / "split_upload.jpg"
    upload_file.touch()
    
    with patch("backend.engine.file_ops.shutil.copy"):
        result = await file_ops.add_project_files("proj1", [str(upload_file)], type="split")
        
    assert result["status"] == "added"
    engine.enqueue_job.assert_called_once()
    assert "split_upload.jpg" in str(engine.enqueue_job.call_args[0][1])

def test_rotate_image(file_ops, mock_dependencies):
    _, _, _, root = mock_dependencies
    split_dir = root / "分割發票"
    split_dir.mkdir()
    (split_dir / "sample.jpg").touch()
    
    dummy_img = np.zeros((10, 20, 3), dtype=np.uint8)
    
    with patch("backend.engine.file_ops.utils.cv_imread_chinese", return_value=dummy_img), \
         patch("backend.engine.file_ops.cv2.rotate", return_value=dummy_img) as mock_rotate, \
         patch("backend.engine.file_ops.utils.cv_imwrite_chinese") as mock_imwrite:
        
        result = file_ops.rotate_image("proj1", "sample.jpg", angle=90)
        
        assert result["status"] == "rotated"
        mock_rotate.assert_called_once_with(dummy_img, cv2.ROTATE_90_CLOCKWISE)
        mock_imwrite.assert_called_once()
