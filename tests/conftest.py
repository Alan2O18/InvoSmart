import sys
import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Mock ollama globally before any imports
sys.modules["ollama"] = MagicMock()
sys.modules["paddleocr"] = MagicMock()
sys.modules["paddle"] = MagicMock() # Just in case
sys.modules["cv2"] = MagicMock()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("sys.executable", sys.executable)
print("which python", shutil.which("python"))

from backend.main import app
from backend.engine import engine

@pytest.fixture(scope="function")
def temp_workspace():
    """Creates a temporary workspace and cleans it up after the test."""
    test_dir = tempfile.mkdtemp()
    yield test_dir
    shutil.rmtree(test_dir, ignore_errors=True)

@pytest.fixture(scope="function")
def mock_engine_for_api():
    """
    Patches the global engine instance for API tests.
    Returns the mock object to configure return values.
    """
    
    with patch("backend.routers.projects.engine") as mock:
        # Default mock behaviors to avoid NoneType errors
        mock.project_manager.list_projects.return_value = []
        mock.project_manager.get_project_status.return_value = {}
        mock.project_manager.list_groups.return_value = []
        yield mock

@pytest.fixture(scope="function")
def real_engine_with_temp_workspace(temp_workspace):
    """
    Configures the real Engine singleton to use a temporary workspace.
    Mocks heavy handlers (OCR, LLM) but keeps core logic.
    """
    # Configure paths
    workspace_root = Path(temp_workspace)
    global_db_path = workspace_root / "projects.db"
    
    # Update Engine's ProjectManager config
    engine.project_manager.workspace_root = workspace_root
    engine.project_manager.global_db_path = global_db_path
    
    # Update sub-components
    engine.project_manager.project_crud.global_db_path = global_db_path
    engine.project_manager.project_setup.workspace_root = workspace_root
    
    # Ensure DB exists
    engine.project_manager.project_crud._ensure_global_db()
    
    # Mock heavy handlers
    engine.ocr_handler = MagicMock()
    engine.ocr_handler.process_image.return_value = "Mock OCR Text"
    
    engine.llm_handler = MagicMock()
    engine.llm_handler.structure_with_llm.return_value = {
        "corrected_full_text": "Mock Corrected",
        "structured_data": {"Vendor": "TestVendor"}
    }
    
    engine.receipt_splitter = MagicMock()
    engine.receipt_splitter.split_scanned_images.return_value = ["split_1.jpg"]
    
    # Reset state if needed (though we are using the same instance)
    engine.active_workers = {}
    engine.task_managers = {}
    
    return engine
