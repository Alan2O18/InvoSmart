# backend/engine/workers.py
"""
Global Worker 模組

提供統一的收據處理 Worker：
- global_receipt_worker_loop: 處理完整收據管線（合併 OCR + LLM）

這個 Worker 在 Engine 啟動時創建，與 Server 同生共死。
使用 ReceiptProcessor 執行完整處理流程。
"""
import time
import logging
from backend.utils import utils

logger = logging.getLogger(__name__)


def global_receipt_worker_loop(engine):
    """
    統一收據處理 Worker 主迴圈。
    
    合併原有的 OCR 和 LLM Worker，
    使用 ReceiptProcessor 執行完整管線。
    
    Args:
        engine: Engine 實例，提供 task_queue、receipt_processor 和 get_task_manager 方法
    """
    logger.info("[GlobalReceiptWorker] Worker 已啟動，等待任務...")
    
    while not engine._shutdown_event.is_set():
        try:
            # 阻塞式獲取任務
            try:
                task = engine.task_queue.get(timeout=1.0)
                if len(task) == 3:
                    project_id, job_id, stage_limit = task
                else:
                    project_id, job_id = task
                    stage_limit = None
            except:
                continue
            
            logger.info(f"[GlobalReceiptWorker] 開始處理: {project_id}/{job_id} (Limit: {stage_limit})")
            
            # 獲取 TaskManager
            try:
                tm = engine.get_task_manager(project_id)
            except Exception as e:
                logger.error(f"[GlobalReceiptWorker] 無法獲取 TaskManager for {project_id}: {e}")
                engine.task_queue.task_done()
                continue
            
            # 確認任務狀態
            job = tm.get_job(job_id)
            if not job:
                logger.warning(f"[GlobalReceiptWorker] Job {job_id} 不存在，跳過")
                engine.task_queue.task_done()
                continue
            
            if job["status"] not in ("pending", "ready"):
                logger.info(f"[GlobalReceiptWorker] Job {job_id} 狀態為 {job['status']}，跳過")
                engine.task_queue.task_done()
                continue
            
            # 標記為 running
            tm._repository.update_job(
                job_id, 
                status="running"
            )
            tm._repository.emit_event(job_id, "processing_started", {})
            
            try:
                # 讀取圖片
                image_path = job["image_path"]
                image = utils.cv_imread_chinese(image_path)
                
                if stage_limit == "ocr":
                    # ===== OCR 階段 =====
                    logger.info("[GlobalReceiptWorker] ===== 進入 OCR 階段 =====")
                    result = engine.receipt_processor.process_ocr_only(image)
                    
                    ocr_result = result.get("ocr_result")
                    ocr_stats = result.get("ocr_stats")
                    
                    # 儲存 OCR 結果，設定 stage='llm', status='ready'
                    tm.complete_ocr(
                        job_id,
                        ocr_result=ocr_result,
                        stats=ocr_stats,
                        advance_to_stage_llm=True  # 設定 stage='llm', status='ready'
                    )
                    logger.info(f"[GlobalReceiptWorker] ✓ OCR 階段完成: {job_id}")
                    engine.task_queue.task_done()
                    continue
                
                if stage_limit == "llm":
                    # ===== LLM 階段 =====
                    # 從 DB 取得 OCR 結果，使用 process_llm_only 處理
                    logger.info("[GlobalReceiptWorker] ===== 進入 LLM 階段 =====")
                    
                    # 從 DB 取得 OCR 結果
                    job_details = tm.get_job_details(job_id)
                    ocr_result = job_details.get("ocr_result", {})
                    
                    if not ocr_result or not ocr_result.get("text"):
                        logger.warning(f"[GlobalReceiptWorker] Job {job_id} OCR 結果為空")
                        tm.fail_job(job_id, "OCR 結果為空，無法執行 LLM 處理")
                        engine.task_queue.task_done()
                        continue
                    
                    logger.info(f"[GlobalReceiptWorker] OCR 類型: {ocr_result.get('type')}, 文字長度: {len(ocr_result.get('text', ''))}")
                    
                    # 使用 process_llm_only 處理
                    try:
                        result = engine.receipt_processor.process_llm_only(ocr_result, image)
                        
                        if not result.get("success"):
                            error_msg = result.get("error", "LLM 處理失敗")
                            logger.warning(f"[GlobalReceiptWorker] ✗ LLM 失敗: {job_id} - {error_msg}")
                            tm.fail_job(job_id, error_msg)
                            engine.task_queue.task_done()
                            continue
                        
                        llm_result = result.get("llm_result", {})
                        llm_stats = result.get("llm_stats", [])
                        
                        # 輸出 LLM 結果到 log
                        import json as json_module
                        logger.info(f"[GlobalReceiptWorker] LLM 結果:\n{json_module.dumps(llm_result, ensure_ascii=False, indent=2)[:1000]}")
                        
                        # 完成 LLM 階段
                        tm.complete_llm(job_id, llm_result, mark_final=True, stats=llm_stats)
                        logger.info(f"[GlobalReceiptWorker] ✓ LLM 階段完成: {job_id}")
                        
                    except Exception as e:
                        logger.error(f"[GlobalReceiptWorker] LLM 處理異常: {e}", exc_info=True)
                        tm.fail_job(job_id, str(e))
                    
                    engine.task_queue.task_done()
                    continue
                
                # ===== 未指定階段時的處理 =====
                # 注意：正確架構下不應該走到這裡，因為任務應該明確指定是 OCR 或 LLM
                logger.warning(f"[GlobalReceiptWorker] Job {job_id} 沒有指定階段 (stage_limit={stage_limit})，跳過")
                engine.task_queue.task_done()
                
            except Exception as e:
                logger.error(f"[GlobalReceiptWorker] 處理失敗 {job_id}: {e}", exc_info=True)
                tm.fail_job(job_id, str(e))
            
            engine.task_queue.task_done()
            
        except Exception as e:
            logger.error(f"[GlobalReceiptWorker] 迴圈錯誤: {e}", exc_info=True)
            time.sleep(1)
    
    logger.info("[GlobalReceiptWorker] Worker 已關閉")
