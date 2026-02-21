"""
Comprehensive Engine Unit Tests

Tests all Engine functions with mocked heavy dependencies (OCR, LLM, Splitter).
"""
import pytest
import os
import tempfile
import time
from unittest.mock import MagicMock, patch
from pathlib import Path


# ============================================================================
# Project Management Tests
# ============================================================================

@pytest.mark.engine
class TestEngineProjectManagement:
    """Tests for project creation and management."""
    
    def test_create_project_new(self, real_engine_with_temp_workspace):
        """Test creating a brand new project."""
        engine = real_engine_with_temp_workspace
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"dummy image content")
            f_path = f.name
        
        try:
            res = engine.create_project("test_new_proj", [f_path], metadata={"key": "val"})
            assert res["status"] == "created_new"
            
            # Verify DB entry
            proj = engine.project_repo.get_project("test_new_proj")
            assert proj is not None
            assert proj["metadata"]["key"] == "val"
            
            # Verify file copied
            root = engine.project_repo._project_root("test_new_proj")
            assert (root / "原始輸入" / os.path.basename(f_path)).exists()
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_create_project_already_exists(self, real_engine_with_temp_workspace):
        """Test creating a project that already exists."""
        engine = real_engine_with_temp_workspace
        
        # Create first
        engine.project_repo.register_project("existing_proj", "Existing", str(engine.project_repo.workspace_root / "existing_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("existing_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("existing_proj") / "jobs.db"))
        
        # Try to create again
        res = engine.create_project("existing_proj", [], metadata={})
        assert res["status"] in ["already_registered", "resumed_registered"]

    def test_get_task_manager_creates_singleton(self, real_engine_with_temp_workspace):
        """Test that get_task_manager returns the same instance for the same project."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("tm_proj", "TM", str(engine.project_repo.workspace_root / "tm_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("tm_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("tm_proj") / "jobs.db"))
        
        tm1 = engine.get_task_manager("tm_proj")
        tm2 = engine.get_task_manager("tm_proj")
        
        assert tm1 is tm2


# ============================================================================
# File Operations Tests
# ============================================================================

@pytest.mark.engine
class TestEngineFileOps:
    """Tests for file operations."""
    
    def test_run_splitting(self, real_engine_with_temp_workspace):
        """Test running splitting on raw files."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("split_proj", "Split", str(engine.project_repo.workspace_root / "split_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("split_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("split_proj") / "jobs.db"))
        
        # Mock file ops
        def mock_splitting(project_id, target_files=None):
            root = engine.project_repo._project_root(project_id)
            (root / "分割發票" / "split_1.jpg").touch()
            tm = engine.get_task_manager(project_id)
            tm.insert_job("split_1", "分割發票/split_1.jpg")
            return {"status": "split_completed"}
        
        engine.file_ops.run_splitting = MagicMock(side_effect=mock_splitting)
        
        res = engine.run_splitting("split_proj")
        assert res["status"] == "split_completed"
        
        tm = engine.get_task_manager("split_proj")
        jobs = tm.list_jobs()
        assert len(jobs) == 1

    def test_get_raw_files_empty(self, real_engine_with_temp_workspace):
        """Test getting raw files when none exist."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("raw_empty", "Empty", str(engine.project_repo.workspace_root / "raw_empty"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("raw_empty"))
        
        files = engine.get_raw_files("raw_empty")
        assert files == []

    def test_get_raw_files_with_files(self, real_engine_with_temp_workspace):
        """Test getting raw files when files exist."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("raw_files", "Files", str(engine.project_repo.workspace_root / "raw_files"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("raw_files"))
        
        # Add file
        root = engine.project_repo._project_root("raw_files")
        (root / "原始輸入" / "test.jpg").touch()
        
        files = engine.get_raw_files("raw_files")
        assert len(files) == 1
        assert files[0]["filename"] == "test.jpg"

    def test_add_project_files_raw(self, real_engine_with_temp_workspace):
        """Test adding raw files to a project."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("add_raw", "Add", str(engine.project_repo.workspace_root / "add_raw"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("add_raw"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("add_raw") / "jobs.db"))
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test")
            f_path = f.name
        
        try:
            res = engine.add_project_files("add_raw", [f_path], type="raw")
            assert res["status"] == "added"
            
            root = engine.project_repo._project_root("add_raw")
            assert (root / "原始輸入" / os.path.basename(f_path)).exists()
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_add_project_files_split(self, real_engine_with_temp_workspace):
        """Test adding split files (should enqueue jobs)."""
        engine = real_engine_with_temp_workspace
        
        # Setup project (Phase 2: no per-project jobs.db needed)
        engine.project_repo.register_project("add_split", "Add", str(engine.project_repo.workspace_root / "add_split"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("add_split"))
        
        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test")
            f_path = f.name
        
        try:
            res = engine.add_project_files("add_split", [f_path], type="split")
            assert res["status"] == "added"
            
            # Check job was enqueued (Phase 2: use get_job_repo)
            job_repo = engine.get_job_repo("add_split")
            jobs = job_repo.list_jobs()
            assert len(jobs) == 1
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_rotate_image(self, real_engine_with_temp_workspace):
        """Test rotating an image."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("rotate_proj", "Rotate", str(engine.project_repo.workspace_root / "rotate_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("rotate_proj"))
        
        # Create a real image file (1x1 pixel)
        import numpy as np
        root = engine.project_repo._project_root("rotate_proj")
        img_path = root / "分割發票" / "test.jpg"
        
        # Mock cv2 imread/imwrite to avoid real image processing
        engine.file_ops.rotate_image = MagicMock(return_value={"status": "rotated", "path": str(img_path)})
        
        res = engine.rotate_image("rotate_proj", "test.jpg", 90)
        assert res["status"] == "rotated"

    def test_delete_raw_file(self, real_engine_with_temp_workspace):
        """Test deleting a raw file."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("del_raw", "Del", str(engine.project_repo.workspace_root / "del_raw"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("del_raw"))
        
        # Create file
        root = engine.project_repo._project_root("del_raw")
        (root / "原始輸入" / "to_delete.jpg").touch()
        
        res = engine.delete_raw_file("del_raw", "to_delete.jpg")
        assert res["status"] == "deleted"
        assert not (root / "原始輸入" / "to_delete.jpg").exists()

    def test_delete_raw_file_not_found(self, real_engine_with_temp_workspace):
        """Test deleting a non-existent raw file."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("del_raw_nf", "Del", str(engine.project_repo.workspace_root / "del_raw_nf"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("del_raw_nf"))
        
        res = engine.delete_raw_file("del_raw_nf", "nonexistent.jpg")
        assert res["status"] == "not_found"


