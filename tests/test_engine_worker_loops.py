import threading
from unittest.mock import AsyncMock, MagicMock, patch

from backend.engine.workers import global_receipt_worker_loop


class ControlledQueue:
    def __init__(self, items, shutdown_event):
        self._items = list(items)
        self._shutdown_event = shutdown_event

    def get(self, timeout=1.0):
        if self._items:
            return self._items.pop(0)
        self._shutdown_event.set()
        raise TimeoutError("queue empty")


def test_global_receipt_worker_loop_skips_missing_jobs():
    shutdown_event = threading.Event()
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value=None)

    engine = MagicMock()
    engine._shutdown_event = shutdown_event
    engine.task_queue = ControlledQueue([("proj1", "job-1")], shutdown_event)
    engine.get_job_repo.return_value = job_repo
    engine.claim_job = AsyncMock()
    engine.complete_job = AsyncMock()
    engine.fail_job = AsyncMock()

    global_receipt_worker_loop(engine)

    engine.claim_job.assert_not_awaited()
    engine.complete_job.assert_not_awaited()
    engine.fail_job.assert_not_awaited()
    engine.receipt_processor.process.assert_not_called()


def test_global_receipt_worker_loop_completes_successful_jobs():
    shutdown_event = threading.Event()
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"image_path": "image.jpg"})

    engine = MagicMock()
    engine._shutdown_event = shutdown_event
    engine.task_queue = ControlledQueue([("proj1", "job-2")], shutdown_event)
    engine.get_job_repo.return_value = job_repo
    engine.claim_job = AsyncMock()
    engine.complete_job = AsyncMock()
    engine.fail_job = AsyncMock()
    engine.receipt_processor.process.return_value = {
        "success": True,
        "result": {"supplier": "Store"},
        "validation": {"ok": True},
        "metadata": {"stats": {"total_time_s": 1.2}, "qr_detected": True},
    }

    with patch("backend.utils.utils.cv_imread_chinese", return_value="image-bytes"):
        global_receipt_worker_loop(engine)

    engine.claim_job.assert_awaited_once_with("proj1", "job-2")
    engine.complete_job.assert_awaited_once_with(
        "proj1",
        "job-2",
        vlm_result={"supplier": "Store"},
        validation={"ok": True},
        stats={"total_time_s": 1.2},
        qr_verified=True,
    )
    engine.fail_job.assert_not_awaited()


def test_global_receipt_worker_loop_fails_when_image_load_breaks():
    shutdown_event = threading.Event()
    job_repo = MagicMock()
    job_repo.get_job = AsyncMock(return_value={"image_path": "broken.jpg"})

    engine = MagicMock()
    engine._shutdown_event = shutdown_event
    engine.task_queue = ControlledQueue([("proj1", "job-3")], shutdown_event)
    engine.get_job_repo.return_value = job_repo
    engine.claim_job = AsyncMock()
    engine.complete_job = AsyncMock()
    engine.fail_job = AsyncMock()

    with patch("backend.utils.utils.cv_imread_chinese", side_effect=OSError("bad image")):
        global_receipt_worker_loop(engine)

    engine.fail_job.assert_awaited_once()
    assert engine.fail_job.await_args.args[:2] == ("proj1", "job-3")
    assert "圖片讀取失敗" in engine.fail_job.await_args.args[2]
    engine.complete_job.assert_not_awaited()
