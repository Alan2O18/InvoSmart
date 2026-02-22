"""
Manual Correction User Case Test (VLM-First)

Tests the complete workflow of manually editing VLM results and saving corrections.
Updated for VLM-First architecture (save_manual_json, complete_vlm, no OCR/LLM split).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import json


class TestManualCorrectionWorkflow:
    """Tests for manual correction user workflow (VLM-First)."""

    @pytest.fixture(scope="function")
    def setup_project_with_job(self, real_engine_with_temp_workspace):
        """
        Setup a project with a single job for manual correction testing.
        Uses VLM-First JobRepository API.
        """
        engine = real_engine_with_temp_workspace
        project_id = "test_manual_correction"
        
        # Register project directly
        project_root = engine.project_repo.workspace_root / project_id
        engine.project_repo.register_project(
            project_id, 
            "Manual Correction Test", 
            str(project_root)
        )
        
        # Setup project layout and jobs.db
        engine.project_repo._ensure_layout(project_root)
        engine.project_repo._init_jobs_db(str(project_root / "jobs.db"))
        
        # Get job repo and create a test job
        tm = engine.get_task_manager(project_id)
        job_id = tm.insert_job("test_job", "/fake/test_image.jpg")
        
        yield {
            "engine": engine,
            "project_id": project_id,
            "tm": tm,
            "job_id": job_id,
            "project_root": project_root
        }

    def test_save_and_retrieve_manual_json(self, setup_project_with_job):
        """Test saving manual correction JSON to a job."""
        ctx = setup_project_with_job
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Save manual JSON correction
        manual_data = {
            "store_name": "測試公司",
            "total": 500,
            "items": [{"name": "商品A", "quantity": 1, "price": 500}]
        }
        tm.save_manual_json(job_id, manual_data)
        
        # Retrieve and verify
        job_details = tm.get_job_details(job_id)
        assert json.loads(job_details["manual_json_text"]) == manual_data

    def test_regenerate_from_manual_text(self, setup_project_with_job):
        """Test that manual JSON can override VLM result."""
        ctx = setup_project_with_job
        engine = ctx["engine"]
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # First complete VLM processing
        vlm_result = {
            "store_name": "原始店家",
            "total": 400,
            "items": [{"name": "商品X", "quantity": 1, "price": 400}]
        }
        tm.complete_vlm(job_id, vlm_result)
        
        # Save manual correction
        manual_data = {
            "store_name": "修正後店家",
            "total": 500,
            "items": [{"name": "商品A", "quantity": 1, "price": 500}]
        }
        tm.save_manual_json(job_id, manual_data)
        
        # Verify both results are saved
        job_details = tm.get_job_details(job_id)
        assert job_details["vlm_result"]["store_name"] == "原始店家"
        assert json.loads(job_details["manual_json_text"])["store_name"] == "修正後店家"

    def test_full_manual_correction_workflow(self, setup_project_with_job):
        """Test complete manual correction workflow."""
        ctx = setup_project_with_job
        engine = ctx["engine"]
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Step 1: VLM processing produces initial result with errors
        vlm_result = {
            "store_name": "測試店",
            "items": [
                {"name": "每報紙", "quantity": 2, "price": 100.0},
                {"name": "圆头笔", "quantity": 3, "price": 50.0}
            ],
            "total": 350.0
        }
        tm.complete_vlm(job_id, vlm_result)
        
        # Step 2: User reviews VLM result and makes corrections
        job_details = tm.get_job_details(job_id)
        original_result = job_details["vlm_result"]
        assert original_result["items"][0]["name"] == "每報紙"  # Has error
        
        # Step 3: User manually corrects the data
        corrected_data = {
            "store_name": "測試店家",
            "items": [
                {"name": "海報紙", "quantity": 2, "price": 100.0},
                {"name": "圓頭筆", "quantity": 3, "price": 50.0}
            ],
            "total": 350.0
        }
        tm.save_manual_json(job_id, corrected_data)
        
        # Step 4: Verify final result
        final_job = tm.get_job_details(job_id)
        manual_result = json.loads(final_job["manual_json_text"])
        
        assert manual_result["items"][0]["name"] == "海報紙"
        assert manual_result["items"][1]["name"] == "圓頭筆"
        assert manual_result["total"] == 350.0

    def test_manual_correction_persists(self, setup_project_with_job):
        """Test that manual corrections persist in database."""
        ctx = setup_project_with_job
        engine = ctx["engine"]
        project_id = ctx["project_id"]
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Complete VLM and save manual correction
        tm.complete_vlm(job_id, {"store_name": "原始", "total": 100})
        manual_data = {"store_name": "修正後", "total": 200}
        tm.save_manual_json(job_id, manual_data)
        
        # Verify manual JSON is saved
        job_details = tm.get_job_details(job_id)
        assert json.loads(job_details["manual_json_text"])["store_name"] == "修正後"
        
        # Simulate new session by getting a new job repo for same project
        tm2 = engine.get_task_manager(project_id)
        job_details2 = tm2.get_job_details(job_id)
        
        # Manual JSON should still be there
        assert json.loads(job_details2["manual_json_text"])["store_name"] == "修正後"

    def test_get_display_result_precedence(self, setup_project_with_job):
        """Test that display result prefers manual_json over vlm_result."""
        ctx = setup_project_with_job
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # No result yet
        result = tm.get_display_result(job_id)
        assert result is None or result == {}
        
        # After VLM completion, display VLM result
        tm.complete_vlm(job_id, {"store_name": "VLM", "total": 100})
        result = tm.get_display_result(job_id)
        assert result["store_name"] == "VLM"
        
        # After manual correction, display manual result
        tm.save_manual_json(job_id, {"store_name": "Manual", "total": 200})
        result = tm.get_display_result(job_id)
        assert result["store_name"] == "Manual"
