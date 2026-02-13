"""
Backend API Full Tests

Tests the full API workflow with mocked handlers.
Updated for Global Worker + Dependency Injection architecture.
"""
import sys
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch
import json
import tempfile
from pathlib import Path

# 1. Setup Mocks BEFORE importing backend modules that might trigger init
sys.modules["ollama"] = MagicMock()
sys.modules["paddleocr"] = MagicMock()
sys.modules["paddle"] = MagicMock()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can import
from fastapi.testclient import TestClient
from backend.main import app
from backend import dependencies
from backend.engine.core import Engine


class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temporary workspace for testing
        cls.test_dir = tempfile.mkdtemp()
        cls.config = {
            "project_manager_settings": {
                "workspace_root": cls.test_dir,
                "global_db_path": os.path.join(cls.test_dir, "projects.db")
            },
            "ocr_settings": {"language": "chinese_cht"},
            "llm_settings": {"model_name": "test-model"}
        }
        
        # Create mock handlers
        cls.mock_ocr_handler = MagicMock()
        cls.mock_ocr_handler.process_image.return_value = "Mock OCR Text"
        cls.mock_ocr_handler.do_paddleocr.return_value = []
        cls.mock_ocr_handler.reconstruct_layout.return_value = "Mock OCR Text"
        cls.mock_ocr_handler.process_receipt.return_value = "Mock Receipt Text"
        
        cls.mock_llm_handler = MagicMock()
        cls.mock_llm_handler.structure_with_llm.return_value = {
            "corrected_full_text": "Mock Corrected",
            "structured_data": {"Vendor": "TestVendor", "Total": 100}
        }
        
        cls.mock_receipt_splitter = MagicMock()
        cls.mock_receipt_splitter.split_scanned_images.return_value = ["split_1.jpg", "split_2.jpg"]
        
        # Create Engine with dependency injection
        cls.engine = Engine(
            config=cls.config,
            receipt_splitter=cls.mock_receipt_splitter,
            start_workers=False  # Don't start workers in test
        )
        
        # Set as global engine for API
        dependencies.set_engine(cls.engine)
        
        # Mock FileOps to avoid real file splitting logic but simulate file creation
        def mock_run_splitting(project_id, target_files=None):
            # Simulate creating split files
            root = cls.engine.project_repo._project_root(project_id)
            split_dir = root / "分割發票"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "split_1.jpg").touch()
            (split_dir / "split_2.jpg").touch()
            
            # Update jobs.db
            tm = cls.engine.get_task_manager(project_id)
            tm.insert_job("split_1", "split_1.jpg")
            tm.insert_job("split_2", "split_2.jpg")
            
            cls.engine.project_repo.update_project_status(project_id, "SPLIT")
            return {"status": "splitting_completed", "new_files": ["split_1.jpg", "split_2.jpg"]}
            
        cls.engine.file_ops.run_splitting = MagicMock(side_effect=mock_run_splitting)

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        dependencies.reset_engine()
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_create_project(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"dummy content")
            f_path = f.name
        
        try:
            with open(f_path, "rb") as f:
                response = self.client.post(
                    "/api/projects/",
                    data={"project_id": "test_proj_1", "metadata": '{"key": "val"}'},
                    files={"files": ("test.pdf", f, "application/pdf")}
                )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "created_new")
        finally:
            os.remove(f_path)

    def test_02_list_projects(self):
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, 200)
        projects = response.json()
        self.assertTrue(any(p["project_id"] == "test_proj_1" for p in projects))

    def test_03_update_activity_info(self):
        info = {
            "group_name": "TestGroup",
            "coordinator": "Alice",
            "teacher_count": 5
        }
        response = self.client.post("/api/projects/test_proj_1/activity_info", json=info)
        self.assertEqual(response.status_code, 200)
        
        # Verify
        response = self.client.get("/api/projects/")
        projects = response.json()
        proj = next(p for p in projects if p["project_id"] == "test_proj_1")
        self.assertEqual(proj["metadata"].get("group_name"), "TestGroup")
        self.assertEqual(proj["metadata"].get("teacher_count"), 5)

    def test_04_groups_management(self):
        # Create Group
        response = self.client.post("/api/projects/groups", json={"group_name": "G1", "leader_name": "L1"})
        self.assertEqual(response.status_code, 200)
        
        # List Groups
        response = self.client.get("/api/projects/groups/list")
        self.assertEqual(response.status_code, 200)
        groups = response.json()
        self.assertTrue(any(g["group_name"] == "G1" for g in groups))
        
        # Delete Group
        response = self.client.delete("/api/projects/groups/G1")
        self.assertEqual(response.status_code, 200)

    def test_05_run_split(self):
        response = self.client.post("/api/projects/test_proj_1/run_split")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "splitting_completed")

    def test_06_run_processing(self):
        """Test VLM processing API (VLM-First architecture)."""
        response = self.client.post("/api/projects/test_proj_1/run_processing")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)

    def test_08_export_archive(self):
        # Mock export handler methods
        self.engine.export_handler.run_excel = MagicMock(return_value="path/to/excel.xlsx")
        self.engine.export_handler.seal_project = MagicMock(return_value={"status": "sealed"})
        
        response = self.client.post("/api/projects/test_proj_1/run_export")
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post("/api/projects/test_proj_1/run_archive")
        self.assertEqual(response.status_code, 200)

    def test_09_regenerate(self):
        self.engine.export_handler.regenerate_from_archive = MagicMock(return_value="path/to/new_archive.zip")
        response = self.client.post("/api/projects/test_proj_1/regenerate", data={"excel_path": "dummy.xlsx"})
        self.assertEqual(response.status_code, 200)

    def test_10_delete_project(self):
        response = self.client.delete("/api/projects/test_proj_1")
        self.assertEqual(response.status_code, 200)
        
        # Verify deleted
        response = self.client.get("/api/projects/")
        projects = response.json()
        self.assertFalse(any(p["project_id"] == "test_proj_1" for p in projects))


if __name__ == "__main__":
    unittest.main()
