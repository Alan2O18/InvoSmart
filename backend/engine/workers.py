# backend/engine/workers.py
"""
Global Worker 模組

提供兩個常駐的 Worker 函數：
- global_ocr_worker_loop: 處理全局 OCR 佇列
- global_llm_worker_loop: 處理全局 LLM 佇列

這些 Worker 在 Engine 啟動時創建，與 Server 同生共死。
採用「無鎖」設計：因為每種任務只有一個 Worker 線程，不需要任何同步機制。
"""
import time
import os
import logging
from backend.utils import utils

logger = logging.getLogger(__name__)


def global_ocr_worker_loop(engine):
    """
    全局 OCR Worker 主迴圈。
    
    從 engine.ocr_queue 獲取任務並處理。
    這是唯一處理 OCR 的線程，因此不需要任何鎖。
    
    Args:
        engine: Engine 實例，提供 ocr_queue、ocr_handler 和 get_task_manager 方法
    """
    logger.info("[GlobalOCRWorker] Worker 已啟動，等待任務...")
    
    while not engine._shutdown_event.is_set():
        try:
            # 阻塞式獲取任務，設置超時以便定期檢查 shutdown
            try:
                project_id, job_id = engine.ocr_queue.get(timeout=1.0)
            except:
                # Queue.Empty 或其他異常，繼續等待
                continue
            
            logger.info(f"[GlobalOCRWorker] 開始處理: {project_id}/{job_id}")
            
            # 獲取該專案的 TaskManager
            try:
                tm = engine.get_task_manager(project_id)
            except Exception as e:
                logger.error(f"[GlobalOCRWorker] 無法獲取 TaskManager for {project_id}: {e}")
                engine.ocr_queue.task_done()
                continue
            
            # 確認任務狀態（可能在排隊時被刪除或取消）
            job = tm.get_job(job_id)
            if not job:
                logger.warning(f"[GlobalOCRWorker] Job {job_id} 不存在，跳過")
                engine.ocr_queue.task_done()
                continue
            
            if job["status"] not in ("pending", "ready"):
                logger.info(f"[GlobalOCRWorker] Job {job_id} 狀態為 {job['status']}，跳過")
                engine.ocr_queue.task_done()
                continue
            
            # 標記為 running
            tm._repository.update_job(job_id, status="running", ocr_start_at=int(time.time()))
            tm._repository.emit_event(job_id, "ocr_started", {})
            
            try:
                # 執行 OCR 處理
                image_path = job["image_path"]
                image = utils.cv_imread_chinese(image_path)
                
                if hasattr(engine.ocr_handler, 'process_receipt'):
                    logger.debug("[GlobalOCRWorker] 使用 PP-Structure 引擎處理")
                    pre_formatted_text = engine.ocr_handler.process_receipt(image)
                else:
                    logger.debug("[GlobalOCRWorker] 使用基本 OCR 引擎處理")
                    ocr_result = engine.ocr_handler.do_paddleocr(image)
                    pre_formatted_text = engine.ocr_handler.reconstruct_layout(ocr_result)
                
                # 完成 OCR，更新狀態
                # advance_to_stage_llm=False: 不自動推進到 LLM
                # 這樣用戶可以選擇手動觸發 LLM
                tm.complete_ocr(job_id, {"data": pre_formatted_text}, advance_to_stage_llm=False)
                logger.info(f"[GlobalOCRWorker] ✓ 完成: {job_id}")
                
            except Exception as e:
                logger.error(f"[GlobalOCRWorker] 處理失敗 {job_id}: {e}", exc_info=True)
                tm.fail_job(job_id, str(e))
            
            engine.ocr_queue.task_done()
            
        except Exception as e:
            logger.error(f"[GlobalOCRWorker] 迴圈錯誤: {e}", exc_info=True)
            time.sleep(1)
    
    logger.info("[GlobalOCRWorker] Worker 已關閉")


def global_llm_worker_loop(engine):
    """
    全局 LLM Worker 主迴圈。
    
    從 engine.llm_queue 獲取任務並處理。
    
    Args:
        engine: Engine 實例，提供 llm_queue、llm_handler 和 get_task_manager 方法
    """
    logger.info("[GlobalLLMWorker] Worker 已啟動，等待任務...")
    
    while not engine._shutdown_event.is_set():
        try:
            try:
                project_id, job_id = engine.llm_queue.get(timeout=1.0)
            except:
                continue
            
            logger.info(f"[GlobalLLMWorker] 開始處理: {project_id}/{job_id}")
            
            try:
                tm = engine.get_task_manager(project_id)
            except Exception as e:
                logger.error(f"[GlobalLLMWorker] 無法獲取 TaskManager for {project_id}: {e}")
                engine.llm_queue.task_done()
                continue
            
            job = tm.get_job(job_id)
            if not job:
                logger.warning(f"[GlobalLLMWorker] Job {job_id} 不存在，跳過")
                engine.llm_queue.task_done()
                continue
            
            if job["status"] not in ("pending", "ready"):
                logger.info(f"[GlobalLLMWorker] Job {job_id} 狀態為 {job['status']}，跳過")
                engine.llm_queue.task_done()
                continue
            
            # 標記為 running
            tm._repository.update_job(job_id, status="running", llm_start_at=int(time.time()))
            tm._repository.emit_event(job_id, "llm_started", {})
            
            try:
                # 獲取 OCR 結果
                job_details = tm.get_job_details(job_id)
                ocr_result = job_details.get("ocr_result", {})
                
                if ocr_result:
                    pre_formatted_text = ocr_result.get("data", "")
                else:
                    pre_formatted_text = ""
                
                if not pre_formatted_text:
                    raise ValueError("OCR 結果為空，無法執行 LLM 處理")
                
                # 執行 LLM 處理
                final_output = engine.llm_handler.structure_with_llm(pre_formatted_text)
                
                # 完成 LLM
                tm.complete_llm(job_id, final_output, mark_final=True)
                logger.info(f"[GlobalLLMWorker] ✓ 完成: {job_id}")
                
            except Exception as e:
                logger.error(f"[GlobalLLMWorker] 處理失敗 {job_id}: {e}", exc_info=True)
                tm.fail_job(job_id, str(e))
            
            engine.llm_queue.task_done()
            
        except Exception as e:
            logger.error(f"[GlobalLLMWorker] 迴圈錯誤: {e}", exc_info=True)
            time.sleep(1)
    
    logger.info("[GlobalLLMWorker] Worker 已關閉")
