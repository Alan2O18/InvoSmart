"""
Comprehensive API Unit Tests

Tests all API endpoints with mocked Engine.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


# ============================================================================
# Project CRUD Endpoints
# ============================================================================

@pytest.mark.api
class TestAPIProjectCRUD:
    """Tests for project CRUD endpoints."""
    
    def test_list_projects(self, mock_engine_for_api):
        """GET / - List all projects."""
        mock_engine_for_api.project_repo.list_projects.return_value = [
            {"project_id": "p1", "name": "Project 1"},
            {"project_id": "p2", "name": "Project 2"}
        ]
        
        response = client.get("/api/projects/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_create_project(self, mock_engine_for_api):
        """POST / - Create a new project."""
        mock_engine_for_api.create_project.return_value = {"status": "created_new"}
        
        files = {"files": ("test.pdf", b"content", "application/pdf")}
        response = client.post(
            "/api/projects/",
            data={"project_id": "new_proj", "metadata": '{"key": "val"}'},
            files=files
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "created_new"

    def test_update_project(self, mock_engine_for_api):
        """PUT /{id} - Update project metadata."""
        response = client.put(
            "/api/projects/test_proj",
            json={"new_key": "new_val"}
        )
        
        assert response.status_code == 200
        mock_engine_for_api.project_repo.update_metadata.assert_called_with("test_proj", {"new_key": "new_val"})

    def test_delete_project(self, mock_engine_for_api):
        """DELETE /{id} - Delete a project."""
        response = client.delete("/api/projects/test_proj")
        
        assert response.status_code == 200
        mock_engine_for_api.project_repo.delete_project.assert_called_with("test_proj")

    def test_get_project_status(self, mock_engine_for_api):
        """GET /{id} - Get project status."""
        mock_engine_for_api.project_repo.get_project_status.return_value = {
            "ingested": True,
            "split": True,
            "processing": False,
            "processed": False,
            "suggested_status": "SPLIT"
        }
        
        response = client.get("/api/projects/test_proj")
        assert response.status_code == 200
        assert response.json()["suggested_status"] == "SPLIT"


# ============================================================================
# File Operations Endpoints
# ============================================================================

@pytest.mark.api
class TestAPIFileOps:
    """Tests for file operation endpoints."""
    
    def test_add_files_raw(self, mock_engine_for_api):
        """POST /{id}/add_files - Add raw files."""
        mock_engine_for_api.add_project_files.return_value = {"status": "added"}
        
        files = {"files": ("test.jpg", b"image", "image/jpeg")}
        response = client.post(
            "/api/projects/test_proj/add_files",
            data={"type": "raw"},
            files=files
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "added"

    def test_add_files_split(self, mock_engine_for_api):
        """POST /{id}/add_files - Add split files."""
        mock_engine_for_api.add_project_files.return_value = {"status": "added"}
        
        files = {"files": ("split.jpg", b"image", "image/jpeg")}
        response = client.post(
            "/api/projects/test_proj/add_files",
            data={"type": "split"},
            files=files
        )
        
        assert response.status_code == 200

    def test_rotate_image(self, mock_engine_for_api):
        """POST /{id}/rotate/{filename} - Rotate image."""
        mock_engine_for_api.rotate_image.return_value = {"status": "rotated"}
        
        response = client.post("/api/projects/test_proj/rotate/test.jpg?angle=90")
        assert response.status_code == 200
        mock_engine_for_api.rotate_image.assert_called_with("test_proj", "test.jpg", 90)

    def test_get_raw_files(self, mock_engine_for_api):
        """GET /{id}/raw_files - Get raw files."""
        mock_engine_for_api.get_raw_files.return_value = [
            {"filename": "file1.jpg", "split_count": 2},
            {"filename": "file2.jpg", "split_count": 0}
        ]
        
        response = client.get("/api/projects/test_proj/raw_files")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_delete_raw_file(self, mock_engine_for_api):
        """DELETE /{id}/raw_files/{filename} - Delete raw file."""
        mock_engine_for_api.delete_raw_file.return_value = {"status": "deleted"}
        
        response = client.delete("/api/projects/test_proj/raw_files/test.jpg")
        assert response.status_code == 200
        mock_engine_for_api.delete_raw_file.assert_called_with("test_proj", "test.jpg")


# ============================================================================
# Processing Endpoints
# ============================================================================

@pytest.mark.api
class TestAPIProcessing:
    """Tests for processing endpoints."""
    
    def test_run_split(self, mock_engine_for_api):
        """POST /{id}/run_split - Run splitting."""
        mock_engine_for_api.run_splitting.return_value = {"status": "split_completed"}
        
        response = client.post("/api/projects/test_proj/run_split")
        assert response.status_code == 200
        mock_engine_for_api.run_splitting.assert_called()

    def test_run_split_single(self, mock_engine_for_api):
        """POST /{id}/split/{filename} - Run splitting on single file."""
        mock_engine_for_api.run_split_single.return_value = {"status": "split_completed"}
        
        response = client.post("/api/projects/test_proj/split/test.jpg")
        assert response.status_code == 200
        mock_engine_for_api.run_split_single.assert_called()

    def test_run_processing(self, mock_engine_for_api):
        """POST /{id}/run_processing - Run VLM processing."""
        mock_engine_for_api.run_processing.return_value = {"status": "processing_queued", "queued_count": 3}
        
        response = client.post("/api/projects/test_proj/run_processing")
        assert response.status_code == 200
        mock_engine_for_api.run_processing.assert_called_with("test_proj")

    def test_run_single_processing(self, mock_engine_for_api):
        """POST /{id}/jobs/{job_id}/process - Run single VLM processing."""
        mock_engine_for_api.run_single_processing.return_value = {"status": "queued", "job_id": "job1"}
        
        response = client.post("/api/projects/test_proj/jobs/job1/process")
        assert response.status_code == 200
        mock_engine_for_api.run_single_processing.assert_called_with("test_proj", "job1")


# ============================================================================
# Job Endpoints
# ============================================================================

@pytest.mark.api
class TestAPIJobs:
    """Tests for job endpoints."""
    
    def test_delete_job(self, mock_engine_for_api):
        """DELETE /{id}/jobs/{job_id} - Delete job."""
        response = client.delete("/api/projects/test_proj/jobs/job1")
        
        assert response.status_code == 200
        mock_engine_for_api.delete_job.assert_called_with("test_proj", "job1")

    def test_get_project_jobs(self, mock_engine_for_api):
        """GET /{id}/jobs - Get project jobs."""
        # This endpoint accesses engine.project_manager._project_root directly
        # which is not covered by our fixture. We need to mock the entire chain.
        from pathlib import Path
        import sqlite3
        import tempfile
        
        # Create a temp db with jobs
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "jobs.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE jobs (
                    job_id TEXT PRIMARY KEY,
                    image_path TEXT,
                    status TEXT,
                    stage TEXT,
                    ocr_start_at REAL,
                    ocr_done_at REAL,
                    llm_start_at REAL,
                    llm_done_at REAL,
                    ocr_result_json TEXT,
                    llm_result_json TEXT,
                    created_at REAL,
                    updated_at REAL,
                    auto_advance INTEGER
                )
            """)
            conn.execute("INSERT INTO jobs (job_id, image_path, status, stage, created_at) VALUES ('j1', 'img.jpg', 'pending', 'ocr', 0)")
            conn.commit()
            conn.close()
            
            # Patch _project_root to return our temp dir
            mock_engine_for_api.project_repo._project_root.return_value = Path(tmpdir)
            
            response = client.get("/api/projects/test_proj/jobs")
            assert response.status_code == 200
            jobs = response.json()
            assert len(jobs) == 1
            assert jobs[0]["job_id"] == "j1"


