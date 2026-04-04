"""
Comprehensive Engine Unit Tests

Tests all Engine functions with mocked heavy dependencies (OCR, LLM, Splitter).
"""
import pytest
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from backend.repositories.project_repository import ProjectArchivedError


# ============================================================================
# Project Management Tests
# ============================================================================

@pytest.mark.engine
@pytest.mark.asyncio
class TestEngineProjectManagement:
    """Tests for project creation and management."""
    
    async def test_create_project_new(self, test_engine):
        """Test creating a brand new project."""
        engine = test_engine
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"dummy image content")
            f_path = f.name
        
        try:
            res = await engine.create_project("test_new_proj", [f_path], metadata={"key": "val"})
            assert res["status"] == "created_new"
            
            # Verify DB entry
            proj = await engine.project_repo.get_project("test_new_proj")
            assert proj is not None
            assert proj["metadata"]["key"] == "val"
            
            # Verify file copied
            root = engine.project_repo._project_root("test_new_proj")
            assert (root / "原始輸入" / os.path.basename(f_path)).exists()
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    async def test_create_project_already_exists(self, test_engine):
        """Test creating a project that already exists."""
        engine = test_engine
        
        # Create first
        await engine.project_repo.register_project("existing_proj", "Existing", str(engine.project_repo.workspace_root / "existing_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("existing_proj"))
        
        # Try to create again
        res = await engine.create_project("existing_proj", [], metadata={})
        assert res["status"] in ["already_registered", "resumed_registered"]

    async def test_get_job_repo_creates_singleton(self, test_engine):
        """Test that get_job_repo returns the same instance for the same project."""
        engine = test_engine
        
        # Setup project
        project_id = "tm_proj"
        await engine.project_repo.register_project(project_id, "TM", str(engine.project_repo.workspace_root / project_id))
        engine.project_repo._ensure_layout(engine.project_repo._project_root(project_id))
        
        repo1 = engine.get_job_repo(project_id)
        repo2 = engine.get_job_repo(project_id)
        
        assert repo1 is repo2
        # Ensure it's cached
        assert project_id in engine._job_repos

    async def test_engine_init_and_workers(self, test_engine):
        """Test Engine initialization with workers, config loading and queue status."""
        from backend.engine.core import Engine
        engine = test_engine
        
        # Test config loading
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", return_value=MagicMock(__enter__=lambda _: MagicMock(read=lambda: '{"test": 1}'))):
                with patch("json.load", return_value={"test": 1}):
                    conf = engine._load_config()
                    assert conf == {"test": 1}

        # Test worker thread startup
        with patch('threading.Thread') as MockThread:
            mock_thread_instance = MockThread.return_value
            mock_thread_instance.is_alive.return_value = True
            
            # Create a true isolated engine with mocked receipt processor
            engine2 = Engine(
                config={"test": 1},
                receipt_processor=MagicMock(),
                project_repo=engine.project_repo,
                start_workers=True,
                session_factory=engine.session_factory
            )
            
            assert engine2._worker_thread is not None
            assert MockThread.call_count == 2
            assert mock_thread_instance.start.call_count == 2
            
            calls = MockThread.call_args_list
            assert calls[0].kwargs['target'].__name__ == 'global_receipt_worker_loop'
            assert calls[1].kwargs['target'].__name__ == 'pdf_worker_loop'
            
            status = engine2.get_queue_status()
            assert status["worker_alive"] is True
            assert status["mode"] == "vlm-first"

    async def test_update_config(self, test_engine):
        """Test runtime configuration updating."""
        engine = test_engine
        engine.receipt_processor = MagicMock()
        
        engine.update_config({"new": "val"})
        assert engine.config == {"new": "val"}
        engine.receipt_processor.update_config.assert_called_once_with({"new": "val"})

    async def test_get_job_repo_without_session_factory(self, test_engine):
        """Test get_job_repo gracefully falls back when session_factory is None."""
        engine = test_engine
        engine.session_factory = None
        
        # This will trigger lines 174-175 where it imports AsyncSessionLocal
        repo = engine.get_job_repo("test_null_factory")
        assert repo is not None
        assert repo.project_id == "test_null_factory"

    async def test_recover_pending_tasks(self, test_engine):
        """Test recovery of pending tasks on startup."""
        engine = test_engine
        
        # Setup specific state
        await engine.project_repo.register_project("rec_proj", "Rec", str(engine.project_repo.workspace_root / "rec_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("rec_proj"))
        tm = engine.get_job_repo("rec_proj")
        
        await tm.insert_job("job_pending", "img1.jpg")
        await tm.update_job("job_pending", status="pending")
        
        await tm.insert_job("job_ready", "img2.jpg")
        
        # Recover
        await engine.recover_pending_tasks()
        
        # Verify queue contains the pending job
        assert engine.task_queue.qsize() == 1
        item = engine.task_queue.get_nowait()
        assert item == ("rec_proj", "job_pending")

    async def test_recover_pending_tasks_exception(self, test_engine):
        """Test recovery of pending tasks handling exceptions."""
        engine = test_engine
        await engine.project_repo.register_project("rec_proj_err", "RecE", str(engine.project_repo.workspace_root / "rec_proj_err"))
        
        with patch.object(engine, 'get_job_repo', side_effect=Exception("DB Error")):
            await engine.recover_pending_tasks()


# ============================================================================
# File Operations Tests
# ============================================================================

@pytest.mark.engine
@pytest.mark.asyncio
class TestEngineFileOps:
    """Tests for file operations."""
    
    async def test_run_splitting(self, test_engine):
        """Test running splitting on raw files."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("split_proj", "Split", str(engine.project_repo.workspace_root / "split_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("split_proj"))
        
        # Mock file ops
        async def mock_splitting(project_id, target_files=None):
            root = engine.project_repo._project_root(project_id)
            (root / "分割發票" / "split_1.jpg").touch()
            tm = engine.get_job_repo(project_id)
            await tm.insert_job("split_1", "分割發票/split_1.jpg")
            return {"status": "split_completed"}
        
        engine.file_ops.run_splitting = MagicMock(side_effect=mock_splitting)
        
        res = await engine.run_splitting("split_proj")
        assert res["status"] == "split_completed"
        
        tm = engine.get_job_repo("split_proj")
        jobs = await tm.list_jobs()
        assert len(jobs) == 1

    async def test_get_raw_files_empty(self, test_engine):
        """Test getting raw files when none exist."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("raw_empty", "Empty", str(engine.project_repo.workspace_root / "raw_empty"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("raw_empty"))
        
        files = await engine.get_raw_files("raw_empty")
        assert files == []

    async def test_get_raw_files_with_files(self, test_engine):
        """Test getting raw files when files exist."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("raw_files", "Files", str(engine.project_repo.workspace_root / "raw_files"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("raw_files"))
        
        # Add file
        root = engine.project_repo._project_root("raw_files")
        (root / "原始輸入" / "test.jpg").touch()
        
        files = await engine.get_raw_files("raw_files")
        assert len(files) == 1
        assert files[0]["filename"] == "test.jpg"

    async def test_add_project_files_raw(self, test_engine):
        """Test adding raw files to a project."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("add_raw", "Add", str(engine.project_repo.workspace_root / "add_raw"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("add_raw"))
        
        # Create temp valid image
        import numpy as np
        import cv2
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f_path = f.name
        cv2.imwrite(f_path, np.zeros((1, 1, 3), dtype=np.uint8))
        
        try:
            res = await engine.add_project_files("add_raw", [f_path], type="raw")
            assert res["status"] == "added"
            
            root = engine.project_repo._project_root("add_raw")
            assert (root / "原始輸入" / os.path.basename(f_path)).exists()
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    async def test_add_project_files_split(self, test_engine):
        """Test adding split files (should enqueue jobs)."""
        engine = test_engine
        
        # Setup project (Phase 2: no per-project jobs.db needed)
        await engine.project_repo.register_project("add_split", "Add", str(engine.project_repo.workspace_root / "add_split"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("add_split"))
        
        # Create temp valid image
        import numpy as np
        import cv2
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f_path = f.name
        cv2.imwrite(f_path, np.zeros((1, 1, 3), dtype=np.uint8))
        
        try:
            res = await engine.add_project_files("add_split", [f_path], type="split")
            assert res["status"] == "added"
            
            # Check job was enqueued (Phase 2: use get_job_repo)
            job_repo = engine.get_job_repo("add_split")
            jobs = await job_repo.list_jobs()
            assert len(jobs) == 1
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    async def test_rotate_image(self, test_engine):
        """Test rotating an image."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("rotate_proj", "Rotate", str(engine.project_repo.workspace_root / "rotate_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("rotate_proj"))
        
        # Create a real image file (1x1 pixel)
        import numpy as np
        root = engine.project_repo._project_root("rotate_proj")
        img_path = root / "分割發票" / "test.jpg"
        
        # Mock cv2 imread/imwrite to avoid real image processing
        engine.file_ops.rotate_image = AsyncMock(return_value={"status": "rotated", "path": str(img_path)})
        
        res = await engine.rotate_image("rotate_proj", "test.jpg", 90)
        assert res["status"] == "rotated"

    async def test_delete_raw_file(self, test_engine):
        """Test deleting a raw file."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("del_raw", "Del", str(engine.project_repo.workspace_root / "del_raw"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("del_raw"))
        
        # Create file
        root = engine.project_repo._project_root("del_raw")
        (root / "原始輸入" / "to_delete.jpg").touch()
        
        res = await engine.delete_raw_file("del_raw", "to_delete.jpg")
        assert res["status"] == "deleted"
        assert not (root / "原始輸入" / "to_delete.jpg").exists()

    async def test_delete_raw_file_not_found(self, test_engine):
        """Test deleting a non-existent raw file."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("del_raw_nf", "Del", str(engine.project_repo.workspace_root / "del_raw_nf"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("del_raw_nf"))
        
        res = await engine.delete_raw_file("del_raw_nf", "nonexistent.jpg")
        assert res["status"] == "not_found"

    async def test_delete_raw_file_exception(self, test_engine):
        """Test exception catching in delete raw file."""
        engine = test_engine
        with patch("os.remove", side_effect=PermissionError("Locked")):
            # It needs to hit `path.exists()` first.
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(PermissionError):
                    await engine.delete_raw_file("some_proj", "file.jpg")

    async def test_run_split_single(self, test_engine):
        """Test run_split_single delegation."""
        from unittest.mock import AsyncMock
        engine = test_engine
        engine.file_ops.run_splitting = AsyncMock(return_value={"status": "done"})
        res = await engine.run_split_single("split_proj", "file1.jpg")
        engine.file_ops.run_splitting.assert_called_once_with("split_proj", target_files=["file1.jpg"])
        assert res["status"] == "done"

    async def test_run_splitting_rejects_archived_project(self, test_engine):
        engine = test_engine
        await engine.project_repo.register_project("split_locked", "Locked", str(engine.project_repo.workspace_root / "split_locked"))
        await engine.project_repo.update_project_status("split_locked", "ARCHIVED")

        with pytest.raises(ProjectArchivedError):
            await engine.run_splitting("split_locked")


# ============================================================================
# Processing Tests (VLM-First)
# ============================================================================

@pytest.mark.engine
@pytest.mark.asyncio
class TestEngineProcessing:
    """Tests for VLM-First processing."""
    
    async def test_run_processing_queues_jobs(self, test_engine):
        """Test that run_processing queues ready jobs to the task queue."""
        engine = test_engine
        
        # Setup project with job
        await engine.project_repo.register_project("proc_proj", "Proc", str(engine.project_repo.workspace_root / "proc_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("proc_proj"))
        
        tm = engine.get_job_repo("proc_proj")
        await tm.insert_job("job1", "test.jpg")
        
        # VLM-First: run_processing queues ready/failed jobs
        res = await engine.run_processing("proc_proj")
        assert res["status"] == "processing_queued"
        assert res["queued_count"] == 1
        
        # Verify job is in task queue
        assert engine.task_queue.qsize() >= 1
        
        # Verify job status changed to pending
        job = await tm.get_job("job1")
        assert job["status"] == "pending"

    async def test_run_processing_skips_done_jobs(self, test_engine):
        """Test that run_processing skips already done jobs."""
        engine = test_engine
        
        await engine.project_repo.register_project("done_proj", "Done", str(engine.project_repo.workspace_root / "done_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("done_proj"))
        
        tm = engine.get_job_repo("done_proj")
        await tm.insert_job("job1", "test.jpg")
        await tm.update_job("job1", status="done")
        
        res = await engine.run_processing("done_proj")
        assert res["queued_count"] == 0

    async def test_run_single_processing(self, test_engine):
        """Test single-job processing queues to task queue."""
        engine = test_engine
        
        await engine.project_repo.register_project("single_proc", "Single", str(engine.project_repo.workspace_root / "single_proc"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("single_proc"))
        
        tm = engine.get_job_repo("single_proc")
        await tm.insert_job("single_job", "test.jpg")
        
        res = await engine.run_single_processing("single_proc", "single_job")
        assert res["status"] == "queued"
        assert res["job_id"] == "single_job"
        
        # Verify task queue
        assert engine.task_queue.qsize() >= 1
        
        # Verify job status
        job = await tm.get_job("single_job")
        assert job["status"] == "pending"

    async def test_run_single_processing_not_found(self, test_engine):
        """Test that run_single_processing raises on unknown job."""
        engine = test_engine
        
        await engine.project_repo.register_project("nf_proj", "NF", str(engine.project_repo.workspace_root / "nf_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("nf_proj"))
        
        with pytest.raises(ValueError):
            await engine.run_single_processing("nf_proj", "nonexistent")

    async def test_run_processing_exception(self, test_engine):
        """Test exception thrown from inside processing initiator."""
        engine = test_engine
        with patch.object(engine, "get_job_repo", side_effect=Exception("Queue Err")):
            with pytest.raises(Exception, match="Queue Err"):
                await engine.run_processing("proj_1")

    async def test_run_processing_rejects_archived_project(self, test_engine):
        engine = test_engine
        await engine.project_repo.register_project("proc_locked", "Locked", str(engine.project_repo.workspace_root / "proc_locked"))
        await engine.project_repo.update_project_status("proc_locked", "ARCHIVED")

        with pytest.raises(ProjectArchivedError):
            await engine.run_processing("proc_locked")


# ============================================================================
# Job Management Tests
# ============================================================================

@pytest.mark.engine
@pytest.mark.asyncio
class TestEngineJobManagement:
    """Tests for job management."""
    
    async def test_delete_job(self, test_engine):
        """Test deleting a job."""
        engine = test_engine
        
        # Setup
        await engine.project_repo.register_project("del_job", "Del", str(engine.project_repo.workspace_root / "del_job"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("del_job"))
        
        tm = engine.get_job_repo("del_job")
        await tm.insert_job("to_delete", "test.jpg")

        with patch.object(engine.file_ops, "delete_job_files", AsyncMock(return_value={"job_found": True})) as mock_cleanup:
            result = await engine.delete_job("del_job", "to_delete")

        mock_cleanup.assert_called_once_with("del_job", "to_delete")
        assert result["status"] == "deleted"
        
        assert await tm.get_job("to_delete") is None

    async def test_cleanup_preview_cache_delegate(self, test_engine):
        engine = test_engine
        with patch.object(engine.file_ops, "cleanup_all_projects_cache", AsyncMock(return_value={"deleted_files": 3})) as mock_cleanup:
            result = await engine.cleanup_preview_cache(max_age_hours=12)

        mock_cleanup.assert_called_once_with(max_age_hours=12)
        assert result["deleted_files"] == 3

    async def test_detect_and_apply_resplit_delegates(self, test_engine):
        engine = test_engine
        await engine.project_repo.register_project("resplit_proj", "Resplit", str(engine.project_repo.workspace_root / "resplit_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("resplit_proj"))

        with patch.object(engine.file_ops, "detect_job_sub_rects", AsyncMock(return_value=[{"points": [], "area": 1.0}])) as mock_detect:
            detected = await engine.detect_job_sub_rects("resplit_proj", "job-1")

        assert len(detected) == 1
        mock_detect.assert_called_once_with("resplit_proj", "job-1")

        with patch.object(engine.file_ops, "apply_job_resplit", AsyncMock(return_value={"status": "resplit_applied"})) as mock_apply:
            result = await engine.apply_job_resplit("resplit_proj", "job-1", [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}])

        mock_apply.assert_called_once()
        assert result["status"] == "resplit_applied"

    async def test_job_state_transitions(self, test_engine):
        """Test claim, complete, and fail transitions."""
        engine = test_engine
        
        await engine.project_repo.register_project("state_proj", "State", str(engine.project_repo.workspace_root / "state_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("state_proj"))
        tm = engine.get_job_repo("state_proj")
        
        # Claim Job
        await tm.insert_job("job_claim", "img.jpg")
        await engine.claim_job("state_proj", "job_claim")
        j1 = await tm.get_job("job_claim")
        assert j1["status"] == "running"
        
        # Complete Job
        await tm.insert_job("job_comp", "img.jpg")
        await engine.complete_job("state_proj", "job_comp", {"header": {}}, {}, {}, True)
        j2 = await tm.get_job("job_comp")
        assert j2["status"] == "done"
        
        # Fail Job
        await tm.insert_job("job_fail", "img.jpg")
        await engine.fail_job("state_proj", "job_fail", "Random Exception")
        j3 = await tm.get_job("job_fail")
        assert j3["status"] == "failed"


# ============================================================================
# Export Tests
# ============================================================================

@pytest.mark.engine
@pytest.mark.asyncio
class TestEngineExport:
    """Tests for export functionality."""
    
    async def test_run_excel(self, test_engine):
        """Test Excel export."""
        from unittest.mock import AsyncMock
        engine = test_engine
        
        engine.export_handler.run_excel = AsyncMock(return_value="path/to/excel.xlsx")
        
        res = await engine.run_excel("test_proj")
        assert res == "path/to/excel.xlsx"
        engine.export_handler.run_excel.assert_called_once_with("test_proj")

    async def test_archive_project(self, test_engine):
        """Test project archiving."""
        from unittest.mock import AsyncMock
        engine = test_engine
        
        engine.export_handler.seal_project = AsyncMock(return_value={"status": "archived", "path": "archive.zip"})
        
        res = await engine.archive_project("test_proj")
        assert res["status"] == "archived"
        engine.export_handler.seal_project.assert_called_once_with("test_proj")

    @patch("backend.engine.regeneration_handler.RegenerationHandler.regenerate_from_archive")
    async def test_regenerate_project(self, mock_regenerate, test_engine):
        """Test project regeneration from archive."""
        from unittest.mock import AsyncMock
        mock_regenerate.side_effect = AsyncMock(return_value="path/to/new.zip")
        
        engine = test_engine
        
        res = await engine.regenerate_project("test_proj", "path/to/excel.xlsx")
        assert res == "path/to/new.zip"


# ============================================================================
# Group Management Tests
# ============================================================================

@pytest.mark.engine
@pytest.mark.asyncio
class TestEngineGroups:
    """Tests for group management."""
    
    async def test_upsert_group(self, test_engine):
        """Test creating/updating a group."""
        engine = test_engine
        
        await engine.project_repo.upsert_group("TestGroup", "TestLeader")
        
        groups = await engine.project_repo.list_groups()
        assert any(g["group_name"] == "TestGroup" for g in groups)

    async def test_list_groups(self, test_engine):
        """Test listing groups."""
        engine = test_engine
        
        await engine.project_repo.upsert_group("G1", "L1")
        await engine.project_repo.upsert_group("G2", "L2")
        
        groups = await engine.project_repo.list_groups()
        assert len(groups) >= 2

    async def test_delete_group(self, test_engine):
        """Test deleting a group."""
        engine = test_engine
        
        await engine.project_repo.upsert_group("ToDelete", "Leader")
        await engine.project_repo.delete_group("ToDelete")
        
        groups = await engine.project_repo.list_groups()
        assert not any(g["group_name"] == "ToDelete" for g in groups)

    async def test_update_activity_info(self, test_engine):
        """Test updating activity info on a project."""
        engine = test_engine
        
        # Setup project
        await engine.project_repo.register_project("activity_proj", "Activity", str(engine.project_repo.workspace_root / "activity_proj"))
        
        await engine.project_repo.update_activity_info("activity_proj", {
            "group_name": "TestGroup",
            "coordinator": "Alice",
            "teacher_count": 5
        })
        
        proj = await engine.project_repo.get_project("activity_proj")
        assert proj["metadata"]["group_name"] == "TestGroup"
        assert proj["metadata"]["teacher_count"] == 5