# ============================================================================
# Processing Tests (VLM-First)
# ============================================================================

@pytest.mark.engine
class TestEngineProcessing:
    """Tests for VLM-First processing."""
    
    def test_run_processing_queues_jobs(self, real_engine_with_temp_workspace):
        """Test that run_processing queues ready jobs to the task queue."""
        engine = real_engine_with_temp_workspace
        
        # Setup project with job
        engine.project_repo.register_project("proc_proj", "Proc", str(engine.project_repo.workspace_root / "proc_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("proc_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("proc_proj") / "jobs.db"))
        
        tm = engine.get_task_manager("proc_proj")
        tm.insert_job("job1", "test.jpg")
        
        # VLM-First: run_processing queues ready/failed jobs
        res = engine.run_processing("proc_proj")
        assert res["status"] == "processing_queued"
        assert res["queued_count"] == 1
        
        # Verify job is in task queue
        assert engine.task_queue.qsize() >= 1
        
        # Verify job status changed to pending
        job = tm.get_job("job1")
        assert job["status"] == "pending"

    def test_run_processing_skips_done_jobs(self, real_engine_with_temp_workspace):
        """Test that run_processing skips already done jobs."""
        engine = real_engine_with_temp_workspace
        
        engine.project_repo.register_project("done_proj", "Done", str(engine.project_repo.workspace_root / "done_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("done_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("done_proj") / "jobs.db"))
        
        tm = engine.get_task_manager("done_proj")
        tm.insert_job("job1", "test.jpg")
        tm.update_job("job1", status="done")
        
        res = engine.run_processing("done_proj")
        assert res["queued_count"] == 0

    def test_run_single_processing(self, real_engine_with_temp_workspace):
        """Test single-job processing queues to task queue."""
        engine = real_engine_with_temp_workspace
        
        engine.project_repo.register_project("single_proc", "Single", str(engine.project_repo.workspace_root / "single_proc"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("single_proc"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("single_proc") / "jobs.db"))
        
        tm = engine.get_task_manager("single_proc")
        tm.insert_job("single_job", "test.jpg")
        
        res = engine.run_single_processing("single_proc", "single_job")
        assert res["status"] == "queued"
        assert res["job_id"] == "single_job"
        
        # Verify task queue
        assert engine.task_queue.qsize() >= 1
        
        # Verify job status
        job = tm.get_job("single_job")
        assert job["status"] == "pending"

    def test_run_single_processing_not_found(self, real_engine_with_temp_workspace):
        """Test that run_single_processing raises on unknown job."""
        engine = real_engine_with_temp_workspace
        
        engine.project_repo.register_project("nf_proj", "NF", str(engine.project_repo.workspace_root / "nf_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("nf_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("nf_proj") / "jobs.db"))
        
        with pytest.raises(ValueError):
            engine.run_single_processing("nf_proj", "nonexistent")


# ============================================================================
# Job Management Tests
# ============================================================================

@pytest.mark.engine
class TestEngineJobManagement:
    """Tests for job management."""
    
    def test_delete_job(self, real_engine_with_temp_workspace):
        """Test deleting a job."""
        engine = real_engine_with_temp_workspace
        
        # Setup
        engine.project_repo.register_project("del_job", "Del", str(engine.project_repo.workspace_root / "del_job"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("del_job"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("del_job") / "jobs.db"))
        
        tm = engine.get_task_manager("del_job")
        tm.insert_job("to_delete", "test.jpg")
        
        engine.delete_job("del_job", "to_delete")
        
        assert tm.get_job("to_delete") is None


# ============================================================================
# Export Tests
# ============================================================================

@pytest.mark.engine
class TestEngineExport:
    """Tests for export functionality."""
    
    def test_run_excel(self, real_engine_with_temp_workspace):
        """Test Excel export."""
        engine = real_engine_with_temp_workspace
        
        engine.export_handler.run_excel = MagicMock(return_value="path/to/excel.xlsx")
        
        res = engine.run_excel("test_proj")
        assert res == "path/to/excel.xlsx"
        engine.export_handler.run_excel.assert_called_once_with("test_proj")

    def test_archive_project(self, real_engine_with_temp_workspace):
        """Test project archiving."""
        engine = real_engine_with_temp_workspace
        
        engine.export_handler.seal_project = MagicMock(return_value={"status": "sealed", "path": "archive.zip"})
        
        res = engine.archive_project("test_proj")
        assert res["status"] == "sealed"
        engine.export_handler.seal_project.assert_called_once_with("test_proj")

    def test_regenerate_project(self, real_engine_with_temp_workspace):
        """Test project regeneration from archive."""
        engine = real_engine_with_temp_workspace
        
        engine.export_handler.regenerate_from_archive = MagicMock(return_value="path/to/new.zip")
        
        res = engine.regenerate_project("test_proj", "path/to/excel.xlsx")
        assert res == "path/to/new.zip"


# ============================================================================
# Group Management Tests
# ============================================================================

@pytest.mark.engine
class TestEngineGroups:
    """Tests for group management."""
    
    def test_upsert_group(self, real_engine_with_temp_workspace):
        """Test creating/updating a group."""
        engine = real_engine_with_temp_workspace
        
        engine.project_repo.upsert_group("TestGroup", "TestLeader")
        
        groups = engine.project_repo.list_groups()
        assert any(g["group_name"] == "TestGroup" for g in groups)

    def test_list_groups(self, real_engine_with_temp_workspace):
        """Test listing groups."""
        engine = real_engine_with_temp_workspace
        
        engine.project_repo.upsert_group("G1", "L1")
        engine.project_repo.upsert_group("G2", "L2")
        
        groups = engine.project_repo.list_groups()
        assert len(groups) >= 2

    def test_delete_group(self, real_engine_with_temp_workspace):
        """Test deleting a group."""
        engine = real_engine_with_temp_workspace
        
        engine.project_repo.upsert_group("ToDelete", "Leader")
        engine.project_repo.delete_group("ToDelete")
        
        groups = engine.project_repo.list_groups()
        assert not any(g["group_name"] == "ToDelete" for g in groups)

    def test_update_activity_info(self, real_engine_with_temp_workspace):
        """Test updating activity info on a project."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_repo.register_project("activity_proj", "Activity", str(engine.project_repo.workspace_root / "activity_proj"))
        
        engine.project_repo.update_activity_info("activity_proj", {
            "group_name": "TestGroup",
            "coordinator": "Alice",
            "teacher_count": 5
        })
        
        proj = engine.project_repo.get_project("activity_proj")
        assert proj["metadata"]["group_name"] == "TestGroup"
        assert proj["metadata"]["teacher_count"] == 5
