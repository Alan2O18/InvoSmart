"""
workers.py 單元測試

測試 _load_image 函數與 global_receipt_worker_loop 的核心邏輯。
"""
import pytest
import numpy as np
import cv2
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from queue import Queue
import threading

from backend.engine.workers import _load_image, global_receipt_worker_loop


# ============================================================================
# _load_image 測試
# ============================================================================

class TestLoadImage:
    """測試圖片讀取函數"""

    def test_load_valid_image(self, tmp_path):
        """讀取有效 JPEG 圖片"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[30:70, 30:70] = (128, 128, 128)
        path = str(tmp_path / "test.jpg")
        cv2.imencode(".jpg", img)[1].tofile(path)

        result = _load_image(path)
        assert result is not None
        assert result.shape[0] > 0
        assert result.shape[1] > 0

    def test_load_nonexistent_file(self):
        """讀取不存在的檔案 → FileNotFoundError"""
        with pytest.raises(FileNotFoundError, match="圖片不存在"):
            _load_image("nonexistent_image_xyz.jpg")

    def test_load_corrupted_file(self, tmp_path):
        """讀取損壞的檔案 → ValueError"""
        path = str(tmp_path / "broken.jpg")
        with open(path, "wb") as f:
            f.write(b"this is not an image")

        with pytest.raises(ValueError, match="無法解碼"):
            _load_image(path)

    def test_load_png(self, tmp_path):
        """讀取 PNG 圖片"""
        img = np.ones((50, 50, 3), dtype=np.uint8) * 200
        path = str(tmp_path / "test.png")
        cv2.imencode(".png", img)[1].tofile(path)

        result = _load_image(path)
        assert result is not None
        assert len(result.shape) == 3


# ============================================================================
# global_receipt_worker_loop 測試
# ============================================================================

class TestWorkerLoop:
    """測試 Worker 迴圈的邏輯"""

    def test_worker_processes_task(self, tmp_path):
        """Worker 從佇列取任務並處理"""
        # 建立測試圖片
        img_path = str(tmp_path / "receipt.jpg")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imencode(".jpg", img)[1].tofile(img_path)

        # Mock engine
        engine = MagicMock()
        engine._shutdown_event = threading.Event()
        engine.task_queue = Queue()

        # 模擬 job
        mock_job = {
            "job_id": "job1",
            "image_path": img_path,
            "status": "pending",
        }
        engine.get_job_repo.return_value.get_job.return_value = mock_job
        engine.receipt_processor.process.return_value = {
            "success": True,
            "result": {"key": "val"},
            "metadata": {"stats": {}, "qr_detected": False},
        }

        # 加入任務
        engine.task_queue.put(("proj1", "job1"))

        # 設定 shutdown event (延遲觸發)
        def shutdown_after():
            import time
            time.sleep(0.5)
            engine._shutdown_event.set()

        t = threading.Thread(target=shutdown_after, daemon=True)
        t.start()

        # 執行 worker loop
        global_receipt_worker_loop(engine)

        # 驗證
        engine.claim_job.assert_called_once_with("proj1", "job1")
        engine.complete_job.assert_called_once()

    def test_worker_handles_missing_job(self, tmp_path):
        """Worker 處理不存在的 job"""
        engine = MagicMock()
        engine._shutdown_event = threading.Event()
        engine.task_queue = Queue()
        engine.get_job_repo.return_value.get_job.return_value = None

        engine.task_queue.put(("proj1", "missing_job"))

        def shutdown_after():
            import time
            time.sleep(0.5)
            engine._shutdown_event.set()

        t = threading.Thread(target=shutdown_after, daemon=True)
        t.start()

        global_receipt_worker_loop(engine)

        engine.claim_job.assert_not_called()
        engine.complete_job.assert_not_called()

    def test_worker_handles_processing_error(self, tmp_path):
        """Worker 處理失敗時呼叫 fail_job"""
        img_path = str(tmp_path / "receipt.jpg")
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.imencode(".jpg", img)[1].tofile(img_path)

        engine = MagicMock()
        engine._shutdown_event = threading.Event()
        engine.task_queue = Queue()

        mock_job = {"job_id": "job2", "image_path": img_path, "status": "pending"}
        engine.get_job_repo.return_value.get_job.return_value = mock_job
        engine.receipt_processor.process.side_effect = RuntimeError("VLM boom")

        engine.task_queue.put(("proj1", "job2"))

        def shutdown_after():
            import time
            time.sleep(0.5)
            engine._shutdown_event.set()

        t = threading.Thread(target=shutdown_after, daemon=True)
        t.start()

        global_receipt_worker_loop(engine)

        engine.fail_job.assert_called_once()
