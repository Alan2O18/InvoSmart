"""
Integration Use Case Tests

Tests end-to-end workflows that combine multiple Engine/API operations.
Updated for Global Worker + Dependency Injection architecture.
"""
import pytest
import os
import time
import tempfile
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app
from backend import dependencies

client = TestClient(app)


# ============================================================================
# Use Case 1: Full Project Lifecycle
# Create → Upload → Split → OCR → LLM → Export → Archive
# ============================================================================

@pytest.mark.integration
class TestFullProjectLifecycle:
    """Tests the complete project processing lifecycle."""
    
    def test_complete_workflow_engine(self, test_engine):
        """Test full lifecycle through Engine (Global Worker architecture)."""
        engine = test_engine
        
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
                root = engine.project_repo._project_root(proj_id)
                (root / "分割發票" / "split_0.jpg").touch()
                tm = engine.get_task_manager(proj_id)
                tm.insert_job("job_0", "分割發票/split_0.jpg")
                return {"status": "split_completed"}
            
            engine.file_ops.run_splitting = MagicMock(side_effect=mock_split)
            res = engine.run_splitting("lifecycle_proj")
            assert res["status"] == "split_completed"
            
            # 4. Verify job created
            tm = engine.get_task_manager("lifecycle_proj")
            jobs = tm.list_jobs()
            assert len(jobs) == 1
            assert jobs[0]["status"] == "ready"
            
            # 5. Run VLM processing (queues jobs)
            res = engine.run_processing("lifecycle_proj")
            assert res["status"] == "processing_queued"
            assert res["queued_count"] == 1
            
            # Verify job marked as pending
            job = tm.get_job("job_0")
            assert job["status"] == "pending"
            
            # Manually complete VLM for testing (simulate worker)
            tm.complete_vlm("job_0", {
                "store_name": "Test Store",
                "total": 100,
                "items": [{"name": "Item 1", "price": 100}]
            })
            
            # 6. Verify VLM completed
            job = tm.get_job("job_0")
            assert job["status"] == "done"
            assert job["vlm_result_json"] is not None
            
            # 7. Export (mocked)
            engine.export_handler.run_excel = MagicMock(return_value="lifecycle_proj.xlsx")
            res = engine.run_excel("lifecycle_proj")
            assert res == "lifecycle_proj.xlsx"
            
            # 8. Archive (mocked)
            engine.export_handler.seal_project = MagicMock(return_value={"status": "sealed"})
            res = engine.archive_project("lifecycle_proj")
            assert res["status"] == "sealed"
            
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)


# ============================================================================
# Use Case 2: Partial Reprocessing (VLM-First)
# Create → Split → Process single jobs
# ============================================================================

@pytest.mark.integration
class TestPartialReprocessing:
    """Tests reprocessing specific jobs (VLM-First architecture)."""
    
    def test_single_job_reprocessing(self, test_engine):
        """Test VLM processing on a single job."""
        engine = test_engine
        
        # Setup project with multiple jobs
        engine.project_repo.register_project("partial_proj", "Partial", str(engine.project_repo.workspace_root / "partial_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("partial_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("partial_proj") / "jobs.db"))
        
        tm = engine.get_task_manager("partial_proj")
        tm.insert_job("job1", "img1.jpg")
        tm.insert_job("job2", "img2.jpg")
        tm.insert_job("job3", "img3.jpg")
        
        # Complete VLM on job1 and job2
        tm.complete_vlm("job1", {"store_name": "Store1", "total": 100})
        tm.complete_vlm("job2", {"store_name": "Store2", "total": 200})
        
        # Run single processing on job3 (just queues)
        res = engine.run_single_processing("partial_proj", "job3")
        assert res["status"] == "queued"
        assert res["job_id"] == "job3"
        
        # Verify job3 marked as pending
        job3 = tm.get_job("job3")
        assert job3["status"] == "pending"

    def test_single_llm_reprocessing(self, test_engine):
        """Test reprocessing a single job that was already done."""
        engine = test_engine
        
        # Setup project
        engine.project_repo.register_project("single_llm_proj", "LLM", str(engine.project_repo.workspace_root / "single_llm_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("single_llm_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("single_llm_proj") / "jobs.db"))
        
        tm = engine.get_task_manager("single_llm_proj")
        tm.insert_job("target_job", "img.jpg")
        
        # Run single processing (just queues)
        res = engine.run_single_processing("single_llm_proj", "target_job")
        assert res["status"] == "queued"
        assert res["job_id"] == "target_job"
        
        # Verify job marked as pending
        job = tm.get_job("target_job")
        assert job["status"] == "pending"


# ============================================================================
# Use Case 3: Group Management Flow
# Create Group → Assign to Project → List → Delete
# ============================================================================

@pytest.mark.integration
class TestGroupManagementFlow:
    """Tests group management workflow."""
    
    def test_group_lifecycle(self, test_engine):
        """Test full group lifecycle."""
        engine = test_engine
        
        # 1. Create groups
        engine.project_repo.upsert_group("教學組", "Alice")
        engine.project_repo.upsert_group("研究組", "Bob")
        
        # 2. List groups
        groups = engine.project_repo.list_groups()
        assert len(groups) >= 2
        
        # 3. Create project and assign group via activity info
        engine.project_repo.register_project("grouped_proj", "Grouped", str(engine.project_repo.workspace_root / "grouped_proj"))
        engine.project_repo.update_activity_info("grouped_proj", {"group_name": "教學組"})
        
        # 4. Verify assignment
        proj = engine.project_repo.get_project("grouped_proj")
        assert proj["metadata"]["group_name"] == "教學組"
        
        # 5. Update group
        engine.project_repo.upsert_group("教學組", "Charlie")  # New leader
        
        groups = engine.project_repo.list_groups()
        teaching_group = next(g for g in groups if g["group_name"] == "教學組")
        assert teaching_group["leader_name"] == "Charlie"
        
        # 6. Delete unused group
        engine.project_repo.delete_group("研究組")
        
        groups = engine.project_repo.list_groups()
        assert not any(g["group_name"] == "研究組" for g in groups)


# ============================================================================
# Use Case 4: File Management Flow
# Add Raw → Get Raw → Rotate → Delete Raw
# ============================================================================

@pytest.mark.integration
class TestFileManagementFlow:
    """Tests file management workflow."""
    
    def test_file_lifecycle(self, test_engine):
        """Test raw file lifecycle."""
        engine = test_engine
        
        # Setup project
        engine.project_repo.register_project("file_proj", "File", str(engine.project_repo.workspace_root / "file_proj"))
        engine.project_repo._ensure_layout(engine.project_repo._project_root("file_proj"))
        engine.project_repo._init_jobs_db(str(engine.project_repo._project_root("file_proj") / "jobs.db"))
        
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
    """Tests full workflow through API endpoints (VLM-First)."""
    
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
        
        # 4. Run VLM processing (VLM-First)
        mock.run_processing.return_value = {"status": "processing_queued", "queued_count": 1}
        res = client.post("/api/projects/api_proj/run_processing")
        assert res.status_code == 200
        
        # 5. Export
        mock.run_excel.return_value = "output.xlsx"
        res = client.post("/api/projects/api_proj/run_export")
        assert res.status_code == 200
        
        # 6. Archive
        mock.archive_project.return_value = {"status": "sealed"}
        res = client.post("/api/projects/api_proj/run_archive")
        assert res.status_code == 200
        
        # 7. Delete project
        res = client.delete("/api/projects/api_proj")
        assert res.status_code == 200