# ============================================================================
# Export Endpoints
# ============================================================================

@pytest.mark.api
class TestAPIExport:
    """Tests for export endpoints."""
    
    def test_run_export(self, mock_engine_for_api):
        """POST /{id}/run_export - Run Excel export."""
        mock_engine_for_api.run_excel.return_value = "/path/to/file.xlsx"
        
        response = client.post("/api/projects/test_proj/run_export")
        assert response.status_code == 200
        mock_engine_for_api.run_excel.assert_called_with("test_proj")

    def test_run_archive(self, mock_engine_for_api):
        """POST /{id}/run_archive - Run archive."""
        mock_engine_for_api.archive_project.return_value = {"status": "sealed", "path": "/archive.zip"}
        
        response = client.post("/api/projects/test_proj/run_archive")
        assert response.status_code == 200
        mock_engine_for_api.archive_project.assert_called_with("test_proj")

    def test_regenerate(self, mock_engine_for_api):
        """POST /{id}/regenerate - Regenerate from archive."""
        mock_engine_for_api.regenerate_project.return_value = "/path/to/new.zip"
        
        response = client.post(
            "/api/projects/test_proj/regenerate",
            data={"excel_path": "/path/to/excel.xlsx"}
        )
        assert response.status_code == 200
        mock_engine_for_api.regenerate_project.assert_called_with("test_proj", "/path/to/excel.xlsx")


# ============================================================================
# Activity Info Endpoint
# ============================================================================

@pytest.mark.api
class TestAPIActivityInfo:
    """Tests for activity info endpoint."""
    
    def test_update_activity_info(self, mock_engine_for_api):
        """POST /{id}/activity_info - Update activity info."""
        info = {"group_name": "G1", "coordinator": "Alice"}
        
        response = client.post("/api/projects/test_proj/activity_info", json=info)
        assert response.status_code == 200
        mock_engine_for_api.project_repo.update_activity_info.assert_called_with("test_proj", info)


# ============================================================================
# Group Endpoints
# ============================================================================

@pytest.mark.api
class TestAPIGroups:
    """Tests for group management endpoints."""
    
    def test_list_groups(self, mock_engine_for_api):
        """GET /groups/list - List groups."""
        mock_engine_for_api.project_repo.list_groups.return_value = [
            {"group_name": "G1", "leader_name": "L1"},
            {"group_name": "G2", "leader_name": "L2"}
        ]
        
        response = client.get("/api/projects/groups/list")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_upsert_group(self, mock_engine_for_api):
        """POST /groups - Create/update group."""
        response = client.post(
            "/api/projects/groups",
            json={"group_name": "NewGroup", "leader_name": "Leader"}
        )
        
        assert response.status_code == 200
        mock_engine_for_api.project_repo.upsert_group.assert_called_with("NewGroup", "Leader")

    def test_delete_group(self, mock_engine_for_api):
        """DELETE /groups/{name} - Delete group."""
        response = client.delete("/api/projects/groups/TestGroup")
        
        assert response.status_code == 200
        mock_engine_for_api.project_repo.delete_group.assert_called_with("TestGroup")
