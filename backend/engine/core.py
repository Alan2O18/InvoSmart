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
import asyncio
import queue
import time
import uuid
import threading
import logging
from pathlib import Path
from typing import Optional, Dict

from backend.repositories.project_repository import ProjectRepository
from backend.repositories.job_repository import JobRepository
from backend.processing.receipt_splitter import ReceiptSplitter

from .workers import global_receipt_worker_loop
from .file_ops import FileOps
from .file_service import FileService
from .export import ExportHandler
from .voucher_generator import VoucherGenerator

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
        session_factory=None,
    ):
        # 加載配置
        self.config = config if config is not None else self._load_config()
        self.session_factory = session_factory
        
        # 依賴注入或默認創建
        self.project_repo = project_repo or self._create_project_repo()
        self.receipt_processor = receipt_processor or self._create_receipt_processor()
        self.receipt_splitter = receipt_splitter or ReceiptSplitter(config={})
        
        # 內部組件
        self.file_service = FileService(self.project_repo)
        self.file_ops = FileOps(self.project_repo, self.receipt_splitter, self)
        self.export_handler = ExportHandler(self.project_repo, self)
        
        # 憑證產生組件
        template_path = str(Path(__file__).parent.parent / "assets" / "templates" / "憑證黏貼用紙.pdf")
        self.voucher_generator = VoucherGenerator(template_path)

        # JobRepository 緩存 (per-project)
        self._job_repos: Dict[str, JobRepository] = {}
        self._repo_lock = threading.Lock()

        processing_settings = self.config.get("processing_settings", {})
        max_image_concurrency = max(1, int(processing_settings.get("image_conversion_max_concurrency", 3)))
        self.image_processing_semaphore = asyncio.Semaphore(max_image_concurrency)
        
        # 全局任務佇列 (影像 VLM 專用)
        self.task_queue: queue.Queue = queue.Queue()
        
        # Worker 控制
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        
        # 條件啟動 Workers
        if start_workers:
            self._start_global_workers()
            logger.info("[Engine] 初始化完成 (Workers 已啟動)")
        else:
            logger.info("[Engine] 初始化完成 (測試模式，Workers 未啟動)")

    def update_config(self, config: dict):
        """
        更新系統配置 (Runtime)
        
        Args:
            config: 完整的配置字典
        """
        self.config = config
        # 更新組件配置
        if self.receipt_processor:
            self.receipt_processor.update_config(config)
        
        # ProjectRepository 可能也需要更新 (例如 workspace_root)，但這通常涉及重啟
        # 暫不支援動態更改 workspace_root
        
        logger.info("[Engine] 系統配置已更新")

    def _load_config(self) -> dict:
        """載入配置檔案"""
        from backend.utils.config import load_config
        return load_config()
    
    def _create_project_repo(self) -> ProjectRepository:
        """創建 ProjectRepository"""
        factory = self.session_factory
        if factory is None:
            from backend.database.core import AsyncSessionLocal
            factory = AsyncSessionLocal
            
        return ProjectRepository(config=self.config.get("project_manager_settings", {}), session_factory=factory)
    
    def _create_receipt_processor(self):
        """創建 ReceiptProcessor"""
        from backend.processing.receipt_processor import ReceiptProcessor
        logger.info("使用統一收據處理器 (ReceiptProcessor)")
        return ReceiptProcessor(config=self.config, db_path=self.global_db_path)

    def _start_global_workers(self):
        """啟動全局 Worker 線程"""
        # 影像 VLM Worker
        self._worker_thread = threading.Thread(
            target=global_receipt_worker_loop,
            args=(self,),
            name="GlobalReceiptWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("[Engine] VLM-First Worker 已啟動")

    async def recover_pending_tasks(self):
        """Server 啟動時恢復未完成的任務"""
        logger.info("[Engine] 正在掃描未完成任務...")
        
        try:
            projects = await self.project_repo.list_projects()
            total_recovered = 0
            
            for project in projects:
                project_id = project.get("id", project.get("project_id", ""))
                if not project_id:
                    continue
                    
                try:
                    job_repo = self.get_job_repo(project_id)
                    jobs = await job_repo.list_jobs()
                    
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

    @property
    def global_db_path(self):
        """單一真理：唯一的全域 SQLite 資料庫路徑（遵照 config.json 裡的設定）。"""
        return self.config.get("project_manager_settings", {}).get("global_db_path", "global.db")

    def get_job_repo(self, project_id: str) -> JobRepository:
        """取得特定專案的 JobRepository (singleton per project, 全域集中 DB)。"""
        with self._repo_lock:
            if project_id not in self._job_repos:
                factory = self.session_factory
                if factory is None:
                    from backend.database.core import AsyncSessionLocal
                    factory = AsyncSessionLocal
                self._job_repos[project_id] = JobRepository(project_id, session_factory=factory)
            return self._job_repos[project_id]

    async def _ensure_project_editable(self, project_id: str):
        await self.project_repo.assert_project_editable(project_id)

    # ========================================
    # Job Operations (直接操作 JobRepository)
    # ========================================

    async def enqueue_job(self, project_id: str, image_path: str) -> str:
        """建立新 Job 並加入佇列。 (針對圖片)"""
        job_repo = self.get_job_repo(project_id)
        job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        await job_repo.insert_job(job_id, image_path, "ready")
        await job_repo.emit_event(job_id, "enqueued", {"image_path": image_path})
        return job_id

    async def claim_job(self, project_id: str, job_id: str) -> bool:
        """將 Job 標記為 running。"""
        job_repo = self.get_job_repo(project_id)
        result = await job_repo.update_job(job_id, status="running")
        if result:
            await job_repo.emit_event(job_id, "claimed", {})
        return result

    async def complete_job(
        self,
        project_id: str,
        job_id: str,
        vlm_result: dict,
        validation: dict = None,
        stats: dict = None,
        qr_verified: bool = False,
    ) -> bool:
        """完成 VLM 處理。"""
        job_repo = self.get_job_repo(project_id)
        return await job_repo.complete_vlm(job_id, vlm_result, validation, stats, qr_verified)

    async def fail_job(self, project_id: str, job_id: str, reason: str = ""):
        """標記 Job 失敗。"""
        job_repo = self.get_job_repo(project_id)
        await job_repo.update_job(job_id, status="failed")
        await job_repo.emit_event(job_id, "failed", {"reason": reason})

    async def delete_job(self, project_id: str, job_id: str) -> dict:
        """刪除 Job，並同步清除對應檔案與快取。"""
        await self._ensure_project_editable(project_id)
        job_repo = self.get_job_repo(project_id)
        file_cleanup = await self.file_ops.delete_job_files(project_id, job_id)
        deleted = await job_repo.delete_job(job_id)
        deferred_gc = await self.file_ops.flush_deferred_gc(project_id) if deleted else {
            "deleted_files": [],
            "missing_files": [],
            "kept_referenced": [],
        }
        return {
            "status": "deleted" if deleted else "not_found",
            "deleted": deleted,
            "file_cleanup": file_cleanup,
            "deferred_gc": deferred_gc,
        }

    # ========================================
    # Processing Queue
    # ========================================

    async def run_processing(self, project_id: str):
        """VLM-First 處理入口 - 將所有待處理任務加入佇列。"""
        logger.info(f"[Processing] 開始處理專案: {project_id}")
        try:
            await self._ensure_project_editable(project_id)
            job_repo = self.get_job_repo(project_id)
            jobs = await job_repo.list_jobs()
            queued = 0
            
            for job in jobs:
                if job["status"] in ("ready", "failed"):
                    await job_repo.update_job(job["job_id"], status="pending")
                    self.task_queue.put((project_id, job["job_id"]))
                    queued += 1
            
            await self.project_repo.update_project_status(project_id, "PROCESSING")
            logger.info(f"[Processing] 已將 {queued} 個任務加入佇列")
            
            return {"status": "processing_queued", "queued_count": queued, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"[Processing] 啟動失敗 {project_id}: {e}", exc_info=True)
            raise e

    async def run_single_processing(self, project_id: str, job_id: str):
        """將單一 Job 加入處理佇列。"""
        try:
            await self._ensure_project_editable(project_id)
            job_repo = self.get_job_repo(project_id)
            job = await job_repo.get_job(job_id)
            if not job:
                raise ValueError(f"Job not found: {job_id}")
            
            await job_repo.update_job(job_id, status="pending")
            self.task_queue.put((project_id, job_id))
            logger.info(f"[Single Processing] Job {job_id} 已加入佇列")
            
            return {"status": "queued", "job_id": job_id, "queue_size": self.task_queue.qsize()}
        except Exception as e:
            logger.error(f"Error queuing single processing for {job_id}: {e}")
            raise e

    # ========================================
    # Delegated Methods
    # ========================================

    async def create_project(self, project_id: str, files: list, name: str = None, metadata: dict = None):
        return await self.project_repo.setup_project(project_id, input_image=files, name=name, metadata=metadata)

    async def run_splitting(self, project_id: str, target_files: Optional[list[str]] = None):
        logger.info(f"[分割] 開始處理專案: {project_id}, 目標檔案={target_files}")
        await self._ensure_project_editable(project_id)
        result = await self.file_ops.run_splitting(project_id, target_files)
        logger.info(f"[分割] 完成: {project_id}")
        return result

    async def run_split_single(self, project_id: str, filename: str):
        """Split a single raw file."""
        logger.info(f"[分割] 單檔處理: {project_id}/{filename}")
        result = await self.file_ops.run_splitting(project_id, target_files=[filename])
        logger.info(f"[分割] 單檔完成: {filename}")
        return result

    async def get_raw_files(self, project_id: str):
        return self.file_service.get_raw_files(project_id)

    async def add_project_files(self, project_id: str, files: list[str], type: str = "raw"):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.add_project_files(project_id, files, type)

    async def rotate_image(self, project_id: str, filename: str, angle: int = 90):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.rotate_image(project_id, filename, angle)

    async def delete_raw_file(self, project_id: str, filename: str):
        await self._ensure_project_editable(project_id)
        return self.file_service.delete_raw_file(project_id, filename)

    async def save_manual_json(self, project_id: str, job_id: str, json_data: dict) -> bool:
        await self._ensure_project_editable(project_id)
        job_repo = self.get_job_repo(project_id)
        return await job_repo.save_manual_json(job_id, json_data)

    async def cleanup_preview_cache(self, max_age_hours: int = 24):
        return await self.file_ops.cleanup_all_projects_cache(max_age_hours=max_age_hours)

    async def optimize_jxl_storage_all_projects(self, force: bool = False):
        projects = await self.project_repo.list_projects()
        details = []
        total_optimized = 0
        total_failed = 0
        for project in projects:
            project_id = project.get("project_id") or project.get("id")
            if not project_id:
                continue
            summary = await self.file_ops.optimize_jxl_storage(project_id, force=force)
            details.append(summary)
            total_optimized += int(summary.get("optimized_jobs", 0))
            total_failed += int(summary.get("failed_jobs", 0))

        return {
            "status": "completed",
            "projects": len(details),
            "optimized_jobs": total_optimized,
            "failed_jobs": total_failed,
            "details": details,
        }

    async def detect_job_sub_rects(self, project_id: str, job_id: str):
        return await self.file_ops.detect_job_sub_rects(project_id, job_id)

    async def apply_job_resplit(self, project_id: str, job_id: str, sub_rects: list[dict]):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.apply_job_resplit(project_id, job_id, sub_rects)

    async def detect_raw_sub_rects(self, project_id: str, raw_filename: str):
        return await self.file_ops.detect_raw_sub_rects(project_id, raw_filename)

    async def apply_raw_resplit(self, project_id: str, raw_filename: str, sub_rects: list[dict]):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.apply_raw_resplit(project_id, raw_filename, sub_rects)

    async def run_excel(self, project_id: str):
        return await self.export_handler.run_excel(project_id)

    async def archive_project(self, project_id: str):
        return await self.export_handler.seal_project(project_id)
        
    async def generate_voucher_pdf(self, project_id: str) -> str:
        """生成憑證黏貼報表 PDF，回傳儲存路徑。"""
        job_repo = self.get_job_repo(project_id)
        jobs = await job_repo.list_jobs()
        
        # 只拿 status == 'done' 且尚未被刪除原始圖片的發票
        done_jobs = [j for j in jobs if j.get("status") == "done" and j.get("image_path")]
        
        # 依照 updated_at 排序一下
        done_jobs.sort(key=lambda x: x.get("updated_at", 0))
        
        # 正規化為絕對路徑，避免相對路徑在不同工作目錄下失敗
        root = self.project_repo._project_root(project_id)
        image_paths = []
        for j in done_jobs:
            p = Path(j["image_path"])
            if not p.is_absolute():
                p = root / "分割發票" / p
            image_paths.append(str(p))
        
        if not image_paths:
            raise ValueError("找不到任何已處理完成的憑證 (status='done')。請先完成至少一張憑證辨識。")
            
        root = self.project_repo._project_root(project_id)
        out_dir = root / "輸出結果"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_pdf_path = out_dir / f"憑證黏貼_自動生成_{project_id}.pdf"
        
        # 產生 PDF
        success = self.voucher_generator.generate_voucher_pdf(image_paths, str(out_pdf_path))
        if not success:
            raise RuntimeError("產生憑證黏貼 PDF 失敗。")
            
        return str(out_pdf_path)

    async def regenerate_project(self, project_id: str, excel_path: str):
        from backend.engine.regeneration_handler import RegenerationHandler
        handler = RegenerationHandler(self.project_repo, self.export_handler._excel_exporter)
        return await handler.regenerate_from_archive(project_id, excel_path, self.config)

    def get_queue_status(self) -> dict:
        """獲取當前佇列狀態"""
        return {
            "task_queue_size": self.task_queue.qsize(),
            "worker_alive": self._worker_thread.is_alive() if self._worker_thread else False,
            "mode": "vlm-first"
        }
