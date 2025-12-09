import os
import json
import threading
import logging
import traceback
from typing import Optional, Dict
from pathlib import Path

from backend.managers import ProjectManager, TaskManager
from backend.processing.ocr_handler import OCRHandler
from backend.processing.llm_handler import LLMHandler
from backend.processing.receipt_splitter import ReceiptSplitter

from .workers import start_cpu_worker, start_gpu_worker
from .file_ops import FileOps
from .export import ExportHandler

# Configure file-based logging
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "engine.log"

# Set up file handler
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Set up console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Configure root logger for backend
backend_logger = logging.getLogger('backend')
backend_logger.setLevel(logging.DEBUG)
backend_logger.addHandler(file_handler)
backend_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

class Engine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Engine, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.config = self._load_config()
        self.project_manager = ProjectManager(config=self.config.get("project_manager_settings", {}))
        self.ocr_handler = OCRHandler(config=self.config)
        self.llm_handler = LLMHandler(config=self.config)
        self.receipt_splitter = ReceiptSplitter(config={})
        
        # Sub-components
        self.file_ops = FileOps(self.project_manager, self.receipt_splitter, self)
        self.export_handler = ExportHandler(self.project_manager)

        # State
        self.active_workers = {} # project_id -> {threads: [], stop_event: Event}
        self.task_managers: Dict[str, TaskManager] = {} # Singleton cache for TaskManagers
        self.tm_lock = threading.Lock()
        
        self.initialized = True

    def _load_config(self):
        # Try local config first
        local_config = "config.json"
        if os.path.exists(local_config):
            with open(local_config, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_task_manager(self, project_id: str) -> TaskManager:
        """
        Singleton access to TaskManager for a given project.
        """
        with self.tm_lock:
            if project_id not in self.task_managers:
                root = self.project_manager._project_root(project_id)
                self.task_managers[project_id] = TaskManager(str(root))
            return self.task_managers[project_id]

    # --- Worker Management ---

    def run_ocr(self, project_id: str):
        """
        Start CPU worker for OCR.
        """
        try:
            tm = self.get_task_manager(project_id)
            
            thread_name = f"CPU-{project_id}"
            if any(t.name == thread_name for t in threading.enumerate()):
                 return {"status": "ocr_already_running"}

            cpu_thread = threading.Thread(
                target=start_cpu_worker, 
                args=(tm, project_id, self.ocr_handler),
                name=thread_name
            )
            cpu_thread.start()
            
            self.project_manager.update_project_status(project_id, "PROCESSING")
            return {"status": "ocr_started"}
        except Exception as e:
            logger.error(f"Error starting OCR for {project_id}: {e}")
            raise e

    def run_llm(self, project_id: str):
        """
        Start GPU worker for LLM.
        """
        try:
            tm = self.get_task_manager(project_id)
            
            thread_name = f"GPU-{project_id}"
            if any(t.name == thread_name for t in threading.enumerate()):
                 return {"status": "llm_already_running"}

            gpu_thread = threading.Thread(
                target=start_gpu_worker, 
                args=(tm, project_id, self.llm_handler),
                name=thread_name
            )
            gpu_thread.start()
            
            return {"status": "llm_started"}
        except Exception as e:
            logger.error(f"Error starting LLM for {project_id}: {e}")
            raise e

    # --- Delegated Methods ---

    def create_project(self, project_id: str, files: list, metadata: dict = None):
        # Delegate to ProjectManager, but we might need to do initial file copy via FileOps or PM
        # PM.setup_project copies files if provided.
        # But Engine.create_project usually implies full setup.
        # Let's keep it simple and delegate to PM + FileOps if needed.
        res = self.project_manager.setup_project(project_id, input_image=files, metadata=metadata)
        return res

    def run_splitting(self, project_id: str, target_files: Optional[list[str]] = None):
        logger.info(f"run_splitting called for {project_id}, target_files={target_files}")
        return self.file_ops.run_splitting(project_id, target_files)

    def run_split_single(self, project_id: str, filename: str):
        """Split a single raw file."""
        logger.info(f"run_split_single called for {project_id}, file={filename}")
        return self.file_ops.run_splitting(project_id, target_files=[filename])

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
        # Not implemented in original engine, but requested in router?
        # Implementing basic deletion
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
    
    def run_single_ocr(self, project_id: str, job_id: str):
        """
        Run OCR for a single job immediately using an ephemeral thread.
        Does NOT advance to LLM stage automatically.
        """
        try:
            tm = self.get_task_manager(project_id)
            # Atomically reset and claim the job so generic workers don't touch it
            task = tm.reset_and_claim(job_id, 'ocr')
            if not task:
                raise ValueError("Job not found or could not be claimed")
            
            # Spawn ephemeral thread to process just this task
            from .workers import process_ocr_task
            t = threading.Thread(
                target=process_ocr_task,
                args=(tm, task, self.ocr_handler),
                kwargs={"auto_advance": False},
                name=f"SingleOCR-{job_id}"
            )
            t.start()
            return {"status": "single_ocr_started"}
        except Exception as e:
            logger.error(f"Error running single OCR for {job_id}: {e}")
            raise e

    def run_single_llm(self, project_id: str, job_id: str):
        """
        Run LLM for a single job immediately using an ephemeral thread.
        """
        try:
            tm = self.get_task_manager(project_id)
            # Atomically reset and claim
            task = tm.reset_and_claim(job_id, 'llm')
            if not task:
                raise ValueError("Job not found or could not be claimed")
            
            # Spawn ephemeral thread
            from .workers import process_llm_task
            t = threading.Thread(
                target=process_llm_task,
                args=(tm, task, self.llm_handler),
                kwargs={"auto_advance": False},
                name=f"SingleLLM-{job_id}"
            )
            t.start()
            return {"status": "single_llm_started"}
        except Exception as e:
            logger.error(f"Error running single LLM for {job_id}: {e}")
            raise e
