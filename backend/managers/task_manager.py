# Task Manager - Facade 整合 Job Repository 和 State Machine
"""
TaskManager (refactored)

This module provides backward-compatible facade for task management.
The actual implementations are split into:
- job_repository.py: Data access layer (CRUD, queries)
- job_state_machine.py: State transition logic (claim, complete, fail)
"""
import json
import time
import uuid
from typing import Optional, Dict, Any, List

from backend.managers.job_repository import JobRepository, DEFAULT_DB_NAME
from backend.managers.job_state_machine import JobStateMachine


class TaskManager:
    """
    Facade class that provides backward-compatible interface.
    Delegates to JobRepository and JobStateMachine internally.
    """
    
    def __init__(self, project_dir: str, db_name: str = DEFAULT_DB_NAME):
        self.project_dir = project_dir
        
        # Initialize components
        self._repository = JobRepository(project_dir, db_name)
        self._state_machine = JobStateMachine(self._repository)
        
        # Expose lock and db_path for backward compatibility
        self.lock = self._repository.lock
        self.db_path = self._repository.db_path

    # ---------------------
    # Basic queue ops (delegated to state machine or repository)
    # ---------------------
    def enqueue(self, image_path: str, job_id: str = "", stage: str = "ocr") -> str:
        """Enqueue a new job for processing."""
        if job_id == "":
            job_id = f"job-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        
        self._repository.insert_job(job_id, image_path, 'ready', stage)
        self._repository.emit_event(
            job_id, "enqueued", {"image_path": image_path, "stage": stage}
        )
        return job_id

    def claim_for_ocr(self) -> Optional[Dict[str, Any]]:
        """Claim a job for OCR processing."""
        return self._state_machine.claim_for_ocr()

    def claim_for_llm(self) -> Optional[Dict[str, Any]]:
        """Claim a job for LLM processing."""
        return self._state_machine.claim_for_llm()

    def reset_and_claim(self, job_id: str, stage: str) -> Optional[Dict[str, Any]]:
        """Reset and claim a job for reprocessing."""
        return self._state_machine.reset_and_claim(job_id, stage)

    def complete_ocr(
        self, job_id: str, ocr_result: Dict[str, Any], advance_to_stage_llm: bool = True
    ) -> bool:
        """Complete OCR stage."""
        return self._state_machine.complete_ocr(job_id, ocr_result, advance_to_stage_llm)

    def complete_llm(
        self, job_id: str, llm_result: Dict[str, Any], mark_final: bool = True
    ) -> bool:
        """Complete LLM stage."""
        return self._state_machine.complete_llm(job_id, llm_result, mark_final)

    def fail_job(self, job_id: str, reason: str = "") -> None:
        """Mark job as failed."""
        self._state_machine.fail_job(job_id, reason)

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        result = self._repository.delete_job(job_id)
        if result:
            self._repository.emit_event(job_id, "deleted", {})
        return result

    # ---------------------
    # Query / monitoring helpers (delegated to repository)
    # ---------------------
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID."""
        return self._repository.get_job(job_id)

    def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs."""
        return self._repository.list_jobs(status)

    def count_jobs(self, stage: Optional[str] = None) -> Dict[str, int]:
        """Count jobs by status."""
        return self._repository.count_jobs(stage)

    # ---------------------
    # Administrative helpers
    # ---------------------
    def dump_all(self) -> Dict[str, Any]:
        """Dump all database contents."""
        return self._repository.dump_all()

    def mark_all_pending_as_failed_if_stale(self, stale_seconds: int = 60 * 60 * 6) -> int:
        """Mark stale jobs as failed."""
        return self._repository.mark_stale_as_failed(stale_seconds)

    def _emit_event(self, job_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit an event (for backward compatibility)."""
        self._repository.emit_event(job_id, event_type, payload)

    # --- Manual Correction Methods ---
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full job details including OCR/LLM results and manual text."""
        with self._repository.lock:
            conn = self._repository._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Parse JSON fields
            ocr_result = None
            llm_result = None
            try:
                if row["ocr_result_json"]:
                    ocr_result = json.loads(row["ocr_result_json"])
            except:
                pass
            try:
                if row["llm_result_json"]:
                    llm_result = json.loads(row["llm_result_json"])
            except:
                pass
            
            return {
                "job_id": row["job_id"],
                "image_path": row["image_path"],
                "status": row["status"],
                "stage": row["stage"],
                "ocr_result": ocr_result,
                "llm_result": llm_result,
                "manual_ocr_text": row["manual_ocr_text"],
                "manual_updated_at": row["manual_updated_at"],
                "ocr_done_at": row["ocr_done_at"],
                "llm_done_at": row["llm_done_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def save_manual_text(self, job_id: str, manual_text: str) -> bool:
        """Save user's manual correction text."""
        with self._repository.lock:
            conn = self._repository._get_conn()
            cur = conn.cursor()
            now = int(time.time())
            cur.execute(
                """UPDATE jobs SET manual_ocr_text=?, manual_updated_at=?, updated_at=? 
                   WHERE job_id=?""",
                (manual_text, now, now, job_id)
            )
            conn.commit()
            affected = cur.rowcount
            conn.close()
            
            if affected > 0:
                self._repository.emit_event(job_id, "manual_text_saved", {"timestamp": now})
            return affected > 0
