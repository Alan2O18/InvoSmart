"""
Unit Tests for JobRepository (VLM-First)

Tests database operations for job persistence using a temporary directory.
Updated for VLM-First schema (no stage, no OCR/LLM split).
"""
import pytest
import os
import sqlite3
import json
import time
from backend.repositories.job_repository import JobRepository

class TestJobRepository:
    """JobRepository Integration Tests"""

    @pytest.fixture
    def repo(self, tmpdir):
        """Create a JobRepository in a temporary directory."""
        return JobRepository(str(tmpdir), db_name="test_jobs.db")

    def test_init_creates_tables(self, repo):
        """Test that tables are created on initialization."""
        conn = repo._get_conn()
        cur = conn.cursor()
        
        # Check jobs table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cur.fetchone() is not None
        
        # Check events table
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        assert cur.fetchone() is not None
        
        # Check VLM-First columns
        cur.execute("PRAGMA table_info(jobs)")
        columns = [row['name'] for row in cur.fetchall()]
        assert "vlm_result_json" in columns
        assert "vlm_stats" in columns
        assert "validation_json" in columns
        assert "qr_verified" in columns
        assert "manual_json_text" in columns
        # Old columns should NOT exist
        assert "stage" not in columns
        assert "ocr_result_json" not in columns
        assert "llm_result_json" not in columns
        
        conn.close()

    def test_insert_and_get_job(self, repo):
        """Test inserting and retrieving a job."""
        job_id = "job_123"
        image_path = "/path/to/img.jpg"
        
        repo.insert_job(job_id, image_path, "ready")
        
        job = repo.get_job(job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["image_path"] == image_path
        assert job["status"] == "ready"

    def test_insert_job_default_status(self, repo):
        """Test insert_job default status is 'ready'."""
        repo.insert_job("j_default", "/img.jpg")
        job = repo.get_job("j_default")
        assert job["status"] == "ready"

    def test_get_non_existent_job(self, repo):
        """Test getting a job that doesn't exist."""
        job = repo.get_job("non_existent")
        assert job is None

    def test_update_job(self, repo):
        """Test updating job fields."""
        job_id = "job_update"
        repo.insert_job(job_id, "/img.jpg", "ready")
        
        # Update status
        success = repo.update_job(job_id, status="running")
        assert success is True
        
        job = repo.get_job(job_id)
        assert job["status"] == "running"
        
        # Update multiple fields (VLM-First schema)
        success = repo.update_job(job_id, status="done", vlm_result_json='{"text": "hi"}')
        assert success is True
        
        job = repo.get_job(job_id)
        assert job["status"] == "done"
        assert job["vlm_result_json"] == '{"text": "hi"}'

    def test_update_non_existent_job(self, repo):
        """Test updating a missing job."""
        success = repo.update_job("fake_id", status="done")
        assert success is False

    def test_delete_job(self, repo):
        """Test deleting a job."""
        job_id = "job_del"
        repo.insert_job(job_id, "/img.jpg", "ready")
        
        success = repo.delete_job(job_id)
        assert success is True
        
        assert repo.get_job(job_id) is None
        
        # Delete again
        success = repo.delete_job(job_id)
        assert success is False

    def test_list_jobs(self, repo):
        """Test listing jobs with and without filter."""
        repo.insert_job("j1", "img1", "ready")
        repo.insert_job("j2", "img2", "done")
        repo.insert_job("j3", "img3", "ready")
        
        all_jobs = repo.list_jobs()
        assert len(all_jobs) == 3
        
        ready_jobs = repo.list_jobs(status="ready")
        assert len(ready_jobs) == 2
        assert all(j["status"] == "ready" for j in ready_jobs)

    def test_count_jobs(self, repo):
        """Test counting jobs (VLM-First: no stage parameter)."""
        repo.insert_job("j1", "img1", "ready")
        repo.insert_job("j2", "img2", "ready")
        repo.insert_job("j3", "img3", "done")
        
        counts = repo.count_jobs()
        assert counts["ready"] == 2
        assert counts["done"] == 1

    def test_complete_vlm(self, repo):
        """Test completing VLM processing for a job."""
        repo.insert_job("j_vlm", "img.jpg", "running")
        
        vlm_result = {"store_name": "TestStore", "total": 100}
        validation = {"confidence": 0.95}
        stats = {"processing_time_ms": 1500}
        
        success = repo.complete_vlm(
            "j_vlm", vlm_result,
            validation=validation,
            stats=stats,
            qr_verified=True
        )
        assert success is True
        
        job = repo.get_job("j_vlm")
        assert job["status"] == "done"
        assert json.loads(job["vlm_result_json"]) == vlm_result
        assert json.loads(job["validation_json"]) == validation
        assert json.loads(job["vlm_stats"]) == stats
        assert job["qr_verified"] == 1

    def test_emit_event(self, repo):
        """Test event logging."""
        job_id = "j_event"
        repo.insert_job(job_id, "img", "ready")
        
        repo.emit_event(job_id, "TEST_EVENT", {"foo": "bar"})
        
        conn = repo._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM events WHERE job_id=?", (job_id,))
        row = cur.fetchone()
        conn.close()
        
        assert row is not None
        assert row["event_type"] == "TEST_EVENT"
        payload = json.loads(row["payload"])
        assert payload["foo"] == "bar"

    def test_mark_stale_as_failed(self, repo):
        """Test marking stale jobs as failed."""
        # Stale job (simulate old created_at)
        repo.insert_job("stale_job", "img", "pending")
        # Manually update created_at to be old
        conn = repo._get_conn()
        old_time = time.time() - 10000
        conn.execute("UPDATE jobs SET created_at=? WHERE job_id='stale_job'", (old_time,))
        conn.commit()
        conn.close()
        
        # Fresh job
        repo.insert_job("fresh_job", "img", "pending")
        
        # Run stale check (threshold 100s)
        count = repo.mark_stale_as_failed(stale_seconds=100)
        assert count == 1
        
        stale = repo.get_job("stale_job")
        assert stale["status"] == "failed"
        
        fresh = repo.get_job("fresh_job")
        assert fresh["status"] == "pending"

    def test_has_pending_work(self, repo):
        """Test checking for pending work."""
        assert repo.has_pending_work() is False
        
        repo.insert_job("j1", "img", "ready")
        assert repo.has_pending_work() is True
        
        repo.update_job("j1", status="done")
        assert repo.has_pending_work() is False
