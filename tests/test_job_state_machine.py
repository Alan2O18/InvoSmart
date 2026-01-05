"""
Unit Tests for JobStateMachine

Tests job workflow transitions (claiming, completing, failing).
"""
import pytest
import json
from backend.managers.job_repository import JobRepository
from backend.managers.job_state_machine import JobStateMachine

class TestJobStateMachine:
    """JobStateMachine Integration Tests"""

    @pytest.fixture
    def sm(self, tmpdir):
        """Create a JobStateMachine with a JobRepository in temp dir."""
        repo = JobRepository(str(tmpdir), db_name="test_sm.db")
        return JobStateMachine(repo)

    def test_claim_for_ocr_success(self, sm):
        """Test claiming a job for OCR."""
        # Insert a ready OCR job
        sm.repo.insert_job("job_ocr", "img.jpg", "ready", "ocr")
        
        job = sm.claim_for_ocr()
        
        assert job is not None
        assert job["job_id"] == "job_ocr"
        assert job["image_path"] == "img.jpg"
        
        # Verify status updated to running
        db_job = sm.repo.get_job("job_ocr")
        assert db_job["status"] == "running"

    def test_claim_for_ocr_no_available_job(self, sm):
        """Test claiming when no job is ready."""
        job = sm.claim_for_ocr()
        assert job is None
        
        # Insert a job that is already running
        sm.repo.insert_job("job_running", "img.jpg", "running", "ocr")
        job = sm.claim_for_ocr()
        assert job is None

    def test_complete_ocr_advance_to_llm(self, sm):
        """Test completing OCR and advancing to LLM."""
        sm.repo.insert_job("job_ocr", "img.jpg", "running", "ocr")
        
        ocr_result = {"text": "abc"}
        stats = {"time": 1.0}
        success = sm.complete_ocr("job_ocr", ocr_result, advance_to_stage_llm=True, stats=stats)
        
        assert success is True
        
        job = sm.repo.get_job("job_ocr")
        assert job["stage"] == "llm"
        assert job["status"] == "ready"
        assert job["ocr_stats"] == json.dumps(stats, ensure_ascii=False)
        assert job["ocr_result_json"] == json.dumps(ocr_result, ensure_ascii=False)

    def test_complete_ocr_no_advance(self, sm):
        """Test completing OCR but staying in same stage (e.g. for inspection)."""
        sm.repo.insert_job("job_ocr_stay", "img.jpg", "running", "ocr")
        
        ocr_result = {"text": "abc"}
        success = sm.complete_ocr("job_ocr_stay", ocr_result, advance_to_stage_llm=False)
        
        assert success is True
        
        job = sm.repo.get_job("job_ocr_stay")
        assert job["stage"] == "ocr" # Remained OCR? 
        # Check implementation: 
        # UPDATE jobs SET status='ready'... WHERE job_id=?
        # It does NOT update stage if advance_to_stage_llm is False.
        # But wait, original code:
        # cur.execute("""UPDATE jobs SET ocr_result_json=?, ocr_stats=?, status='ready' ...""")
        # Typically the stage assumes it is already correct, but here we just update status to ready.
        # So stage should remain 'ocr'.
        assert job["stage"] == "ocr"
        assert job["status"] == "ready"

    def test_claim_for_llm_success(self, sm):
        """Test claiming a job for LLM."""
        # Insert a ready LLM job
        sm.repo.insert_job("job_llm", "img.jpg", "ready", "llm")
        # Ensure it has OCR result (required by claim_for_llm usually?)
        sm.repo.update_job("job_llm", ocr_result_json='{"text": "ocr"}')
        
        job = sm.claim_for_llm()
        
        assert job is not None
        assert job["job_id"] == "job_llm"
        assert job["ocr_result"]["text"] == "ocr"
        
        db_job = sm.repo.get_job("job_llm")
        assert db_job["status"] == "running"

    def test_complete_llm_mark_final(self, sm):
        """Test completing LLM and finalizing."""
        sm.repo.insert_job("job_llm_run", "img.jpg", "running", "llm")
        
        llm_result = {"data": "done"}
        success = sm.complete_llm("job_llm_run", llm_result, mark_final=True)
        
        assert success is True
        
        job = sm.repo.get_job("job_llm_run")
        assert job["status"] == "done"
        assert job["stage"] == "finalize"
        assert job["llm_result_json"] == json.dumps(llm_result, ensure_ascii=False)

    def test_reset_and_claim_for_rerun(self, sm):
        """Test resetting a job for rerun."""
        # Job failed or done
        sm.repo.insert_job("job_rerun", "img.jpg", "done", "finalize")
        sm.repo.update_job("job_rerun", ocr_result_json='{"a":1}', llm_result_json='{"b":2}')
        
        # Reset for OCR
        job = sm.reset_and_claim("job_rerun", "ocr")
        
        assert job["job_id"] == "job_rerun"
        
        db_job = sm.repo.get_job("job_rerun")
        assert db_job["status"] == "running"
        assert db_job["stage"] == "ocr"
        # Stats should be cleared
        assert db_job["ocr_stats"] is None
        assert db_job["llm_stats"] is None
        # Results should be cleared
        assert db_job["ocr_result_json"] is None

    def test_fail_job(self, sm):
        """Test failing a job."""
        sm.repo.insert_job("job_fail", "img.jpg", "running", "ocr")
        
        sm.fail_job("job_fail", reason="Error")
        
        job = sm.repo.get_job("job_fail")
        assert job["status"] == "failed"
        
        # Check event
        conn = sm.repo._get_conn()
        row = conn.execute("SELECT payload FROM events WHERE job_id='job_fail' AND event_type='failed'").fetchone()
        conn.close()
        assert "Error" in row[0]
