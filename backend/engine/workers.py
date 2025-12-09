import time
import os
import logging
from backend.managers import TaskManager
from backend.utils import utils

logger = logging.getLogger(__name__)

def process_ocr_task(tm: TaskManager, task: dict, ocr_handler, auto_advance: bool = True):
    try:
        image_path = task["image_path"]
        logger.info(f"[OCR] Processing: {os.path.basename(image_path)}")
        
        image = utils.cv_imread_chinese(image_path)
        ocr_result = ocr_handler.do_paddleocr(image)
        pre_formatted_text = ocr_handler.reconstruct_layout(ocr_result)

        task["pre_formatted_text"] = pre_formatted_text
        tm.complete_ocr(task["job_id"], {"data": pre_formatted_text}, advance_to_stage_llm=auto_advance)
        logger.info(f"[OCR] ✓ Completed: {os.path.basename(image_path)}")
        return True
    except Exception as e:
        logger.error(f"[OCR] Error: {e}", exc_info=True)
        tm.fail_job(task["job_id"], str(e))
        return False

def process_llm_task(tm: TaskManager, task: dict, llm_handler, auto_advance: bool = True):
    try:
        image_path = task["image_path"]
        logger.info(f"[LLM] Structuring: {os.path.basename(image_path)}")
        
        pre_formatted_text = task["ocr_result"]
        final_output = llm_handler.structure_with_llm(pre_formatted_text)
        # For LLM, auto_advance usually means "mark as final done" vs "pending" if there was a next stage.
        # But complete_llm has mark_final param. Let's map auto_advance to mark_final for consistency,
        # or just assume LLM is the last stage for now.
        tm.complete_llm(task["job_id"], final_output, mark_final=True) 
        logger.info(f"[LLM] ✓ Completed: {os.path.basename(image_path)}")
        return True
    except Exception as e:
        logger.error(f"[LLM] Error: {e}", exc_info=True)
        tm.fail_job(task["job_id"], str(e))
        return False

def start_cpu_worker(tm: TaskManager, project_id: str, ocr_handler):
    logger.info(f"[CPU Worker] Started for {project_id}")
    while True:
        try:
            task = tm.claim_for_ocr()
            if not task:
                # No more tasks pending OCR
                break
            
            process_ocr_task(tm, task, ocr_handler, auto_advance=True)
        
        except Exception as e:
            logger.error(f"[CPU Worker] Loop Error: {e}")
            time.sleep(1)
    logger.info(f"[CPU Worker] Finished for {project_id}")

def start_gpu_worker(tm: TaskManager, project_name: str, llm_handler):
    logger.info(f"[GPU Worker] Started for {project_name}")
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
            logger.error(f"[GPU Worker] Loop Error: {e}")
            time.sleep(1)
    
    logger.info(f"[GPU Worker] Finished for {project_name}")
