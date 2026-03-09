import pytest
import numpy as np
import threading
import time
from unittest.mock import MagicMock, AsyncMock, patch
from backend.engine.workers import global_receipt_worker_loop

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    # threading.Event to control breaking out of the while loop
    engine._shutdown_event = threading.Event()
    
    # Task queue mock
    engine.task_queue = MagicMock()
    
    # Async methods that will be called via loop.run_until_complete
    engine.claim_job = AsyncMock()
    engine.complete_job = AsyncMock()
    engine.fail_job = AsyncMock()
    
    # Receipt processor mock
    engine.receipt_processor = MagicMock()
    
    # Job repo
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "fake/path.jpg"})
    engine.get_job_repo.return_value = job_repo
    
    return engine

def test_worker_loop_timeout_exit(mock_engine, monkeypatch):
    # Test that when the shutdown event is triggered quickly, it exits gracefully
    def mock_get(timeout):
        # Trigger shutdown immediately during the first get
        mock_engine._shutdown_event.set()
        raise Exception("Timeout")
        
    mock_engine.task_queue.get.side_effect = mock_get
    
    global_receipt_worker_loop(mock_engine)
    
    mock_engine.claim_job.assert_not_called()

@patch('backend.utils.utils.cv_imread_chinese')
def test_worker_loop_process_success(mock_load_image, mock_engine):
    # Setup happy path
    dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)
    mock_load_image.return_value = dummy_img
    
    mock_engine.receipt_processor.process.return_value = {
        "success": True,
        "result": {"header": "OK"},
        "validation": True,
        "metadata": {"stats": {}, "qr_detected": True}
    }
    
    # Simulate grabbing one task then shutting down
    def auto_shutdown(*args, **kwargs):
        mock_engine._shutdown_event.set()
        return ("proj1", "j1")
        
    mock_engine.task_queue.get.side_effect = auto_shutdown
    
    global_receipt_worker_loop(mock_engine)
    
    mock_engine.claim_job.assert_called_once_with("proj1", "j1")
    mock_engine.complete_job.assert_called_once_with(
        "proj1", "j1",
        vlm_result={"header": "OK"},
        validation=True,
        stats={},
        qr_verified=True
    )

@patch('backend.utils.utils.cv_imread_chinese')
def test_worker_loop_process_failure_from_receipt_processor(mock_load_image, mock_engine):
    mock_load_image.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
    
    mock_engine.receipt_processor.process.return_value = {
        "success": False,
        "error": "Blurry image"
    }
    
    def auto_shutdown(*args, **kwargs):
        mock_engine._shutdown_event.set()
        return ("proj1", "j1")
        
    mock_engine.task_queue.get.side_effect = auto_shutdown
    
    global_receipt_worker_loop(mock_engine)
    
    mock_engine.claim_job.assert_called_once_with("proj1", "j1")
    mock_engine.fail_job.assert_called_once_with("proj1", "j1", "Blurry image")

@patch('backend.utils.utils.cv_imread_chinese')
def test_worker_loop_process_image_load_error(mock_load_image, mock_engine):
    # Test handling of FileNotFoundError during _load_image
    mock_load_image.side_effect = FileNotFoundError("Missing file")
    
    def auto_shutdown(*args, **kwargs):
        mock_engine._shutdown_event.set()
        return ("proj1", "j1")
        
    mock_engine.task_queue.get.side_effect = auto_shutdown
    
    global_receipt_worker_loop(mock_engine)
    
    mock_engine.fail_job.assert_called_once_with("proj1", "j1", "圖片讀取失敗: Missing file")
    mock_engine.receipt_processor.process.assert_not_called()


