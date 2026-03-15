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
from .pdf_worker import pdf_worker_loop
from .file_ops import FileOps
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
        
        # 獨立 PDF 任務佇列
        self.pdf_task_queue: queue.Queue = queue.Queue()
        
        # Worker 控制
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._pdf_worker_thread: Optional[threading.Thread] = None
        
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
        # 1. 影像 VLM Worker
        self._worker_thread = threading.Thread(
            target=global_receipt_worker_loop,
            args=(self,),
            name="GlobalReceiptWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info("[Engine] VLM-First Worker 已啟動")
        
        # 2. 獨立 PDF Worker
        self._pdf_worker_thread = threading.Thread(
            target=pdf_worker_loop,
            args=(self,),
            name="PDFProcessingWorker",
            daemon=True
        )
        self._pdf_worker_thread.start()
        logger.info("[Engine] PDF Processing Worker 已啟動")

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

    async def enqueue_pdf_upload(self, project_id: str, source_pdf_path: str, image_path: str) -> str:
        """
        將上傳的 PDF 建立為 Job。
        image_path 會指向已抽取的首頁 JPG (供 VLM 分析)。
        source_pdf_path 保存 PDF 原始路徑。
        """
        job_repo = self.get_job_repo(project_id)
        job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
        # 1. 建立 job (此時會帶入 image_path 讓 VLM 覺得這是一張圖片)
        await job_repo.insert_job(job_id, image_path, "ready")
        
        # 2. 補充 PDF 特殊欄位 (Bug 1 fix: 同時設定 compressed_pdf_path 讓 Worker 有輸出路徑)
        source_dir = os.path.dirname(source_pdf_path)
        output_dir = os.path.join(os.path.dirname(source_dir), "輸出結果")  # 與 原始輸入 平行
        os.makedirs(output_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(source_pdf_path))[0]
        compressed_pdf_path = os.path.join(output_dir, f"{stem}_compressed.pdf")
        
        await job_repo.update_job(
            job_id,
            source_pdf_path=source_pdf_path,
            compressed_pdf_path=compressed_pdf_path,
            pdf_status="uploaded"
        )
        
        # 3. 發送事件
        await job_repo.emit_event(job_id, "enqueued_pdf", {"source_pdf_path": source_pdf_path, "image_path": image_path})
        return job_id

    async def enqueue_pdf_job(self, project_id: str, job_id: str, commands: dict) -> bool:
        """
        將已現存的 Job 加入 PDF 處理佇列。
        前端送出蓋章排版指令時呼叫此方法。
        """
        await self._ensure_project_editable(project_id)
        job_repo = self.get_job_repo(project_id)
        # 更新狀態為準備壓縮
        await job_repo.update_job(job_id, pdf_status="pending_compression")
        
        # 將任務推入獨立佇列
        self.pdf_task_queue.put((project_id, job_id, commands))
        logger.info(f"[Engine] PDF 任務 {job_id} 已加入隊列")
        return True

    async def claim_job(self, project_id: str, job_id: str) -> bool:
        """將 Job 標記為 running。"""
        job_repo = self.get_job_repo(project_id)
        result = await job_repo.update_job(job_id, status="running")
        if result:
            await job_repo.emit_event(job_id, "claimed", {})
        return result

    async def complete_job(self, project_id: str, job_id: str, vlm_result: dict,
                     validation: dict = None, stats: dict = None,
                     qr_verified: bool = False) -> bool:
        """完成 VLM 處理。"""
        job_repo = self.get_job_repo(project_id)
        return await job_repo.complete_vlm(job_id, vlm_result, validation, stats, qr_verified)

    async def fail_job(self, project_id: str, job_id: str, reason: str = ""):
        """標記 Job 失敗。"""
        job_repo = self.get_job_repo(project_id)
        await job_repo.update_job(job_id, status="failed")
        await job_repo.emit_event(job_id, "failed", {"reason": reason})

    async def delete_job(self, project_id: str, job_id: str) -> bool:
        """刪除 Job。"""
        await self._ensure_project_editable(project_id)
        job_repo = self.get_job_repo(project_id)
        return await job_repo.delete_job(job_id)

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
        return self.file_ops.get_raw_files(project_id)

    async def add_project_files(self, project_id: str, files: list[str], type: str = "raw"):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.add_project_files(project_id, files, type)

    async def add_pdf_files(self, project_id: str, files: list[str]):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.add_pdf_files(project_id, files)

    async def rotate_image(self, project_id: str, filename: str, angle: int = 90):
        await self._ensure_project_editable(project_id)
        return await self.file_ops.rotate_image(project_id, filename, angle)

    async def delete_raw_file(self, project_id: str, filename: str):
        try:
            await self._ensure_project_editable(project_id)
            root = self.project_repo._project_root(project_id)
            path = root / "原始輸入" / filename
            if path.exists():
                os.remove(path)
                return {"status": "deleted"}
            return {"status": "not_found"}
        except Exception as e:
            logger.error(f"Error deleting raw file: {e}")
            raise e

    async def save_manual_json(self, project_id: str, job_id: str, json_data: dict) -> bool:
        await self._ensure_project_editable(project_id)
        job_repo = self.get_job_repo(project_id)
        return await job_repo.save_manual_json(job_id, json_data)

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
        
        # Bug 1 fix: 正規化為絕對路徑，避免相對路徑找不到檔案
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
