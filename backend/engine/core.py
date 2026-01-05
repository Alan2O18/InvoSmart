# backend/engine/core.py
"""
Engine - 系統核心協調器

採用依賴注入架構：
- 所有依賴可通過構造函數注入
- 支持 start_workers 參數控制 Worker 啟動
- 測試時傳入 mock 依賴，不啟動 Workers

使用統一的 ReceiptProcessor 處理管線，
合併 OCR 和 LLM 為單一 Worker。
"""
import os
import json
import queue
import threading
import logging
from typing import Optional, Dict

from backend.managers import ProjectManager, TaskManager
from backend.processing.receipt_splitter import ReceiptSplitter

from .workers import global_receipt_worker_loop, global_ocr_worker_loop, global_llm_worker_loop
from .file_ops import FileOps
from .export import ExportHandler

logger = logging.getLogger(__name__)


class Engine:
    """
    系統核心引擎 - 支持依賴注入
    
    所有依賴都可通過構造函數注入，方便測試。
    生產環境使用 get_engine() 工廠函數獲取配置好的實例。
    
    新版使用統一的 ReceiptProcessor 和單一 Worker。
    """

    def __init__(
        self,
        config: dict = None,
        ocr_handler = None,  # 保留向後兼容
        llm_handler = None,  # 保留向後兼容
        receipt_processor = None,
        project_manager: ProjectManager = None,
        receipt_splitter = None,
        start_workers: bool = True,
        use_unified_worker: bool = True  # 新參數：是否使用統一 Worker
    ):
        """
        初始化 Engine。
        
        Args:
            config: 配置字典，None 則從 config.json 加載
            ocr_handler: [舊版] OCR 處理器，保留向後兼容
            llm_handler: [舊版] LLM 處理器，保留向後兼容
            receipt_processor: 收據處理器，None 則創建默認
            project_manager: 專案管理器，None 則創建默認
            receipt_splitter: 發票分割器，None 則創建默認
            start_workers: 是否啟動 Global Workers（測試時設 False）
            use_unified_worker: 是否使用統一 Worker（合併 OCR+LLM）
        """
        # 加載配置
        self.config = config if config is not None else self._load_config()
        self.use_unified_worker = use_unified_worker
        
        # 依賴注入或默認創建
        self.project_manager = project_manager or self._create_project_manager()
        self.receipt_processor = receipt_processor or self._create_receipt_processor()
        self.receipt_splitter = receipt_splitter or ReceiptSplitter(config={})
        
        # 向後兼容：保存 ocr_handler 和 llm_handler
        # 如果有傳入，使用舊版模式；否則使用統一處理器
        self.ocr_handler = ocr_handler
        self.llm_handler = llm_handler
        if ocr_handler is not None or llm_handler is not None:
            # 測試模式或舊版模式
            logger.debug("使用舊版 OCR/LLM handler 模式")
            self.use_unified_worker = False
        
        # 內部組件
        self.file_ops = FileOps(self.project_manager, self.receipt_splitter, self)
        self.export_handler = ExportHandler(self.project_manager)

        # TaskManager 緩存
        self.task_managers: Dict[str, TaskManager] = {}
        self.tm_lock = threading.Lock()
        
        # 全局任務佇列 - 總是初始化所有佇列以支援分離模式
        self.task_queue: queue.Queue = queue.Queue()  # 統一模式用
        self.ocr_queue: queue.Queue = queue.Queue()   # 分離模式 OCR 用
        self.llm_queue: queue.Queue = queue.Queue()   # 分離模式 LLM 用

        
        # Worker 控制
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._ocr_worker_thread: Optional[threading.Thread] = None
        self._llm_worker_thread: Optional[threading.Thread] = None
        
        # 條件啟動 Workers
        if start_workers:
            self._start_global_workers()
            self._recover_pending_tasks()
            logger.info("[Engine] 初始化完成 (Workers 已啟動)")
        else:
            logger.info("[Engine] 初始化完成 (測試模式，Workers 未啟動)")

    def _load_config(self) -> dict:
        """載入配置檔案"""
        local_config = "config.json"
        if os.path.exists(local_config):
            with open(local_config, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _create_project_manager(self) -> ProjectManager:
        """創建 ProjectManager"""
        return ProjectManager(config=self.config.get("project_manager_settings", {}))
    
    def _create_receipt_processor(self):
        """創建 ReceiptProcessor"""
        from backend.processing.receipt_processor import ReceiptProcessor
        logger.info("使用統一收據處理器 (ReceiptProcessor)")
        return ReceiptProcessor(config=self.config)

    def _start_global_workers(self):
        """啟動全局 Worker 線程"""
        if self.use_unified_worker:
            # 統一 Worker
            self._worker_thread = threading.Thread(
                target=global_receipt_worker_loop,
                args=(self,),
                name="GlobalReceiptWorker",
                daemon=True
            )
            self._worker_thread.start()
            logger.info("[Engine] 統一收據處理 Worker 已啟動")
        else:
            # 舊版分離 Worker
            self._ocr_worker_thread = threading.Thread(
                target=global_ocr_worker_loop,
                args=(self,),
                name="GlobalOCRWorker",
                daemon=True
            )
            self._ocr_worker_thread.start()
            logger.info("[Engine] 全局 OCR Worker 已啟動")
            
            self._llm_worker_thread = threading.Thread(
                target=global_llm_worker_loop,
                args=(self,),
                name="GlobalLLMWorker",
                daemon=True
            )
            self._llm_worker_thread.start()
            logger.info("[Engine] 全局 LLM Worker 已啟動")

    def _recover_pending_tasks(self):
        """Server 啟動時恢復未完成的任務"""
        logger.info("[Engine] 正在掃描未完成任務...")
        
        try:
            projects = self.project_manager.list_projects()
            total_recovered = 0
            
            for project in projects:
                project_id = project.get("id", project.get("project_id", ""))
                if not project_id:
                    continue
                    
                try:
                    tm = self.get_task_manager(project_id)
                    jobs = tm.list_jobs()
                    
                    for job in jobs:
                        if job["status"] in ("pending", "running"):
                            if self.use_unified_worker:
                                # 統一佇列：不區分 stage
                                self.task_queue.put((project_id, job["job_id"]))
                                total_recovered += 1
                            else:
                                # 舊版分離佇列
                                if job["stage"] == "ocr":
                                    self.ocr_queue.put((project_id, job["job_id"]))
                                    total_recovered += 1
                                elif job["stage"] == "llm":
                                    self.llm_queue.put((project_id, job["job_id"]))
                                    total_recovered += 1
                except Exception as e:
                    logger.warning(f"[Engine] 恢復專案 {project_id} 任務失敗: {e}")
            
            logger.info(f"[Engine] 已恢復 {total_recovered} 個未完成任務")
        except Exception as e:
            logger.error(f"[Engine] 任務恢復失敗: {e}")

    def get_task_manager(self, project_id: str) -> TaskManager:
        """Singleton access to TaskManager for a given project."""
        with self.tm_lock:
            if project_id not in self.task_managers:
                root = self.project_manager._project_root(project_id)
                self.task_managers[project_id] = TaskManager(str(root))
            return self.task_managers[project_id]

    # ========================================
    # Worker Management
    # ========================================

    def run_processing(self, project_id: str):
        """
        [新版] 批次將所有 ready 的任務加入統一佇列。
        
        使用統一 Worker 時的主要入口點。
        """
        if not self.use_unified_worker:
            # 向後兼容：使用舊版 run_ocr
            return self.run_ocr(project_id)
        
        logger.info(f"[Processing] 開始處理專案: {project_id}")
        try:
            tm = self.get_task_manager(project_id)
            
            # 標記 OCR 階段為 pending
            count = tm.mark_ocr_stage_as_pending()
            logger.info(f"[Processing] 標記 {count} 個工作為 pending")
            
            jobs = tm.list_jobs()
            queued = 0
            for job in jobs:
                if job["status"] == "pending":
                    self.task_queue.put((project_id, job["job_id"]))
                    queued += 1
            
            self.project_manager.update_project_status(project_id, "PROCESSING")
            logger.info(f"[Processing] 已將 {queued} 個任務加入統一佇列 (queue size: {self.task_queue.qsize()})")
            
            return {"status": "processing_queued", "queued_count": queued, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"[Processing] 啟動失敗 {project_id}: {e}", exc_info=True)
            raise e

    def run_ocr(self, project_id: str):
        """批次將所有 ready 的 OCR 任務加入佇列。"""
        # Removed unified worker delegation to allow simpler logic flow
        # if self.use_unified_worker:
        #     return self.run_processing(project_id)
        
        logger.info(f"[OCR] 開始處理專案: {project_id}")
        try:
            tm = self.get_task_manager(project_id)
            
            count = tm.mark_ocr_stage_as_pending()
            logger.info(f"[OCR] 標記 {count} 個工作為 pending")
            
            jobs = tm.list_jobs()
            queued = 0
            for job in jobs:
                if job["status"] == "pending" and job["stage"] == "ocr":
                    self.ocr_queue.put((project_id, job["job_id"]))
                    queued += 1
            
            self.project_manager.update_project_status(project_id, "PROCESSING")
            logger.info(f"[OCR] 已將 {queued} 個任務加入全局佇列 (queue size: {self.ocr_queue.qsize()})")
            
            return {"status": "ocr_queued", "queued_count": queued, "queue_size": self.ocr_queue.qsize()}
        except Exception as e:
            logger.error(f"[OCR] 啟動失敗 {project_id}: {e}", exc_info=True)
            raise e

    def run_ocr_only(self, project_id: str):
        """
        僅執行 OCR，不進入 LLM 階段。
        完成後設定 stage='llm', status='ready'
        """
        if not self.use_unified_worker:
            # For run_ocr_only, we don't need unified worker, but we can log that we are running in detached mode
            pass
            
        # logger.warning("[OCR Only] 舊版模式不支援 run_ocr_only，執行標準 OCR")
        # return self.run_ocr(project_id)

        logger.info(f"[OCR Only] 開始處理專案: {project_id}")
        try:
            tm = self.get_task_manager(project_id)
            
            # 標記 OCR 階段為 pending
            count = tm.mark_ocr_stage_as_pending()
            logger.info(f"[OCR Only] 標記 {count} 個工作為 pending")
            
            jobs = tm.list_jobs()
            queued = 0
            for job in jobs:
                if job["status"] == "pending" and job["stage"] == "ocr":
                    # 使用 tuple 傳遞 stage_limit
                    self.task_queue.put((project_id, job["job_id"], "ocr"))
                    queued += 1
            
            self.project_manager.update_project_status(project_id, "PROCESSING")
            logger.info(f"[OCR Only] 已將 {queued} 個任務加入佇列")
            
            return {"status": "ocr_only_queued", "queued_count": queued, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"[OCR Only] 啟動失敗 {project_id}: {e}", exc_info=True)
            raise e

    def run_llm(self, project_id: str):
        """批次將所有 ready 的 LLM 任務加入佇列。"""
        # Removed unified mode blocking to allow separate LLM execution
        # if self.use_unified_worker:
        #     logger.warning("[LLM] 統一模式下無需單獨調用 run_llm")
        #     return {"status": "unified_mode", "message": "LLM processing is included in unified pipeline"}
        
        logger.info(f"[LLM] 開始處理專案: {project_id}")
        try:
            tm = self.get_task_manager(project_id)
            
            count = tm.mark_llm_stage_as_pending()
            logger.info(f"[LLM] 標記 {count} 個工作為 pending")
            
            jobs = tm.list_jobs()
            queued = 0
            for job in jobs:
                if job["status"] == "pending" and job["stage"] == "llm":
                    self.llm_queue.put((project_id, job["job_id"]))
                    queued += 1
            
            logger.info(f"[LLM] 已將 {queued} 個任務加入全局佇列 (queue size: {self.llm_queue.qsize()})")
            return {"status": "llm_queued", "queued_count": queued, "queue_size": self.llm_queue.qsize()}
        except Exception as e:
            logger.error(f"[LLM] 啟動失敗 {project_id}: {e}", exc_info=True)
            raise e

    def run_single_processing(self, project_id: str, job_id: str):
        """[新版] 將單一 Job 加入統一處理佇列。"""
        if not self.use_unified_worker:
            return self.run_single_ocr(project_id, job_id)
        
        try:
            tm = self.get_task_manager(project_id)
            
            job = tm.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            tm.mark_pending_for_ocr(job_id)
            self.task_queue.put((project_id, job_id))
            logger.info(f"[Single Processing] Job {job_id} 已加入統一佇列 (queue size: {self.task_queue.qsize()})")
            
            return {"status": "queued", "job_id": job_id, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"Error queuing single processing for {job_id}: {e}")
            raise e

    def run_single_ocr(self, project_id: str, job_id: str):
        """將單一 Job 加入 OCR 處理佇列。"""
        # if self.use_unified_worker:
        #     return self.run_single_processing(project_id, job_id)
        
        try:
            tm = self.get_task_manager(project_id)
            
            job = tm.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            tm.mark_pending_for_ocr(job_id)
            self.ocr_queue.put((project_id, job_id))
            logger.info(f"[Single OCR] Job {job_id} 已加入 OCR 佇列 (queue size: {self.ocr_queue.qsize()})")
            
            return {"status": "queued", "job_id": job_id, "queue_size": self.ocr_queue.qsize()}
        except Exception as e:
            logger.error(f"Error queuing single OCR for {job_id}: {e}")
            raise e

    def run_single_ocr_only(self, project_id: str, job_id: str):
        """單一 Job 僅執行 OCR"""
        if not self.use_unified_worker:
            logger.warning("[Single OCR Only] 舊版模式不支援 run_single_ocr_only，執行標準 OCR")
            return self.run_single_ocr(project_id, job_id)

        try:
            tm = self.get_task_manager(project_id)
            
            job = tm.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            tm.mark_pending_for_ocr(job_id)
            # 使用 tuple 傳遞 stage_limit
            self.task_queue.put((project_id, job_id, "ocr"))
            logger.info(f"[Single OCR Only] Job {job_id} 已加入佇列 (queue size: {self.task_queue.qsize()})")
            
            return {"status": "queued", "job_id": job_id, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"Error queuing single OCR only for {job_id}: {e}")
            raise e

    def run_single_llm(self, project_id: str, job_id: str):
        """將單一 Job 加入 LLM 處理佇列。"""
        # Removed unified mode blocking
        # if self.use_unified_worker:
        #     logger.warning("[Single LLM] 統一模式下無需單獨調用 run_single_llm")
        #     return {"status": "unified_mode", "message": "Use run_single_processing instead"}
        
        try:
            tm = self.get_task_manager(project_id)
            
            job = tm.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            tm.mark_pending_for_llm(job_id)
            self.llm_queue.put((project_id, job_id))
            logger.info(f"[Single LLM] Job {job_id} 已加入 LLM 佇列 (queue size: {self.llm_queue.qsize()})")
            
            return {"status": "queued", "job_id": job_id, "queue_size": self.llm_queue.qsize()}
        except Exception as e:
            logger.error(f"Error queuing single LLM for {job_id}: {e}")
            raise e

    # ========================================
    # Delegated Methods
    # ========================================

    def create_project(self, project_id: str, files: list, name: str = None, metadata: dict = None):
        res = self.project_manager.setup_project(project_id, input_image=files, name=name, metadata=metadata)
        return res

    def run_splitting(self, project_id: str, target_files: Optional[list[str]] = None):
        logger.info(f"[分割] 開始處理專案: {project_id}, 目標檔案={target_files}")
        result = self.file_ops.run_splitting(project_id, target_files)
        logger.info(f"[分割] 完成: {project_id}")
        return result

    def run_split_single(self, project_id: str, filename: str):
        """Split a single raw file."""
        logger.info(f"[分割] 單檔處理: {project_id}/{filename}")
        result = self.file_ops.run_splitting(project_id, target_files=[filename])
        logger.info(f"[分割] 單檔完成: {filename}")
        return result

    def get_raw_files(self, project_id: str):
        return self.file_ops.get_raw_files(project_id)

    def add_project_files(self, project_id: str, files: list[str], type: str = "raw"):
        return self.file_ops.add_project_files(project_id, files, type)

    def rotate_image(self, project_id: str, filename: str, angle: int = 90):
        return self.file_ops.rotate_image(project_id, filename, angle)

    def delete_job(self, project_id: str, job_id: str):
        tm = self.get_task_manager(project_id)
        return tm.delete_job(job_id)

    def delete_raw_file(self, project_id: str, filename: str):
        try:
            root = self.project_manager._project_root(project_id)
            path = root / "原始輸入" / filename
            if path.exists():
                os.remove(path)
                return {"status": "deleted"}
            return {"status": "not_found"}
        except Exception as e:
            logger.error(f"Error deleting raw file: {e}")
            raise e

    def run_excel(self, project_id: str):
        return self.export_handler.run_excel(project_id)

    def archive_project(self, project_id: str):
        return self.export_handler.seal_project(project_id)

    def regenerate_project(self, project_id: str, excel_path: str):
        return self.export_handler.regenerate_from_archive(project_id, excel_path, self.config)

    def get_queue_status(self) -> dict:
        """獲取當前佇列狀態（供 Debug 使用）"""
        if self.use_unified_worker:
            return {
                "task_queue_size": self.task_queue.qsize(),
                "worker_alive": self._worker_thread.is_alive() if self._worker_thread else False,
                "mode": "unified"
            }
        else:
            return {
                "ocr_queue_size": self.ocr_queue.qsize(),
                "llm_queue_size": self.llm_queue.qsize(),
                "ocr_worker_alive": self._ocr_worker_thread.is_alive() if self._ocr_worker_thread else False,
                "llm_worker_alive": self._llm_worker_thread.is_alive() if self._llm_worker_thread else False,
                "mode": "legacy"
            }
