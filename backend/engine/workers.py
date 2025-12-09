import time
import os
import logging
from backend.managers import TaskManager
from backend.utils import utils

logger = logging.getLogger(__name__)

def process_ocr_task(tm: TaskManager, task: dict, ocr_handler, auto_advance: bool = True):
    try:
        image_path = task["image_path"]
        logger.debug(f"[OCR Task] 處理中: {os.path.basename(image_path)}")
        
        image = utils.cv_imread_chinese(image_path)
        ocr_result = ocr_handler.do_paddleocr(image)
        pre_formatted_text = ocr_handler.reconstruct_layout(ocr_result)

        task["pre_formatted_text"] = pre_formatted_text
        tm.complete_ocr(task["job_id"], {"data": pre_formatted_text}, advance_to_stage_llm=auto_advance)
        logger.debug(f"[OCR Task] ✓ 完成: {os.path.basename(image_path)}")
        return True
    except Exception as e:
        logger.error(f"[OCR Task] 錯誤: {e}", exc_info=True)
        tm.fail_job(task["job_id"], str(e))
        return False

def process_llm_task(tm: TaskManager, task: dict, llm_handler, auto_advance: bool = True):
    try:
        image_path = task["image_path"]
        logger.debug(f"[LLM Task] 結構化處理中: {os.path.basename(image_path)}")
        
        pre_formatted_text = task["ocr_result"]
        final_output = llm_handler.structure_with_llm(pre_formatted_text)
        # For LLM, auto_advance usually means "mark as final done" vs "pending" if there was a next stage.
        # But complete_llm has mark_final param. Let's map auto_advance to mark_final for consistency,
        # or just assume LLM is the last stage for now.
        tm.complete_llm(task["job_id"], final_output, mark_final=True) 
        logger.debug(f"[LLM Task] ✓ 完成: {os.path.basename(image_path)}")
        return True
    except Exception as e:
        logger.error(f"[LLM Task] 錯誤: {e}", exc_info=True)
        tm.fail_job(task["job_id"], str(e))
        return False

def start_cpu_worker(tm: TaskManager, project_id: str, ocr_handler):
    logger.debug(f"[CPU Worker] 開始運行: {project_id}")
    while True:
        try:
            task = tm.claim_for_ocr()
            if not task:
                # No more tasks pending OCR
                break
            
            process_ocr_task(tm, task, ocr_handler, auto_advance=True)
        
        except Exception as e:
            logger.error(f"[CPU Worker] 迴圈錯誤: {e}")
            time.sleep(1)
    logger.debug(f"[CPU Worker] 結束: {project_id}")

def start_gpu_worker(tm: TaskManager, project_name: str, llm_handler):
    logger.debug(f"[GPU Worker] 開始運行: {project_name}")
    while True:
        try:
            task = tm.claim_for_llm()
            if task == "all_task_done":
                break
            if task is None:
                time.sleep(1)
                continue
            
            process_llm_task(tm, task, llm_handler, auto_advance=True)
        
        except Exception as e:
            logger.error(f"[GPU Worker] 迴圈錯誤: {e}")
            time.sleep(1)
    
    logger.debug(f"[GPU Worker] 結束: {project_name}")
