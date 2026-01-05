# backend/engine/workers.py
"""
Global Worker 模組

提供統一的收據處理 Worker：
- global_receipt_worker_loop: 處理完整收據管線（合併 OCR + LLM）

這個 Worker 在 Engine 啟動時創建，與 Server 同生共死。
使用 ReceiptProcessor 執行完整處理流程。

保留舊的 Worker 函數以支援向後兼容（可選使用）。
"""
import time
import os
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
                    # ===== OCR-only 模式 =====
                    logger.debug("[GlobalReceiptWorker] 執行 OCR-only 模式")
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
                    logger.info(f"[GlobalReceiptWorker] ✓ OCR Only 完成: {job_id}")
                    engine.task_queue.task_done()
                    continue

                # 使用統一管線處理
                logger.debug("[GlobalReceiptWorker] 使用 ReceiptProcessor 處理...")
                result = engine.receipt_processor.process(image)
                
                # 檢查是否處理失敗
                if not result.get("success", True):
                    # 即使失敗，也要記錄已完成的 OCR 結果
                    ocr_result = result.get("ocr_result")
                    ocr_stats = result.get("ocr_stats")
                    if ocr_result:
                        tm.complete_ocr(job_id, ocr_result, advance_to_stage_llm=False, stats=ocr_stats)
                    
                    error_msg = result.get("error", "VLM 處理失敗（無輸出）")
                    logger.warning(f"[GlobalReceiptWorker] ✗ VLM 失敗: {job_id} - {error_msg}")
                    tm.fail_job(job_id, error_msg)
                    engine.task_queue.task_done()
                    continue
                
                # 檢查是否有空資料（VLM/LLM 無輸出）
                # 注意：新版 receipt_processor 返回 llm_result 而非 data
                llm_result = result.get("llm_result", {})
                if not llm_result or llm_result == {}:
                    # 記錄 OCR 結果
                    ocr_result = result.get("ocr_result")
                    ocr_stats = result.get("ocr_stats")
                    if ocr_result:
                        tm.complete_ocr(job_id, ocr_result, advance_to_stage_llm=False, stats=ocr_stats)
                    
                    logger.warning(f"[GlobalReceiptWorker] ✗ LLM 輸出為空: {job_id}")
                    tm.fail_job(job_id, "LLM 識別結果為空")
                    engine.task_queue.task_done()
                    continue
                
                # 提取結果與統計
                ocr_result = result.get("ocr_result", {})
                ocr_stats = result.get("ocr_stats")
                llm_result = result.get("llm_result", {})
                llm_stats = result.get("llm_stats")
                
                # 完成 OCR 階段（包含 stats）
                tm.complete_ocr(job_id, ocr_result, advance_to_stage_llm=True, stats=ocr_stats)
                
                # 完成 LLM 階段（包含 stats）
                tm.complete_llm(job_id, llm_result, mark_final=True, stats=llm_stats)
                
                logger.info(f"[GlobalReceiptWorker] ✓ 完成: {job_id} (類型: {result.get('invoice_type', 'unknown')})")                
            except Exception as e:
                logger.error(f"[GlobalReceiptWorker] 處理失敗 {job_id}: {e}", exc_info=True)
                tm.fail_job(job_id, str(e))
            
            engine.task_queue.task_done()
            
        except Exception as e:
            logger.error(f"[GlobalReceiptWorker] 迴圈錯誤: {e}", exc_info=True)
            time.sleep(1)
    
    logger.info("[GlobalReceiptWorker] Worker 已關閉")


# ============================================
# 舊版 Worker（保留以支援向後兼容）
# ============================================

def global_ocr_worker_loop(engine):
    """
    [舊版] 全局 OCR Worker 主迴圈。
    
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
            tm._repository.update_job(job_id, status="running")
            tm._repository.emit_event(job_id, "ocr_started", {})
            
            try:
                # 執行 OCR 處理
                image_path = job["image_path"]
                image = utils.cv_imread_chinese(image_path)
                
                # 使用新的 ReceiptProcessor（僅 OCR 階段）
                if hasattr(engine, 'receipt_processor'):
                    logger.debug("[GlobalOCRWorker] 使用 ReceiptProcessor OCR 模式")
                    result = engine.receipt_processor.process_ocr_only(image)
                    pre_formatted_text = result.get("ocr_result", {}).get("data", "")
                elif hasattr(engine.ocr_handler, 'process_receipt'):
                    logger.debug("[GlobalOCRWorker] 使用 PP-Structure 引擎處理")
                    pre_formatted_text = engine.ocr_handler.process_receipt(image)
                else:
                    logger.debug("[GlobalOCRWorker] 使用基本 OCR 引擎處理")
                    ocr_result = engine.ocr_handler.do_paddleocr(image)
                    pre_formatted_text = engine.ocr_handler.reconstruct_layout(ocr_result)
                
                # 完成 OCR，更新狀態
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
    [舊版] 全局 LLM Worker 主迴圈。
    
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
            tm._repository.update_job(job_id, status="running")
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
                
                # 使用新的 ReceiptProcessor（僅 LLM 階段）
                if hasattr(engine, 'receipt_processor'):
                    logger.debug("[GlobalLLMWorker] 使用 ReceiptProcessor LLM 模式")
                    final_output = engine.receipt_processor.process_llm_only(pre_formatted_text)
                else:
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
