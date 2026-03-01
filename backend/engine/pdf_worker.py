# backend/engine/pdf_worker.py
"""
PDF 獨立工作線程
專門處理 CPU-bound 的 PDF 操作 (壓縮、蓋章、重排)，避免阻塞主線程或 VLM 請求。
"""
import logging
import time
import asyncio
import json
from backend.processing.pdf_engine import execute_commands

logger = logging.getLogger(__name__)

def pdf_worker_loop(engine):
    """
    獨立的 PDF 處理主迴圈。
    
    Args:
        engine: 系統核心 Engine 實例
    """
    logger.info("[PDF Worker] 獨立 PDF Worker 已啟動，等待任務...")
    
    # PDF worker 可能需要 async context 來存取 JobRepository，所以我們開一個獨立的 event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while not getattr(engine, "_shutdown_event", None) or not engine._shutdown_event.is_set():
        try:
            # 嘗試從 PDF 專用佇列獲取任務
            try:
                # 確保 engine 有 pdf_task_queue
                if not hasattr(engine, "pdf_task_queue"):
                    time.sleep(1)
                    continue
                task = engine.pdf_task_queue.get(timeout=1.0)
                project_id, job_id, commands_dict = task[0], task[1], task[2]
            except Exception:
                # 拿不到任務或 timeout，繼續迴圈
                continue
            
            logger.info(f"[PDF Worker] 開始處理任務: {project_id}/{job_id}")
            
            # --- 以下是在 event loop 內執行的 asyncio 邏輯 ---
            async def process_pdf_task(project_id, job_id, commands):
                try:
                    job_repo = engine.get_job_repo(project_id)
                    
                    # 1. Claim job (設為 processing)
                    await job_repo.update_job(job_id, pdf_status="compressing")
                    
                    # 2. 取得 Job 取出路徑參數
                    job = await job_repo.get_job(job_id)
                    if not job:
                        logger.warning(f"[PDF Worker] 找不到 Job: {job_id}")
                        return
                    
                    source_pdf_path = job.get("source_pdf_path")
                    compressed_pdf_path = job.get("compressed_pdf_path")
                    
                    if not source_pdf_path or not compressed_pdf_path:
                        logger.error(f"[PDF Worker] 缺乏 PDF 路徑參數: {job_id}")
                        await job_repo.update_job(job_id, status="failed", pdf_status="failed")
                        return
                        
                    # 3. 呼叫純函式 PDF 引擎執行 (這可能很慢，但我們在獨立 Thread 不怕阻塞)
                    logger.info(f"[PDF Worker] 執行 PDF 引擎重建指令: {job_id}")
                    success = execute_commands(source_pdf_path, compressed_pdf_path, commands)
                    
                    # 4. 根據結果更新狀態
                    if success:
                        # 將執行結果存回 db，標記完成
                        await job_repo.update_job(
                            job_id,
                            pdf_status="completed",
                            pdf_commands_json=json.dumps(commands, ensure_ascii=False)
                        )
                        logger.info(f"[PDF Worker] ✓ PDF 處理與壓縮完成: {job_id}")
                    else:
                        await job_repo.update_job(job_id, status="failed", pdf_status="failed")
                        logger.error(f"[PDF Worker] ✗ PDF 引擎回傳錯誤: {job_id}")
                        
                except Exception as e:
                    logger.error(f"[PDF Worker] 任務處理異常: {job_id} - {str(e)}", exc_info=True)
                    try:
                        job_repo = engine.get_job_repo(project_id)
                        await job_repo.update_job(job_id, status="failed", pdf_status="failed")
                    except Exception as inner_e:
                        logger.error(f"[PDF Worker] 無法寫入失敗狀態: {inner_e}")
            
            # 跑上面的 async function
            loop.run_until_complete(process_pdf_task(project_id, job_id, commands_dict))
            
        except Exception as e:
            logger.error(f"[PDF Worker] Worker 迴圈最外層異常: {e}", exc_info=True)
            time.sleep(1)
            
    logger.info("[PDF Worker] 獨立 PDF Worker 已停止")
