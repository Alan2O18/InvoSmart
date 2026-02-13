# Workers - VLM-First 背景處理 Worker
"""
統一收據處理 Worker (VLM-First 架構)

只使用一個 worker 處理所有任務，流程：
1. 從佇列取出任務
2. 呼叫 ReceiptProcessor.process() 
3. 透過 Engine 儲存結果到資料庫
"""
import logging
import cv2
import time
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


def global_receipt_worker_loop(engine):
    """
    VLM-First Worker 主迴圈。
    
    Args:
        engine: Engine 實例
    """
    logger.info("[Worker] VLM-First Worker 已啟動，等待任務...")
    
    while not engine._shutdown_event.is_set():
        try:
            # 阻塞式獲取任務 (timeout 1 秒)
            try:
                task = engine.task_queue.get(timeout=1.0)
                project_id, job_id = task[0], task[1]
            except:
                continue
            
            logger.info(f"[Worker] 開始處理: {project_id}/{job_id}")
            
            # 獲取 JobRepository
            try:
                job_repo = engine.get_job_repo(project_id)
            except Exception as e:
                logger.error(f"[Worker] 無法獲取 JobRepository: {e}")
                continue
            
            # 獲取 Job
            job = job_repo.get_job(job_id)
            if not job:
                logger.warning(f"[Worker] Job 不存在: {job_id}")
                continue
            
            # Claim job (set to running)
            engine.claim_job(project_id, job_id)
            
            # 讀取圖片
            image_path = job["image_path"]
            try:
                image = _load_image(image_path)
            except Exception as e:
                logger.error(f"[Worker] 圖片讀取失敗: {e}")
                engine.fail_job(project_id, job_id, f"圖片讀取失敗: {e}")
                continue
            
            # VLM 處理
            try:
                result = engine.receipt_processor.process(image)
                
                if result.get("success"):
                    engine.complete_job(
                        project_id, job_id,
                        vlm_result=result.get("result", {}),
                        validation=result.get("validation"),
                        stats=result.get("metadata", {}).get("stats"),
                        qr_verified=result.get("metadata", {}).get("qr_detected", False)
                    )
                    logger.info(f"[Worker] ✓ 處理完成: {job_id}")
                else:
                    error_msg = result.get("error", "Unknown error")
                    engine.fail_job(project_id, job_id, error_msg)
                    logger.error(f"[Worker] ✗ 處理失敗: {job_id} - {error_msg}")
                    
            except Exception as e:
                logger.error(f"[Worker] 處理異常: {e}", exc_info=True)
                engine.fail_job(project_id, job_id, str(e))
            
        except Exception as e:
            logger.error(f"[Worker] Worker 迴圈異常: {e}", exc_info=True)
            time.sleep(1)
    
    logger.info("[Worker] Worker 已停止")


def _load_image(image_path: str):
    """載入圖片，支援中文路徑"""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"圖片不存在: {image_path}")
    
    # OpenCV 中文路徑支援
    with open(path, 'rb') as f:
        data = np.frombuffer(f.read(), dtype=np.uint8)
    
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"無法解碼圖片: {image_path}")
    
    return image
