# main.py
import os
import json
from backend.managers.project_manager import ProjectManager
from backend.processing.ocr_handler import OCRHandler
from backend.processing.llm_handler import LLMHandler
# from backend.processing.image_handler import split_receipts_from_image
from backend.processing.receipt_splitter import ReceiptSplitter
from backend.managers.task_manager import TaskManager
from backend.utils import utils
import threading
import traceback
import time


def cpu_worker(task_manager: TaskManager, ocr_handler: OCRHandler):
    """
    從輸入佇列獲取圖片路徑，執行 OCR 和佈局重構，
    然後將結果放入輸出佇列。
    """
    while True:
        try:
            task = task_manager.claim_for_ocr()
            if not task:
                break
            image_path = task["image_path"]
            print(f"[CPU Worker] Processing: {os.path.basename(image_path)}")

            # print(image_path)
            image = utils.cv_imread_chinese(image_path)
            # print(image)
            ocr_result = ocr_handler.do_paddleocr(image)
            # print(ocr_result)
            pre_formatted_text = ocr_handler.reconstruct_layout(ocr_result)

            task["pre_formatted_text"] = pre_formatted_text
            task_manager.complete_ocr(task["job_id"], {"data": pre_formatted_text})
        except Exception as e:
            print(f"[CPU Worker] ERROR processing {os.path.basename(image_path)}: {e}")
            task_manager.fail_job(task["job_id"], str(e))


# ----- [新] GPU Worker -----
def gpu_worker(task_manager: TaskManager, llm_handler: LLMHandler):
    """
    從輸入佇列獲取已 OCR 的任務，執行 LLM 結構化，
    並將最終結果存檔並更新總任務列表。
    """
    while True:
        base_name = "ERROR"
        try:
            task = task_manager.claim_for_llm()
            if task == "all_task_done":  # 收到結束信號
                break
            if task is None:
                time.sleep(1)
                print("not get job wait 1s")
                continue
            print(task)
            image_path = task["image_path"]
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            print(f"[GPU Worker] Structuring: {base_name}")
            pre_formatted_text = task["ocr_result"]
            final_output = llm_handler.structure_with_llm(pre_formatted_text)
            task_manager.complete_llm(task["job_id"], final_output)
        except Exception as e:
            print(f"[GPU Worker] FATAL ERROR on task {base_name}: {e}")
            task_manager.fail_job(task["job_id"], str(e))


def main():
    # --- [優化 2] 讀取設定檔 ---
    try:
        with open(
            "C:/Users/tange/OneDrive/Desktop/all project/py for NKNU GA/main_src/config.json",
            "r",
            encoding="utf-8",
        ) as f:
            config = json.load(f)
    except FileNotFoundError:
        print("[FATAL] 設定檔 'config.json' 不存在。")
        return

    # --- 互動與初始化 ---
    action = input("請選擇操作： (1) 執行新專案 (2) 從 Excel 重新生成: ")

    if action == "2":
        project_name = input("請輸入要重新生成的專案名稱: ")
        excel_path = input("請提供 Excel 檔案的完整路徑: ")
        if not os.path.exists(excel_path):
            print("[FATAL] Excel 檔案不存在。")
            return
            
        try:
            pm = ProjectManager(config=config["project_manager_settings"])
            # The config for LLMHandler is at the top level of the config file.
            pm.regenerate_from_archive(project_name, excel_path, config)
            print("[INFO] 重新生成完成。")
        except Exception as e:
            print(f"\n[FATAL] 重新生成過程中發生嚴重錯誤: {e}")
            print("異常完整資訊:", traceback.print_exc())
        return

    elif action == "1":
        project_name = input("請輸入本次辨識的專案名稱: ")
        if not project_name:
            return

        try:
            pm = ProjectManager(config=config["project_manager_settings"])

            # --- [優化 3] 執行前置作業 ---
            fileList = os.listdir("C:/Users/tange/OneDrive/Desktop/all project/py for NKNU GA/input")
            fileList = [os.path.join("C:/Users/tange/OneDrive/Desktop/all project/py for NKNU GA/input", i) for i in fileList]
            # print(fileList)
            project_status = pm.setup_project(project_name, fileList)
            print(project_status)
            # 初始化處理引擎
            tm = TaskManager(project_status["project_root"])
            ocr_handler = OCRHandler(config=config)
            llm_handler = LLMHandler(config=config)
            receipt_spliter = ReceiptSplitter(config={})

            # --- 建立任務清單 ---
            if project_status["project_status"] == "NEW":
                for image_path in os.listdir(os.path.join(project_status["project_root"], "原始輸入")):
                    try:
                        image = os.path.join(project_status["project_root"], "原始輸入", image_path)
                        image = utils.cv_imread_chinese(image)
                        # 呼叫分割函式，將裁切的小圖存到 temp_split_dir
                        cropped_image = receipt_spliter.split(image, True)
                        cropped_image_paths = [os.path.join(project_status["project_root"], "分割發票", f"{image_path}_spilt_{i}.jpg") for i in range(len(cropped_image))]
                        for i, img in enumerate(cropped_image):
                            utils.cv_imwrite_chinese(cropped_image_paths[i], img)
                        # 為每一張成功裁切的小圖建立一個任務
                        for crop_path in cropped_image_paths:
                            tm.enqueue(crop_path)
                    except Exception as e:
                        print(
                            f"[ERROR] 分割圖片 '{os.path.basename(image_path)}' 時出錯: {e}"
                        )
                        print("異常完整資訊:", traceback.print_exc())

                tasks = tm.list_jobs("pending")
                if len(tasks) == 0:
                    print("[ERROR] 未能成功分割出任何單據，處理中止。")
                    return

            # --- 處理任務 (為了簡潔，仍使用循序迴圈) ---

            tasks = tm.list_jobs("pending")
            if len(tasks) == 0:
                print("[INFO] 沒有待處理的任務。")

            print(f"[INFO] 啟動流水線，處理 {len(tasks)} 個任務...")

            cpu_thread = threading.Thread(
                target=cpu_worker, args=(tm, ocr_handler)
            )
            gpu_thread = threading.Thread(
                target=gpu_worker, args=(tm, llm_handler)
            )

            cpu_thread.start()
            gpu_thread.start()

            # 等待 CPU Worker 完成所有 OCR 任務
            cpu_thread.join()

            # 等待 GPU Worker 處理完所有剩餘的 LLM 任務
            gpu_thread.join()

            print("[INFO] 所有並行任務已完成。")

            # --- [優化 1] 彙總與歸檔 ---
            pm.archive_to_excel(project_name)

        except Exception as e:
            print(f"\n[FATAL] 專案處理過程中發生嚴重錯誤: {e}")
            print("異常完整資訊:", traceback.print_exc())
    else:
        print("無效的選擇。")


if __name__ == "__main__":
    # 確保處理引擎的初始化也接收 config
    # 例如 OCRHandler(config=config['ocr_settings'])
    main()
