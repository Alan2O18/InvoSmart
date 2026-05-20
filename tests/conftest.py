import sys
import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# ============================================================================
# Lazy Loading Protection for Heavy Dependencies
# Only mock when the module hasn't been loaded yet
# ============================================================================

def _create_lazy_mock(module_name):
    """Create a mock that can be configured by tests."""
    mock = MagicMock()
    mock._is_test_mock = True
    return mock

# Only mock if not already imported
if "ollama" not in sys.modules:
    sys.modules["ollama"] = _create_lazy_mock("ollama")

if "paddleocr" not in sys.modules:
    sys.modules["paddleocr"] = _create_lazy_mock("paddleocr")

if "paddle" not in sys.modules:
    sys.modules["paddle"] = _create_lazy_mock("paddle")

# Add project root to path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("sys.executable", sys.executable)
print("which python", shutil.which("python"))

# Import after mocking
from backend.main import app
from backend import dependencies


# ============================================================================
# Core Fixtures
# ============================================================================

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base

@pytest_asyncio.fixture
async def async_session_factory():
    """提供測試用的記憶體內非同步 Session Factory"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    
    await engine.dispose()


@pytest.fixture(scope="function")
def temp_workspace():
    """Creates a temporary workspace and cleans it up after the test."""
    test_dir = tempfile.mkdtemp()
    yield Path(test_dir)
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def mock_ocr_handler():
    """Mock OCR handler for testing."""
    mock = MagicMock()
    mock.do_paddleocr.return_value = [{"text": "test", "box": [0, 0, 100, 100]}]
    mock.reconstruct_layout.return_value = "Mock OCR Text"
    mock.process_receipt.return_value = "Mock Receipt Text"
    return mock


@pytest.fixture
def mock_llm_handler():
    """Mock LLM handler for testing."""
    mock = MagicMock()
    mock.structure_with_llm.return_value = {
        "corrected_full_text": "Mock Corrected",
        "structured_data": {"Vendor": "TestVendor"}
    }
    return mock


@pytest.fixture
def mock_receipt_splitter():
    """Mock receipt splitter for testing."""
    mock = MagicMock()
    mock.split_scanned_images.return_value = ["split_1.jpg"]
    return mock


@pytest.fixture
def mock_rapidocr():
    """Mock RapidOCR handler wrapper."""
    mock = MagicMock()
    mock.do_ocr.return_value = ([], {})
    mock.get_high_confidence_text.return_value = []
    return mock

@pytest.fixture
def mock_vision_handler():
    """Mock VisionHandler."""
    mock = MagicMock()
    mock.image_to_markdown.return_value = ("# Markdown", {})
    mock.describe_image.return_value = ("Description", {})
    return mock

@pytest.fixture
def mock_qr_handler():
    """Mock QRHandler."""
    mock = MagicMock()
    mock.detect_and_decode.return_value = (None, None)
    return mock

@pytest.fixture
def mock_audit_handler():
    """Mock AuditHandler."""
    mock = MagicMock()
    mock.audit_electronic.return_value = {"is_valid": True}
    mock.audit_traditional.return_value = {"is_valid": True}
    return mock


@pytest_asyncio.fixture
async def test_engine(temp_workspace, mock_ocr_handler, mock_llm_handler, mock_receipt_splitter, async_session_factory):
    """
    創建測試用 Engine 實例。
    
    特點：
    - 使用臨時工作區
    - 注入 mock handlers
    - 不啟動 Workers (start_workers=False)
    - 自動設置為全局實例供 Depends 使用
    """
    from backend.engine.core import Engine
    from backend.repositories.project_repository import ProjectRepository
    
    # 創建使用臨時目錄的 ProjectRepository
    pm_config = {
        "workspace_root": str(temp_workspace),
        "global_db_path": str(temp_workspace / "projects.db")
    }
    project_repo = ProjectRepository(config=pm_config, session_factory=async_session_factory)
    
    # 創建 Engine，注入所有依賴
    engine = Engine(
        config={
            "project_manager_settings": pm_config,
            "ocr_settings": {"language": "chinese_cht", "use_angle_cls": True},
            "llm_settings": {"model_name": "test-model"}
        },
        project_repo=project_repo,
        receipt_splitter=mock_receipt_splitter,
        start_workers=False,  # 關鍵：不啟動 Workers
        session_factory=async_session_factory
    )
    
    # 設置為全局實例（供 FastAPI Depends 使用）
    dependencies.set_engine(engine)
    
    yield engine
    
    # 清理：重置全局實例
    dependencies.reset_engine()


@pytest.fixture
def mock_engine_for_api():
    """
    Patches the engine for API tests using dependency injection.
    """
    from contextlib import ExitStack
    from unittest.mock import AsyncMock
    
    mock = MagicMock()
    mock.recover_pending_tasks = AsyncMock()
    mock.stop_workers = AsyncMock()
    mock.project_repo.list_projects.return_value = []
    mock.project_repo.get_project_status.return_value = {}
    mock.project_repo.list_groups.return_value = []
    
    # 設置為全局實例
    dependencies.set_engine(mock)
    
    yield mock
    
    # 清理
    dependencies.reset_engine()


@pytest.fixture
def client(test_engine):
    """FastAPI TestClient with injected engine."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest_asyncio.fixture
async def db_session(async_session_factory):
    """Provide a database session for testing."""
    async with async_session_factory() as session:
        yield session



@pytest.fixture
def mock_app_client(mock_engine_for_api):
    """
    FastAPI TestClient utilizing the pure mock engine instance.
    Essential for rapidly testing Router boundaries without database hits.
    """
    from fastapi.testclient import TestClient
    from backend.dependencies import get_db, get_sync_db
    
    # Provide simple yield mocks so we don't hit 503
    async def override_get_db():
        from unittest.mock import AsyncMock
        yield AsyncMock()
        
    def override_get_sync_db():
        from unittest.mock import MagicMock
        yield MagicMock()
        
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_sync_db] = override_get_sync_db
    
    with TestClient(app) as client:
        yield client
        
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_sync_db, None)


@pytest.fixture(scope="function")
def fresh_ollama_mock():
    """
    Provides a fresh, reset ollama mock for tests that need it.
    """
    mock_ollama = sys.modules.get("ollama")
    if mock_ollama and hasattr(mock_ollama, "_is_test_mock"):
        mock_ollama.reset_mock()
        mock_ollama.list.return_value = []
        mock_ollama.chat.reset_mock()
        mock_ollama.chat.side_effect = None
        mock_ollama.chat.return_value = {"message": {"content": "{}"}}
    yield mock_ollama
    if mock_ollama and hasattr(mock_ollama, "_is_test_mock"):
        mock_ollama.chat.side_effect = None
        mock_ollama.chat.reset_mock()
