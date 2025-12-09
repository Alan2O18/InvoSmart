"""
Integration Use Case Tests

Tests end-to-end workflows that combine multiple Engine/API operations.
"""
import pytest
import os
import time
import tempfile
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


# ============================================================================
# Use Case 1: Full Project Lifecycle
# Create → Upload → Split → OCR → LLM → Export → Archive
# ============================================================================

@pytest.mark.integration
class TestFullProjectLifecycle:
    """Tests the complete project processing lifecycle."""
    
    def test_complete_workflow_engine(self, real_engine_with_temp_workspace):
        """Test full lifecycle through Engine."""
        engine = real_engine_with_temp_workspace
        
        # 1. Create project
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test image")
            f_path = f.name
        
        try:
            res = engine.create_project("lifecycle_proj", [f_path], metadata={"test": True})
            assert res["status"] == "created_new"
            
            # 2. Verify file ingested
            files = engine.get_raw_files("lifecycle_proj")
            assert len(files) == 1
            
            # 3. Run splitting (mocked)
            def mock_split(proj_id, target=None):
                root = engine.project_manager._project_root(proj_id)
                (root / "分割發票" / "split_0.jpg").touch()
                tm = engine.get_task_manager(proj_id)
                tm.enqueue("分割發票/split_0.jpg", "job_0")
                return {"status": "split_completed"}
            
            engine.file_ops.run_splitting = MagicMock(side_effect=mock_split)
            res = engine.run_splitting("lifecycle_proj")
            assert res["status"] == "split_completed"
            
            # 4. Verify job created
            tm = engine.get_task_manager("lifecycle_proj")
            jobs = tm.list_jobs()
            assert len(jobs) == 1
            assert jobs[0]["status"] == "pending"
            assert jobs[0]["stage"] == "ocr"
            
            # 5. Run OCR (mocked worker - synchronous for test)
            from backend.engine import core
            
            def mock_ocr_worker(tm, proj_id, handler):
                task = tm.claim_for_ocr()
                if task:
                    tm.complete_ocr(task["job_id"], {"text": "Invoice #123\nTotal: $100"})
            
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(core, "start_cpu_worker", mock_ocr_worker)
                res = engine.run_ocr("lifecycle_proj")
                assert res["status"] == "ocr_started"
            
            time.sleep(0.5)
            
            # 6. Verify OCR completed, job advanced to LLM
            job = tm.get_job("job_0")
            assert job["stage"] == "llm"
            assert "Invoice" in job["ocr_result_json"]
            
            # 7. Run LLM (mocked worker - synchronous for test)
            def mock_llm_worker(tm, proj_id, handler):
                task = tm.claim_for_llm()
                if task and task != "all_task_done":
                    tm.complete_llm(task["job_id"], {
                        "corrected_full_text": "Invoice #123\nTotal: $100",
                        "structured_data": {"invoice_no": "123", "total": 100}
                    })
            
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(core, "start_gpu_worker", mock_llm_worker)
                res = engine.run_llm("lifecycle_proj")
                assert res["status"] == "llm_started"
            
            time.sleep(0.5)
            
            # 8. Verify LLM completed
            job = tm.get_job("job_0")
            assert job["status"] == "done"
            assert "structured_data" in job["llm_result_json"]
            
            # 9. Export (mocked)
            engine.export_handler.run_excel = MagicMock(return_value="lifecycle_proj.xlsx")
            res = engine.run_excel("lifecycle_proj")
            assert res == "lifecycle_proj.xlsx"
            
            # 10. Archive (mocked)
            engine.export_handler.seal_project = MagicMock(return_value={"status": "sealed"})
            res = engine.archive_project("lifecycle_proj")
            assert res["status"] == "sealed"
            
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)


# ============================================================================
# Use Case 2: Partial Reprocessing
# Create → Split → Single OCR → Single LLM (for specific jobs)
# ============================================================================

