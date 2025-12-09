# Job State Machine - 狀態機邏輯
"""
JobStateMachine handles all job state transitions and workflow logic.
Separates business logic from data persistence.
"""
import json
import time
from typing import Optional, Dict, Any


class JobStateMachine:
    """
    State machine for job workflow transitions.
    Handles claiming, completing, and failing jobs with proper state management.
    """
    
    def __init__(self, repository):
        """
        Initialize with a JobRepository instance.
        
        Args:
            repository: JobRepository instance for data access
        """
        self.repo = repository
    
    # ---------------------
    # Claim Operations
    # ---------------------
    def claim_for_ocr(self) -> Optional[Dict[str, Any]]:
        """Claim a job for OCR processing."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT job_id, image_path FROM jobs 
                   WHERE status IN ('ready', 'pending') AND stage='ocr' 
                   ORDER BY created_at ASC LIMIT 1"""
            )
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            
            job_id = row["job_id"]
            cur.execute(
                """UPDATE jobs SET status='running', 
                   ocr_start_at=strftime('%s','now'), 
                   updated_at=strftime('%s','now') 
                   WHERE job_id=?""",
                (job_id,),
            )
            conn.commit()
            conn.close()
            
            self.repo.emit_event(job_id, "ocr_claimed", {})
            return {"job_id": job_id, "image_path": row["image_path"]}
    
    def mark_ocr_stage_as_pending(self) -> int:
        """Mark all ready OCR jobs as pending. Returns count of updated jobs."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE jobs SET status='pending', updated_at=strftime('%s','now')
                   WHERE status='ready' AND stage='ocr'"""
            )
            count = cur.rowcount
            conn.commit()
            conn.close()
            return count

    def claim_for_llm(self) -> Optional[Dict[str, Any]]:
        """Claim a job for LLM processing."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            cur.execute(
                """SELECT job_id, image_path, ocr_result_json FROM jobs 
                   WHERE status IN ('ready', 'pending') AND stage='llm' 
                   ORDER BY created_at ASC LIMIT 1"""
            )
            row = cur.fetchone()
            if not row:
                # Check if there's still OCR work pending
                cur.execute(
                    """SELECT job_id FROM jobs 
                       WHERE (status IN ('ready', 'pending') AND stage='ocr') 
                       OR (status='running') LIMIT 1"""
                )
                if not cur.fetchone():
                    conn.close()
                    return "all_task_done"
                else:
                    conn.close()
                    return None
            
            job_id = row["job_id"]
            cur.execute(
                """UPDATE jobs SET status='running', 
                   llm_start_at=strftime('%s','now'), 
                   updated_at=strftime('%s','now') 
                   WHERE job_id=?""",
                (job_id,),
            )
            conn.commit()
            conn.close()
            
            self.repo.emit_event(job_id, "llm_claimed", {})
            
            try:
                ocr_data = (
                    json.loads(row["ocr_result_json"])
                    if row["ocr_result_json"]
                    else None
                )
            except Exception:
                ocr_data = None
            
            return {
                "job_id": job_id,
                "image_path": row["image_path"],
                "ocr_result": ocr_data,
            }
    
    def mark_llm_stage_as_pending(self) -> int:
        """Mark all ready LLM jobs as pending. Returns count of updated jobs."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE jobs SET status='pending', updated_at=strftime('%s','now')
                   WHERE status='ready' AND stage='llm'"""
            )
            count = cur.rowcount
            conn.commit()
            conn.close()
            return count

    def reset_and_claim(self, job_id: str, stage: str) -> Optional[Dict[str, Any]]:
        """
        Atomically reset a job to 'running' for a specific stage and return it.
        This prevents other workers from claiming it.
        Also clears completion timestamps to allow proper rerun.
        """
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            
            # First check if job exists
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return None
            
            # Update status and clear timestamps based on stage
            now = int(time.time())
            if stage == 'ocr':
                cur.execute(
                    """UPDATE jobs SET status='running', stage=?, updated_at=?, 
                       ocr_done_at=NULL, llm_done_at=NULL, 
                       ocr_result_json=NULL, llm_result_json=NULL 
                       WHERE job_id=?""",
                    (stage, now, job_id)
                )
            elif stage == 'llm':
                cur.execute(
                    """UPDATE jobs SET status='running', stage=?, updated_at=?, 
                       llm_done_at=NULL, llm_result_json=NULL 
                       WHERE job_id=?""",
                    (stage, now, job_id)
                )
            else:
                cur.execute(
                    "UPDATE jobs SET status='running', stage=?, updated_at=? WHERE job_id=?",
                    (stage, now, job_id)
                )
            conn.commit()
            
            # Fetch updated row data
            cur.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,))
            row = cur.fetchone()
            conn.close()
            
            self.repo.emit_event(job_id, f"{stage}_claimed_manual", {})
            
            res = {
                "job_id": job_id,
                "image_path": row["image_path"],
            }
            
            if stage == 'llm':
                try:
                    ocr_data = json.loads(row["ocr_result_json"]) if row["ocr_result_json"] else None
                except:
                    ocr_data = None
                res["ocr_result"] = ocr_data
                
            return res

    # ---------------------
    # Completion Operations
    # ---------------------
    def complete_ocr(
        self, job_id: str, ocr_result: Dict[str, Any], advance_to_stage_llm: bool = True
    ) -> bool:
        """Mark OCR stage as complete and optionally advance to LLM stage."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            now = int(time.time())
            ocr_json = json.dumps(ocr_result, ensure_ascii=False)
            
            if advance_to_stage_llm:
                cur.execute(
                    """UPDATE jobs SET ocr_result_json=?, ocr_done_at=?, 
                       stage='llm', status='ready', updated_at=strftime('%s','now') 
                       WHERE job_id=?""",
                    (ocr_json, now, job_id),
                )
            else:
                cur.execute(
                    """UPDATE jobs SET ocr_result_json=?, ocr_done_at=?, 
                       status='ready', updated_at=strftime('%s','now') 
                       WHERE job_id=?""",
                    (ocr_json, now, job_id),
                )
            conn.commit()
            conn.close()
            
            self.repo.emit_event(job_id, "ocr_completed", {"ocr_done_at": now})
            return True

    def complete_llm(
        self, job_id: str, llm_result: Dict[str, Any], mark_final: bool = True
    ) -> bool:
        """Mark LLM stage as complete and optionally finalize the job."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            now = int(time.time())
            llm_json = json.dumps(llm_result, ensure_ascii=False)
            
            if mark_final:
                cur.execute(
                    """UPDATE jobs SET llm_result_json=?, llm_done_at=?, 
                       status='done', stage='finalize', updated_at=strftime('%s','now') 
                       WHERE job_id=?""",
                    (llm_json, now, job_id),
                )
            else:
                cur.execute(
                    """UPDATE jobs SET llm_result_json=?, llm_done_at=?, 
                       status='pending', updated_at=strftime('%s','now') 
                       WHERE job_id=?""",
                    (llm_json, now, job_id),
                )
            conn.commit()
            conn.close()
            
            self.repo.emit_event(job_id, "llm_completed", {"llm_done_at": now})
            return True

    def fail_job(self, job_id: str, reason: str = "") -> None:
        """Mark a job as failed."""
        with self.repo.lock:
            conn = self.repo._get_conn()
            cur = conn.cursor()
            cur.execute(
                """UPDATE jobs SET status='failed', updated_at=strftime('%s','now') 
                   WHERE job_id=?""",
                (job_id,),
            )
            conn.commit()
            conn.close()
            
            self.repo.emit_event(job_id, "failed", {"reason": reason})
