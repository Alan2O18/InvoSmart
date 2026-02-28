"""
Unit Tests for JobRepository (VLM-First)

Tests database operations for job persistence using a temporary directory.
Updated for VLM-First schema (no stage, no OCR/LLM split).
"""
import pytest
import os
import json
import time
from sqlalchemy import text
from backend.repositories.job_repository import JobRepository

@pytest.mark.asyncio
class TestJobRepository:
    """JobRepository Integration Tests"""

    @pytest.fixture
    def repo(self, async_session_factory):
        """Create a JobRepository using the in-memory testing DB."""
        return JobRepository("test_proj", session_factory=async_session_factory)

    async def test_init_creates_tables(self, repo, async_session_factory):
        """Test that tables are created on initialization and schema is correct."""
        async with async_session_factory() as session:
            # Check jobs table
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"))
            assert result.fetchone() is not None
            
            # Check events table
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='events'"))
            assert result.fetchone() is not None
            
            # Check VLM-First columns
            result = await session.execute(text("PRAGMA table_info(jobs)"))
            columns = [row[1] for row in result.fetchall()]  # PRAGMA returns (cid, name, type, ...)
            assert "vlm_result_json" in columns
            assert "vlm_stats" in columns
            assert "validation_json" in columns
            assert "qr_verified" in columns
            assert "manual_json_text" in columns
            # Old columns should NOT exist
            assert "stage" not in columns
            assert "ocr_result_json" not in columns
            assert "llm_result_json" not in columns

    async def test_insert_and_get_job(self, repo):
        """Test inserting and retrieving a job."""
        job_id = "job_123"
        image_path = "/path/to/img.jpg"
        
        await repo.insert_job(job_id, image_path, "ready")
        
        job = await repo.get_job(job_id)
        assert job is not None
        assert job["job_id"] == job_id
        assert job["image_path"] == image_path
        assert job["status"] == "ready"

    async def test_insert_job_default_status(self, repo):
        """Test insert_job default status is 'ready'."""
        await repo.insert_job("j_default", "/img.jpg")
        job = await repo.get_job("j_default")
        assert job["status"] == "ready"

    async def test_get_non_existent_job(self, repo):
        """Test getting a job that doesn't exist."""
        job = await repo.get_job("non_existent")
        assert job is None

    async def test_update_job(self, repo):
        """Test updating job fields."""
        job_id = "job_update"
        await repo.insert_job(job_id, "/img.jpg", "ready")
        
        # Update status
        success = await repo.update_job(job_id, status="running")
        assert success is True
        
        job = await repo.get_job(job_id)
        assert job["status"] == "running"
        
        # Update multiple fields (VLM-First schema)
        success = await repo.update_job(job_id, status="done", vlm_result_json='{"text": "hi"}')
        assert success is True
        
        job = await repo.get_job(job_id)
        assert job["status"] == "done"
        assert job["vlm_result_json"] == '{"text": "hi"}'

    async def test_update_non_existent_job(self, repo):
        """Test updating a missing job."""
        success = await repo.update_job("fake_id", status="done")
        assert success is False

    async def test_delete_job(self, repo):
        """Test deleting a job."""
        job_id = "job_del"
        await repo.insert_job(job_id, "/img.jpg", "ready")
        
        success = await repo.delete_job(job_id)
        assert success is True
        
        assert await repo.get_job(job_id) is None
        
        # Delete again
        success = await repo.delete_job(job_id)
        assert success is False

    async def test_list_jobs(self, repo):
        """Test listing jobs with and without filter."""
        await repo.insert_job("j1", "img1", "ready")
        await repo.insert_job("j2", "img2", "done")
        await repo.insert_job("j3", "img3", "ready")
        
        all_jobs = await repo.list_jobs()
        assert len(all_jobs) == 3
        
        ready_jobs = await repo.list_jobs(status="ready")
        assert len(ready_jobs) == 2
        assert all(j["status"] == "ready" for j in ready_jobs)

    async def test_count_jobs(self, repo):
        """Test counting jobs (VLM-First: no stage parameter)."""
        await repo.insert_job("j1", "img1", "ready")
        await repo.insert_job("j2", "img2", "ready")
        await repo.insert_job("j3", "img3", "done")
        
        counts = await repo.count_jobs()
        assert counts["ready"] == 2
        assert counts["done"] == 1

    async def test_complete_vlm(self, repo):
        """Test completing VLM processing for a job."""
        await repo.insert_job("j_vlm", "img.jpg", "running")
        
        vlm_result = {"store_name": "TestStore", "total": 100}
        validation = {"confidence": 0.95}
        stats = {"processing_time_ms": 1500}
        
        success = await repo.complete_vlm(
            "j_vlm", vlm_result,
            validation=validation,
            stats=stats,
            qr_verified=True
        )
        assert success is True
        
        job = await repo.get_job("j_vlm")
        assert job["status"] == "done"
        assert json.loads(job["vlm_result_json"]) == vlm_result
        assert json.loads(job["validation_json"]) == validation
        assert json.loads(job["vlm_stats"]) == stats
        assert job["qr_verified"] == 1

    async def test_emit_event(self, repo, async_session_factory):
        """Test event logging."""
        from backend.database.models import Project
        job_id = "j_event"
        
        # Inject parent project to satisfy FK constraint
        async with async_session_factory() as session:
            session.add(Project(project_id="test_proj"))
            await session.commit()
            
        await repo.insert_job(job_id, "img", "ready")
        
        await repo.emit_event(job_id, "TEST_EVENT", {"foo": "bar"})
        
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT * FROM events WHERE job_id='j_event'"))
            row = result.fetchone()
            
        assert row is not None
        assert row[2] == "TEST_EVENT"  # event_type is usually the 3rd column
        payload = json.loads(row[4])   # payload is now the 5th column (id, job_id, event_type, ts, payload)
        assert payload["foo"] == "bar"

    async def test_mark_stale_as_failed(self, repo, async_session_factory):
        """Test marking stale jobs as failed."""
        from backend.database.models import Project
        # Inject parent project to satisfy FK constraint
        async with async_session_factory() as session:
            session.add(Project(project_id="test_proj"))
            await session.commit()
            
        # Stale job (simulate old created_at)
        await repo.insert_job("stale_job", "img", "pending")
        # Manually update created_at to be old
        old_time = time.time() - 10000
        async with async_session_factory() as session:
            await session.execute(text(f"UPDATE jobs SET created_at={old_time} WHERE job_id='stale_job'"))
            await session.commit()
        
        # Fresh job
        await repo.insert_job("fresh_job", "img", "pending")
        
        # Run stale check (threshold 100s)
        count = await repo.mark_stale_as_failed(stale_seconds=100)
        assert count == 1
        
        stale = await repo.get_job("stale_job")
        assert stale["status"] == "failed"
        
        fresh = await repo.get_job("fresh_job")
        assert fresh["status"] == "pending"

    async def test_has_pending_work(self, repo, async_session_factory):
        """Test checking for pending work."""
        from backend.database.models import Project
        # Inject parent project to satisfy FK constraint
        async with async_session_factory() as session:
            session.add(Project(project_id="test_proj"))
            await session.commit()
            
        assert await repo.has_pending_work() is False
        
        await repo.insert_job("j1", "img", "ready")
        assert await repo.has_pending_work() is True
        
        await repo.update_job("j1", status="done")
        assert await repo.has_pending_work() is False

    async def test_save_manual_json_and_get_details(self, repo, async_session_factory):
        """Test syncing items to InvoiceItem table and stitching them back."""
        from backend.database.models import Project, InvoiceItem
        from sqlalchemy import select
        
        job_id = "job_manual_json"
        async with async_session_factory() as session:
            session.add(Project(project_id="test_proj"))
            await session.commit()
            
        await repo.insert_job(job_id, "img", "ready")
        
        # Initial VLM Result (with 1 item)
        initial_json = {
            "header": {"buyer": "A"},
            "items": [{"name": "Item 1", "price": 100, "qty": 1}]
        }
        await repo.update_job(job_id, vlm_result_json=json.dumps(initial_json))
        
        # User manually edits and saves JSON (now 2 items)
        manual_json = {
            "header": {"buyer": "A Edited"},
            "items": [
                {"name": "Item 1", "price": 100, "qty": 1},
                {"name": "Item 2", "price": 200, "qty": 2}
            ]
        }
        
        await repo.save_manual_json(job_id, manual_json)
        
        # 1. Verify DB Job record is updated
        job = await repo.get_job(job_id)
        assert job["manual_json_text"] is not None
        saved_manual = json.loads(job["manual_json_text"])
        assert saved_manual["header"]["buyer"] == "A Edited"
        
        # 2. Verify InvoiceItems were actually extracted and saved to DB
        async with async_session_factory() as session:
            result = await session.execute(select(InvoiceItem).where(InvoiceItem.job_id == job_id))
            items = result.scalars().all()
            assert len(items) == 2
            assert items[0].description == "Item 1"
            assert items[1].description == "Item 2"
            
        # 3. Verify get_job_details stitches items dynamically
        details = await repo.get_job_details(job_id)
        assert details["manual_json_text"] is not None
        parsed_manual = json.loads(details["manual_json_text"])
        assert "items" in parsed_manual
        assert len(parsed_manual["items"]) == 2
        
        # 4. Verify get_display_result (from manual json)
        display = await repo.get_display_result(job_id)
        assert display["header"]["buyer"] == "A Edited"
        assert len(display["items"]) == 2
