# backend/engine/core.py
"""
Engine - 系統核心協調器 (VLM-First 簡化版)

採用依賴注入架構：
- ProjectRepository: 專案資料管理
- JobRepository: Job 資料管理 (per-project)
- ReceiptProcessor: VLM 處理核心
- ReceiptSplitter: 圖片分割

不再使用 TaskManager / ProjectManager 中間層。
"""
import os
import json
import queue
import time
import uuid
import threading
import logging
from typing import Optional, Dict

from backend.repositories.project_repository import ProjectRepository
from backend.repositories.job_repository import JobRepository
from backend.processing.receipt_splitter import ReceiptSplitter

from .workers import global_receipt_worker_loop
from .file_ops import FileOps
from .export import ExportHandler

logger = logging.getLogger(__name__)


class Engine:
    """
    系統核心引擎 - VLM-First 簡化版
    
    直接使用 Repository 層，不再經過 TaskManager / ProjectManager。
    """

    def __init__(
        self,
        config: dict = None,
        receipt_processor=None,
        project_repo: ProjectRepository = None,
        receipt_splitter=None,
        start_workers: bool = True,
    ):
        # 加載配置
        self.config = config if config is not None else self._load_config()
        
        # 依賴注入或默認創建
        self.project_repo = project_repo or self._create_project_repo()
        self.receipt_processor = receipt_processor or self._create_receipt_processor()
        self.receipt_splitter = receipt_splitter or ReceiptSplitter(config={})
        
        # 內部組件
        self.file_ops = FileOps(self.project_repo, self.receipt_splitter, self)
        self.export_handler = ExportHandler(self.project_repo)

        # JobRepository 緩存 (per-project)
        self._job_repos: Dict[str, JobRepository] = {}
        self._repo_lock = threading.Lock()
        
        # 全局任務佇列
        self.task_queue: queue.Queue = queue.Queue()
        
        # Worker 控制
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        
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
    
    def _create_project_repo(self) -> ProjectRepository:
        """創建 ProjectRepository"""
        return ProjectRepository(config=self.config.get("project_manager_settings", {}))
    
    def _create_receipt_processor(self):
        """創建 ReceiptProcessor"""
        from backend.processing.receipt_processor import ReceiptProcessor
        logger.info("使用統一收據處理器 (ReceiptProcessor)")
        return ReceiptProcessor(config=self.config)

    def _start_global_workers(self):
        """啟動全局 Worker 線程"""
        self._worker_thread = threading.Thread(
            target=global_receipt_worker_loop,
            args=(self,),
            name="GlobalReceiptWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("[Engine] VLM-First Worker 已啟動")

    def _recover_pending_tasks(self):
        """Server 啟動時恢復未完成的任務"""
        logger.info("[Engine] 正在掃描未完成任務...")
        
        try:
            projects = self.project_repo.list_projects()
            total_recovered = 0
            
            for project in projects:
                project_id = project.get("id", project.get("project_id", ""))
                if not project_id:
                    continue
                    
                try:
                    job_repo = self.get_job_repo(project_id)
                    jobs = job_repo.list_jobs()
                    
                    for job in jobs:
                        if job["status"] in ("pending", "running"):
                            self.task_queue.put((project_id, job["job_id"]))
                            total_recovered += 1
                except Exception as e:
                    logger.warning(f"[Engine] 恢復專案 {project_id} 任務失敗: {e}")
            
            logger.info(f"[Engine] 已恢復 {total_recovered} 個未完成任務")
        except Exception as e:
            logger.error(f"[Engine] 任務恢復失敗: {e}")

    # ========================================
    # Repository Access
    # ========================================

    def get_job_repo(self, project_id: str) -> JobRepository:
        """取得特定專案的 JobRepository (singleton per project)。"""
        with self._repo_lock:
            if project_id not in self._job_repos:
                root = self.project_repo._project_root(project_id)
                self._job_repos[project_id] = JobRepository(str(root))
            return self._job_repos[project_id]

    # Backward compat alias (for workers.py etc.)
    def get_task_manager(self, project_id: str):
        """Alias for get_job_repo — backward compatibility."""
        return self.get_job_repo(project_id)

    # ========================================
    # Job Operations (直接操作 JobRepository)
    # ========================================

    def enqueue_job(self, project_id: str, image_path: str) -> str:
        """建立新 Job 並加入佇列。"""
        job_repo = self.get_job_repo(project_id)
        job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        job_repo.insert_job(job_id, image_path, "ready")
        job_repo.emit_event(job_id, "enqueued", {"image_path": image_path})
        return job_id

    def claim_job(self, project_id: str, job_id: str) -> bool:
        """將 Job 標記為 running。"""
        job_repo = self.get_job_repo(project_id)
        result = job_repo.update_job(job_id, status="running")
        if result:
            job_repo.emit_event(job_id, "claimed", {})
        return result

    def complete_job(self, project_id: str, job_id: str, vlm_result: dict,
                     validation: dict = None, stats: dict = None,
                     qr_verified: bool = False) -> bool:
        """完成 VLM 處理。"""
        job_repo = self.get_job_repo(project_id)
        return job_repo.complete_vlm(job_id, vlm_result, validation, stats, qr_verified)

    def fail_job(self, project_id: str, job_id: str, reason: str = ""):
        """標記 Job 失敗。"""
        job_repo = self.get_job_repo(project_id)
        job_repo.update_job(job_id, status="failed")
        job_repo.emit_event(job_id, "failed", {"reason": reason})

    def delete_job(self, project_id: str, job_id: str) -> bool:
        """刪除 Job。"""
        job_repo = self.get_job_repo(project_id)
        return job_repo.delete_job(job_id)

    # ========================================
    # Processing Queue
    # ========================================

    def run_processing(self, project_id: str):
        """VLM-First 處理入口 - 將所有待處理任務加入佇列。"""
        logger.info(f"[Processing] 開始處理專案: {project_id}")
        try:
            job_repo = self.get_job_repo(project_id)
            jobs = job_repo.list_jobs()
            queued = 0
            
            for job in jobs:
                if job["status"] in ("ready", "failed"):
                    job_repo.update_job(job["job_id"], status="pending")
                    self.task_queue.put((project_id, job["job_id"]))
                    queued += 1
            
            self.project_repo.update_project_status(project_id, "PROCESSING")
            logger.info(f"[Processing] 已將 {queued} 個任務加入佇列")
            
            return {"status": "processing_queued", "queued_count": queued, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"[Processing] 啟動失敗 {project_id}: {e}", exc_info=True)
            raise e

    def run_single_processing(self, project_id: str, job_id: str):
        """將單一 Job 加入處理佇列。"""
        try:
            job_repo = self.get_job_repo(project_id)
            job = job_repo.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            job_repo.update_job(job_id, status="pending")
            self.task_queue.put((project_id, job_id))
            logger.info(f"[Single Processing] Job {job_id} 已加入佇列")
            
            return {"status": "queued", "job_id": job_id, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"Error queuing single processing for {job_id}: {e}")
            raise e

    # ========================================
    # Delegated Methods
    # ========================================

    def create_project(self, project_id: str, files: list, name: str = None, metadata: dict = None):
        return self.project_repo.setup_project(project_id, input_image=files, name=name, metadata=metadata)

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

    def delete_raw_file(self, project_id: str, filename: str):
        try:
            root = self.project_repo._project_root(project_id)
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
        """獲取當前佇列狀態"""
        return {
            "task_queue_size": self.task_queue.qsize(),
            "worker_alive": self._worker_thread.is_alive() if self._worker_thread else False,
            "mode": "vlm-first"
        }
