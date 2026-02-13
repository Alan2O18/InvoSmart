"""
Unit Tests for JobRepository

Tests database operations for job persistence using a temporary directory.
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
        # tmpdir is a py.path.local object (from pytest)
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
        
        # Check columns (migration check)
        cur.execute("PRAGMA table_info(jobs)")
        columns = [row['name'] for row in cur.fetchall()]
        assert "ocr_stats" in columns
        assert "manual_ocr_text" in columns
        
        conn.close()

    def test_insert_and_get_job(self, repo):
        """Test inserting and retrieving a job."""
        job_id = "job_123"
        image_path = "/path/to/img.jpg"
        
        repo.insert_job(job_id, image_path, "ready", "ocr")
        
        job = repo.get_job(job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["image_path"] == image_path
        assert job["status"] == "ready"
        assert job["stage"] == "ocr"

    def test_get_non_existent_job(self, repo):
        """Test getting a job that doesn't exist."""
        job = repo.get_job("non_existent")
        assert job is None

    def test_update_job(self, repo):
        """Test updating job fields."""
        job_id = "job_update"
        repo.insert_job(job_id, "/img.jpg", "ready", "ocr")
        
        # Update status
        success = repo.update_job(job_id, status="running")
        assert success is True
        
        job = repo.get_job(job_id)
        assert job["status"] == "running"
        
        # Update multiple fields
        success = repo.update_job(job_id, status="done", ocr_result_json='{"text": "hi"}')
        assert success is True
        
        job = repo.get_job(job_id)
        assert job["status"] == "done"
        assert job["ocr_result_json"] == '{"text": "hi"}'

    def test_update_non_existent_job(self, repo):
        """Test updating a missing job."""
        success = repo.update_job("fake_id", status="done")
        assert success is False

    def test_delete_job(self, repo):
        """Test deleting a job."""
        job_id = "job_del"
        repo.insert_job(job_id, "/img.jpg", "ready", "ocr")
        
        success = repo.delete_job(job_id)
        assert success is True
        
        assert repo.get_job(job_id) is None
        
        # Delete again
        success = repo.delete_job(job_id)
        assert success is False

    def test_list_jobs(self, repo):
        """Test listing jobs with and without filter."""
        repo.insert_job("j1", "img1", "ready", "ocr")
        repo.insert_job("j2", "img2", "done", "llm")
        repo.insert_job("j3", "img3", "ready", "ocr")
        
        all_jobs = repo.list_jobs()
        assert len(all_jobs) == 3
        
        ready_jobs = repo.list_jobs(status="ready")
        assert len(ready_jobs) == 2
        assert all(j["status"] == "ready" for j in ready_jobs)

    def test_count_jobs(self, repo):
        """Test counting jobs."""
        repo.insert_job("j1", "img1", "ready", "ocr")
        repo.insert_job("j2", "img2", "ready", "ocr")
        repo.insert_job("j3", "img3", "done", "llm")
        
        counts = repo.count_jobs()
        assert counts["ready"] == 2
        assert counts["done"] == 1
        
        # Filter by stage
        counts_ocr = repo.count_jobs(stage="ocr")
        assert counts_ocr["ready"] == 2
        assert "done" not in counts_ocr

    def test_find_claimable_job(self, repo):
        """Test finding a claimable job."""
        # j1: done (not claimable)
        repo.insert_job("j1", "img1", "done", "ocr")
        # j2: ready, ocr (claimable) - Set old timestamp
        repo.insert_job("j2", "img2", "ready", "ocr")
        conn = repo._get_conn()
        conn.execute("UPDATE jobs SET created_at=1000 WHERE job_id='j2'")
        conn.commit()
        
        # j3: pending, ocr (claimable) - Set newer timestamp
        repo.insert_job("j3", "img3", "pending", "ocr")
        conn.execute("UPDATE jobs SET created_at=2000 WHERE job_id='j3'")
        conn.commit()
        conn.close()
        
        # j4: ready, llm (not claimable for 'ocr')
        repo.insert_job("j4", "img4", "ready", "llm")
        
        # Assume retrieval order by created_at. j2 created before j3.
        job = repo.find_claimable_job("ocr")
        assert job is not None
        assert job["job_id"] == "j2"
        
        # If j2 is taken (e.g. status changed to running)
        repo.update_job("j2", status="running")
        
        job = repo.find_claimable_job("ocr")
        assert job is not None
        assert job["job_id"] == "j3"
        
        # Test finding for another stage
        job_llm = repo.find_claimable_job("llm")
        assert job_llm["job_id"] == "j4"

    def test_emit_event(self, repo):
        """Test event logging."""
        job_id = "j_event"
        repo.insert_job(job_id, "img", "ready", "ocr")
        
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
        repo.insert_job("stale_job", "img", "pending", "ocr")
        # Manually update created_at to be old
        conn = repo._get_conn()
        old_time = time.time() - 10000
        conn.execute("UPDATE jobs SET created_at=? WHERE job_id='stale_job'", (old_time,))
        conn.commit()
        conn.close()
        
        # Fresh job
        repo.insert_job("fresh_job", "img", "pending", "ocr")
        
        # Run stale check (threshold 100s)
        count = repo.mark_stale_as_failed(stale_seconds=100)
        assert count == 1
        
        stale = repo.get_job("stale_job")
        assert stale["status"] == "failed"
        
        fresh = repo.get_job("fresh_job")
        assert fresh["status"] == "pending"
