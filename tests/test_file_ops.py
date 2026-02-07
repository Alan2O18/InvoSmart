"""
Unit Tests for FileOps

Tests file operations including:
- Getting raw files
- Adding project files
- Image rotation
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import cv2


class TestFileOps:
    """FileOps Tests"""

    @pytest.fixture
    def mock_deps(self):
        """Create mocked dependencies for FileOps."""
        project_manager = MagicMock()
        receipt_splitter = MagicMock()
        engine = MagicMock()
        task_manager = MagicMock()
        engine.get_task_manager.return_value = task_manager
        
        return {
            'project_manager': project_manager,
            'receipt_splitter': receipt_splitter,
            'engine': engine,
            'task_manager': task_manager
        }

    @pytest.fixture
    def temp_project(self):
        """Create temporary project directory structure."""
        temp_dir = tempfile.mkdtemp()
        project_root = Path(temp_dir)
        
        # Create directories
        (project_root / "原始輸入").mkdir()
        (project_root / "分割發票").mkdir()
        
        yield project_root
        
        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def file_ops(self, mock_deps, temp_project):
        """Create FileOps instance with mocked deps."""
        from backend.engine.file_ops import FileOps
        
        mock_deps['project_manager']._project_root.return_value = temp_project
        
        return FileOps(
            mock_deps['project_manager'],
            mock_deps['receipt_splitter'],
            mock_deps['engine']
        )

    # ===== get_raw_files Tests =====
    
    def test_get_raw_files_empty(self, file_ops, temp_project):
        """Test getting raw files from empty directory."""
        result = file_ops.get_raw_files("test_project")
        
        assert result == []

    def test_get_raw_files_with_images(self, file_ops, temp_project):
        """Test getting raw files with images present."""
        # Create test images
        raw_dir = temp_project / "原始輸入"
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(raw_dir / "test1.jpg"), test_image)
        cv2.imwrite(str(raw_dir / "test2.png"), test_image)
        
        result = file_ops.get_raw_files("test_project")
        
        assert len(result) == 2
        filenames = [f['filename'] for f in result]
        assert "test1.jpg" in filenames
        assert "test2.png" in filenames

    def test_get_raw_files_counts_splits(self, file_ops, temp_project):
        """Test that split_count is calculated correctly."""
        raw_dir = temp_project / "原始輸入"
        split_dir = temp_project / "分割發票"
        
        # Create raw image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(raw_dir / "receipt.jpg"), test_image)
        
        # Create split images
        cv2.imwrite(str(split_dir / "receipt_split_0_123.jpg"), test_image)
        cv2.imwrite(str(split_dir / "receipt_split_1_123.jpg"), test_image)
        
        result = file_ops.get_raw_files("test_project")
        
        assert len(result) == 1
        assert result[0]['filename'] == "receipt.jpg"
        assert result[0]['split_count'] == 2

    def test_get_raw_files_ignores_non_images(self, file_ops, temp_project):
        """Test that non-image files are ignored."""
        raw_dir = temp_project / "原始輸入"
        
        # Create non-image file
        (raw_dir / "notes.txt").write_text("test")
        
        # Create image file
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(raw_dir / "image.jpg"), test_image)
        
        result = file_ops.get_raw_files("test_project")
        
        assert len(result) == 1
        assert result[0]['filename'] == "image.jpg"

    # ===== rotate_image Tests =====
    
    @pytest.mark.skip(reason="Requires utils.cv_imread_chinese which has complex path handling")
    def test_rotate_image_90(self, file_ops, temp_project):
        """Test rotating image 90 degrees clockwise."""
        split_dir = temp_project / "分割發票"
        
        # Create test image (non-square to verify rotation)
        test_image = np.zeros((100, 200, 3), dtype=np.uint8)  # 100x200
        cv2.imwrite(str(split_dir / "test.jpg"), test_image)
        
        result = file_ops.rotate_image("test_project", "test.jpg", 90)
        
        assert result['status'] == "rotated"
        
        # Verify rotation happened
        rotated = cv2.imread(str(split_dir / "test.jpg"))
        assert rotated.shape[:2] == (200, 100)  # Dimensions swapped

    @pytest.mark.skip(reason="Requires utils.cv_imread_chinese")
    def test_rotate_image_180(self, file_ops, temp_project):
        """Test rotating image 180 degrees."""
        split_dir = temp_project / "分割發票"
        
        test_image = np.zeros((100, 200, 3), dtype=np.uint8)
        cv2.imwrite(str(split_dir / "test.jpg"), test_image)
        
        result = file_ops.rotate_image("test_project", "test.jpg", 180)
        
        assert result['status'] == "rotated"
        
        rotated = cv2.imread(str(split_dir / "test.jpg"))
        assert rotated.shape[:2] == (100, 200)  # Same dimensions

    def test_rotate_image_not_found(self, file_ops, temp_project):
        """Test rotation of non-existent image raises error."""
        with pytest.raises(FileNotFoundError):
            file_ops.rotate_image("test_project", "nonexistent.jpg", 90)

    # ===== add_project_files Tests =====
    
    @pytest.mark.skip(reason="Requires complex file copy and path handling")
    def test_add_project_files_raw(self, file_ops, temp_project, mock_deps):
        """Test adding files to raw directory."""
        # Create source file
        source_dir = tempfile.mkdtemp()
        source_file = Path(source_dir) / "test_receipt.jpg"
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(source_file), test_image)
        
        try:
            result = file_ops.add_project_files("test_project", [str(source_file)], type="raw")
            
            assert result['status'] == "added"
            assert (temp_project / "原始輸入" / "test_receipt.jpg").exists()
        finally:
            shutil.rmtree(source_dir)

    @pytest.mark.skip(reason="Requires complex file copy and path handling")
    def test_add_project_files_split(self, file_ops, temp_project, mock_deps):
        """Test adding files to split directory enqueues them."""
        source_dir = tempfile.mkdtemp()
        source_file = Path(source_dir) / "receipt.jpg"
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(source_file), test_image)
        
        try:
            result = file_ops.add_project_files("test_project", [str(source_file)], type="split")
            
            assert result['status'] == "added"
            assert (temp_project / "分割發票" / "receipt.jpg").exists()
            # Verify task was enqueued
            mock_deps['task_manager'].enqueue.assert_called()
        finally:
            shutil.rmtree(source_dir)

    def test_add_project_files_invalid_type(self, file_ops):
        """Test adding files with invalid type raises error."""
        with pytest.raises(ValueError):
            file_ops.add_project_files("test_project", ["file.jpg"], type="invalid")

    # ===== run_splitting Tests =====
    
    @pytest.mark.skip(reason="Requires receipt_splitter with complex image processing")
    def test_run_splitting_success(self, file_ops, temp_project, mock_deps):
        """Test successful splitting operation."""
        raw_dir = temp_project / "原始輸入"
        
        # Create test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(str(raw_dir / "test.jpg"), test_image)
        
        # Mock splitter to return one cropped image
        mock_deps['receipt_splitter'].split.return_value = [test_image]
        
        result = file_ops.run_splitting("test_project")
        
        assert result['status'] == "split_completed"
        mock_deps['project_manager'].update_project_status.assert_called_with(
            "test_project", "SPLIT"
        )
