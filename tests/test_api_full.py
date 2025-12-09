import sys
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch
import json
import tempfile
from pathlib import Path

# 1. Setup Mocks BEFORE importing backend modules that might trigger init
# Mock ollama to avoid SystemError during LLMHandler init
sys.modules["ollama"] = MagicMock()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now we can import
from fastapi.testclient import TestClient
from backend.main import app
from backend.engine import engine

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
            "llm_settings": {"model_name": "test-model"}
        }
        
        # Re-initialize engine with test config
        # Since Engine is a singleton and might be already initialized by imports,
        # we need to force re-init or patch its components.
        # Easier to just patch the project_manager and handlers within the existing engine instance.
        
        # Patch ProjectManager to use test paths
        engine.project_manager.workspace_root = Path(cls.config["project_manager_settings"]["workspace_root"])
        engine.project_manager.global_db_path = Path(cls.config["project_manager_settings"]["global_db_path"])
        engine.project_manager.project_crud.global_db_path = engine.project_manager.global_db_path
        engine.project_manager.project_setup.workspace_root = engine.project_manager.workspace_root
        engine.project_manager.project_crud._ensure_global_db() # Re-create DB in test dir
        
        # Mock heavy handlers
        engine.ocr_handler.process_image = MagicMock(return_value="Mock OCR Text")
        engine.llm_handler.structure_with_llm = MagicMock(return_value={
            "corrected_full_text": "Mock Corrected",
            "structured_data": {"Vendor": "TestVendor", "Total": 100}
        })
        engine.receipt_splitter.split_scanned_images = MagicMock(return_value=["split_1.jpg", "split_2.jpg"])
        
        # Mock FileOps to avoid real file splitting logic but simulate file creation
        original_run_splitting = engine.file_ops.run_splitting
        
        def mock_run_splitting(project_id, target_files=None):
            # Simulate creating split files
            root = engine.project_manager._project_root(project_id)
            split_dir = root / "切分後圖片"
            split_dir.mkdir(parents=True, exist_ok=True)
            (split_dir / "split_1.jpg").touch()
            (split_dir / "split_2.jpg").touch()
            
            # Update jobs.db
            tm = engine.get_task_manager(project_id)
            tm.enqueue("split_1.jpg", "split_1.jpg")
            tm.enqueue("split_2.jpg", "split_2.jpg")
            
            engine.project_manager.update_project_status(project_id, "SPLIT")
            return {"status": "splitting_completed", "new_files": ["split_1.jpg", "split_2.jpg"]}
            
        engine.file_ops.run_splitting = MagicMock(side_effect=mock_run_splitting)

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir)

    def test_01_create_project(self):
        # Create a dummy file to upload
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

    def test_06_run_ocr(self):
        # This will trigger the mocked worker
        # Since we are using threads, we might need to wait or mock the thread starting to run synchronously
        # But for this test, we just want to ensure the API returns success and status updates
        
        # Mock start_cpu_worker to run synchronously for test
        with patch("backend.engine.core.start_cpu_worker") as mock_worker:
            response = self.client.post("/api/projects/test_proj_1/run_ocr")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "ocr_started")
            mock_worker.assert_called()

    def test_07_run_llm(self):
        with patch("backend.engine.core.start_gpu_worker") as mock_worker:
            response = self.client.post("/api/projects/test_proj_1/run_llm")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "llm_started")
            mock_worker.assert_called()

    def test_08_export_archive(self):
        # Mock export handler methods
        engine.export_handler.run_excel = MagicMock(return_value="path/to/excel.xlsx")
        engine.export_handler.seal_project = MagicMock(return_value={"status": "sealed"})
        
        response = self.client.post("/api/projects/test_proj_1/run_export")
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post("/api/projects/test_proj_1/run_archive")
        self.assertEqual(response.status_code, 200)

    def test_09_regenerate(self):
        engine.export_handler.regenerate_from_archive = MagicMock(return_value="path/to/new_archive.zip")
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
