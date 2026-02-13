# Task Manager - Facade 整合 Job Repository (VLM-First 簡化版)
"""
TaskManager

VLM-First 架構的簡化版 TaskManager。
移除 OCR/LLM 分階段邏輯，統一使用 VLM 處理。
"""
import json
import time
import uuid
from typing import Optional, Dict, Any, List

from backend.managers.job_repository import JobRepository, DEFAULT_DB_NAME


class TaskManager:
    """
    VLM-First TaskManager - 簡化版任務管理器
    """
    
    def __init__(self, project_dir: str, db_name: str = DEFAULT_DB_NAME):
        self.project_dir = project_dir
        self._repository = JobRepository(project_dir, db_name)
        
        # 暴露 lock 和 db_path 供外部使用
        self.lock = self._repository.lock
        self.db_path = self._repository.db_path

    # ---------------------
    # Basic Operations
    # ---------------------
    def enqueue(self, image_path: str, job_id: str = "") -> str:
        """Enqueue a new job for processing."""
        if job_id == "":
            job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
        self._repository.insert_job(job_id, image_path, 'ready')
        self._repository.emit_event(
            job_id, "enqueued", {"image_path": image_path}
        )
        return job_id

    def claim_job(self, job_id: str) -> bool:
        """Claim a job for processing (set to running)."""
        result = self._repository.update_job(job_id, status='running')
        if result:
            self._repository.emit_event(job_id, "claimed", {})
        return result

    def complete_job(self, job_id: str, vlm_result: Dict[str, Any],
                     validation: Dict[str, Any] = None,
                     stats: Dict[str, Any] = None,
                     qr_verified: bool = False) -> bool:
        """Complete VLM processing for a job."""
        return self._repository.complete_vlm(
            job_id, vlm_result, validation, stats, qr_verified
        )

    def fail_job(self, job_id: str, reason: str = "") -> None:
        """Mark job as failed."""
        self._repository.update_job(job_id, status='failed')
        self._repository.emit_event(job_id, "failed", {"reason": reason})

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        result = self._repository.delete_job(job_id)
        if result:
            self._repository.emit_event(job_id, "deleted", {})
        return result

    # ---------------------
    # Query Methods
    # ---------------------
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        return self._repository.get_job(job_id)

    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs."""
        return self._repository.list_jobs(status)

    def count_jobs(self) -> Dict[str, int]:
        """Count jobs by status."""
        return self._repository.count_jobs()

    # ---------------------
    # Job Details (for Edit View)
    # ---------------------
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full job details including VLM results and manual edits."""
        job = self._repository.get_job(job_id)
        if not job:
            return None
        
        # Parse JSON fields
        vlm_result = None
        validation = None
        vlm_stats = None
        
        try:
            if job.get("vlm_result_json"):
                vlm_result = json.loads(job["vlm_result_json"])
        except:
            pass
        
        try:
            if job.get("validation_json"):
                validation = json.loads(job["validation_json"])
        except:
            pass
        
        try:
            if job.get("vlm_stats"):
                vlm_stats = json.loads(job["vlm_stats"])
        except:
            pass
        
        manual_json = None
        try:
            if job.get("manual_json_text"):
                manual_json = json.loads(job["manual_json_text"])
        except:
            pass

        return {
            "job_id": job["job_id"],
            "image_path": job["image_path"],
            "status": job["status"],
            "vlm_result": vlm_result,
            "validation": validation,
            "vlm_stats": vlm_stats,
            "qr_verified": bool(job.get("qr_verified")),
            "manual_json": manual_json,
            "manual_updated_at": job.get("manual_updated_at"),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        }

    def save_manual_json(self, job_id: str, json_data: dict) -> bool:
        """儲存人工編輯的 JSON 結果"""
        json_text = json.dumps(json_data, ensure_ascii=False)
        now = int(time.time())
        
        result = self._repository.update_job(
            job_id,
            manual_json_text=json_text,
            manual_updated_at=now
        )
        
        if result:
            self._repository.emit_event(job_id, "manual_json_saved", {"timestamp": now})
        return result

    def get_display_result(self, job_id: str) -> Optional[dict]:
        """
        獲取顯示用的結果
        優先級: manual_json_text → vlm_result_json
        """
        job = self._repository.get_job(job_id)
        if not job:
            return None
        
        # 優先使用人工 JSON
        if job.get("manual_json_text"):
            try:
                return json.loads(job["manual_json_text"])
            except:
                pass
        
        # 其次使用 VLM 結果
        if job.get("vlm_result_json"):
            try:
                return json.loads(job["vlm_result_json"])
            except:
                pass
        
        return None

    # ---------------------
    # Administrative
    # ---------------------
    def dump_all(self) -> Dict[str, Any]:
        """Dump all database contents."""
        return self._repository.dump_all()

    def mark_all_pending_as_failed_if_stale(self, stale_seconds: int = 60 * 60 * 6) -> int:
        """Mark stale jobs as failed."""
        return self._repository.mark_stale_as_failed(stale_seconds)