@pytest.mark.integration
class TestPartialReprocessing:
    """Tests reprocessing specific jobs."""
    
    def test_single_job_reprocessing(self, real_engine_with_temp_workspace):
        """Test OCR/LLM on a single job."""
        engine = real_engine_with_temp_workspace
        
        # Setup project with multiple jobs
        engine.project_manager.project_crud.register_project("partial_proj", "Partial", str(engine.project_manager.workspace_root / "partial_proj"))
        engine.project_manager.project_setup._ensure_layout(engine.project_manager._project_root("partial_proj"))
        engine.project_manager.project_setup._init_jobs_db(str(engine.project_manager._project_root("partial_proj") / "jobs.db"))
        
        tm = engine.get_task_manager("partial_proj")
        tm.enqueue("img1.jpg", "job1")
        tm.enqueue("img2.jpg", "job2")
        tm.enqueue("img3.jpg", "job3")
        
        # Complete OCR on job1 and job2
        tm.complete_ocr("job1", {"text": "OCR1"})
        tm.complete_ocr("job2", {"text": "OCR2"})
        
        # Now run single OCR on job3
        from backend.engine import workers
        
        ocr_called = []
        def mock_ocr(tm, task, handler, auto_advance=True):
            ocr_called.append(task["job_id"])
            tm.complete_ocr(task["job_id"], {"text": f"SingleOCR_{task['job_id']}"}, advance_to_stage_llm=auto_advance)
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(workers, "process_ocr_task", mock_ocr)
            res = engine.run_single_ocr("partial_proj", "job3")
            assert res["status"] == "single_ocr_started"
        
        time.sleep(0.5)
        
        # Verify job3 processed
        job3 = tm.get_job("job3")
        # Note: auto_advance=False in run_single_ocr, so stage might still be 'ocr'
        assert job3["ocr_result_json"] is not None

    def test_single_llm_reprocessing(self, real_engine_with_temp_workspace):
        """Test LLM on a single job that was already OCR'd."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_manager.project_crud.register_project("single_llm_proj", "LLM", str(engine.project_manager.workspace_root / "single_llm_proj"))
        engine.project_manager.project_setup._ensure_layout(engine.project_manager._project_root("single_llm_proj"))
        engine.project_manager.project_setup._init_jobs_db(str(engine.project_manager._project_root("single_llm_proj") / "jobs.db"))
        
        tm = engine.get_task_manager("single_llm_proj")
        tm.enqueue("img.jpg", "target_job")
        tm.complete_ocr("target_job", {"text": "OCR text to reprocess"})
        
        from backend.engine import workers
        
        def mock_llm(tm, task, handler, auto_advance=True):
            tm.complete_llm(task["job_id"], {"reprocessed": True}, mark_final=auto_advance)
        
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(workers, "process_llm_task", mock_llm)
            res = engine.run_single_llm("single_llm_proj", "target_job")
            assert res["status"] == "single_llm_started"


# ============================================================================
# Use Case 3: Group Management Flow
# Create Group → Assign to Project → List → Delete
# ============================================================================

@pytest.mark.integration
class TestGroupManagementFlow:
    """Tests group management workflow."""
    
    def test_group_lifecycle(self, real_engine_with_temp_workspace):
        """Test full group lifecycle."""
        engine = real_engine_with_temp_workspace
        
        # 1. Create groups
        engine.project_manager.upsert_group("教學組", "Alice")
        engine.project_manager.upsert_group("研究組", "Bob")
        
        # 2. List groups
        groups = engine.project_manager.list_groups()
        assert len(groups) >= 2
        
        # 3. Create project and assign group via activity info
        engine.project_manager.project_crud.register_project("grouped_proj", "Grouped", str(engine.project_manager.workspace_root / "grouped_proj"))
        engine.project_manager.update_activity_info("grouped_proj", {"group_name": "教學組"})
        
        # 4. Verify assignment
        proj = engine.project_manager.project_crud.get_project("grouped_proj")
        assert proj["metadata"]["group_name"] == "教學組"
        
        # 5. Update group
        engine.project_manager.upsert_group("教學組", "Charlie")  # New leader
        
        groups = engine.project_manager.list_groups()
        teaching_group = next(g for g in groups if g["group_name"] == "教學組")
        assert teaching_group["leader_name"] == "Charlie"
        
        # 6. Delete unused group
        engine.project_manager.delete_group("研究組")
        
        groups = engine.project_manager.list_groups()
        assert not any(g["group_name"] == "研究組" for g in groups)


# ============================================================================
# Use Case 4: File Management Flow
# Add Raw → Get Raw → Rotate → Delete Raw
# ============================================================================

@pytest.mark.integration
class TestFileManagementFlow:
    """Tests file management workflow."""
    
    def test_file_lifecycle(self, real_engine_with_temp_workspace):
        """Test raw file lifecycle."""
        engine = real_engine_with_temp_workspace
        
        # Setup project
        engine.project_manager.project_crud.register_project("file_proj", "File", str(engine.project_manager.workspace_root / "file_proj"))
        engine.project_manager.project_setup._ensure_layout(engine.project_manager._project_root("file_proj"))
        engine.project_manager.project_setup._init_jobs_db(str(engine.project_manager._project_root("file_proj") / "jobs.db"))
        
        # 1. Add raw files
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"test")
            f_path = f.name
        
        try:
            res = engine.add_project_files("file_proj", [f_path], type="raw")
            assert res["status"] == "added"
            
            # 2. Get raw files
            files = engine.get_raw_files("file_proj")
            assert len(files) == 1
            
            # 3. Delete raw file
            filename = os.path.basename(f_path)
            res = engine.delete_raw_file("file_proj", filename)
            assert res["status"] == "deleted"
            
            # 4. Verify deleted
            files = engine.get_raw_files("file_proj")
            assert len(files) == 0
            
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)


# ============================================================================
# Use Case 5: API Full Workflow
# Similar to Engine lifecycle but through API endpoints
# ============================================================================

@pytest.mark.integration
class TestAPIFullWorkflow:
    """Tests full workflow through API endpoints."""
    
    def test_api_project_lifecycle(self, mock_engine_for_api):
        """Test creating and processing a project via API."""
        mock = mock_engine_for_api
        
        # 1. Create project
        mock.create_project.return_value = {"status": "created_new"}
        files = {"files": ("test.jpg", b"image", "image/jpeg")}
        res = client.post("/api/projects/", data={"project_id": "api_proj"}, files=files)
        assert res.status_code == 200
        
        # 2. Get raw files
        mock.get_raw_files.return_value = [{"filename": "test.jpg"}]
        res = client.get("/api/projects/api_proj/raw_files")
        assert res.status_code == 200
        
        # 3. Run split
        mock.run_splitting.return_value = {"status": "split_completed"}
        res = client.post("/api/projects/api_proj/run_split")
        assert res.status_code == 200
        
        # 4. Run OCR
        mock.run_ocr.return_value = {"status": "ocr_started"}
        res = client.post("/api/projects/api_proj/run_ocr")
        assert res.status_code == 200
        
        # 5. Run LLM
        mock.run_llm.return_value = {"status": "llm_started"}
        res = client.post("/api/projects/api_proj/run_llm")
        assert res.status_code == 200
        
        # 6. Export
        mock.run_excel.return_value = "output.xlsx"
        res = client.post("/api/projects/api_proj/run_export")
        assert res.status_code == 200
        
        # 7. Archive
        mock.archive_project.return_value = {"status": "sealed"}
        res = client.post("/api/projects/api_proj/run_archive")
        assert res.status_code == 200
        
        # 8. Delete project
        res = client.delete("/api/projects/api_proj")
        assert res.status_code == 200
