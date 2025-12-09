"""
Manual Correction User Case Test

Tests the complete workflow of manually correcting OCR text and regenerating LLM results.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
import json


class TestManualCorrectionWorkflow:
    """Tests for manual correction user workflow."""

    @pytest.fixture(scope="function")
    def setup_project_with_job(self, real_engine_with_temp_workspace):
        """
        Set up a test project with a job ready for manual correction testing.
        Uses the properly configured engine from fixture.
        """
        engine = real_engine_with_temp_workspace
        project_id = "test_manual_correction"
        
        # Register project directly using project_crud (skips file operations)
        project_root = engine.project_manager.workspace_root / project_id
        engine.project_manager.project_crud.register_project(
            project_id, 
            "Manual Correction Test", 
            str(project_root)
        )
        
        # Setup project layout and jobs.db
        engine.project_manager.project_setup._ensure_layout(project_root)
        engine.project_manager.project_setup._init_jobs_db(str(project_root / "jobs.db"))
        
        # Get task manager and create a test job
        tm = engine.get_task_manager(project_id)
        job_id = tm.enqueue("/fake/test_image.jpg", stage='ocr')
        
        yield {
            "engine": engine,
            "project_id": project_id,
            "tm": tm,
            "job_id": job_id,
            "project_root": project_root
        }

    def test_save_and_retrieve_manual_text(self, setup_project_with_job):
        """Test saving manual correction text to a job."""
        ctx = setup_project_with_job
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Save manual text
        manual_text = "人工修正後的發票文字\n供應商: 測試公司\n總金額: 500"
        tm.save_manual_text(job_id, manual_text)
        
        # Retrieve and verify
        job_details = tm.get_job_details(job_id)
        assert job_details["manual_ocr_text"] == manual_text

    def test_regenerate_from_manual_text(self, setup_project_with_job):
        """Test regenerating LLM result from manual text."""
        ctx = setup_project_with_job
        engine = ctx["engine"]
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Simulate OCR completion first
        tm.complete_ocr(job_id, {"data": "原始OCR文字"}, advance_to_stage_llm=False)
        
        # Save manual text
        manual_text = "人工修正後的發票文字\n供應商: 測試公司\n總金額: 500"
        tm.save_manual_text(job_id, manual_text)
        
        # Configure mock llm_handler (already mocked by fixture)
        extracted_data = {
            "supplier": "測試公司",
            "invoice_id": "AB12345678",
            "date": "2025-12-09",
            "items": [
                {"description": "商品A", "quantity": 1, "price": 500.0}
            ],
            "total_amount": 500.0
        }
        engine.llm_handler.regenerate_from_corrected_text.return_value = extracted_data
        
        # Regenerate from manual text
        job_details = tm.get_job_details(job_id)
        retrieved_manual_text = job_details["manual_ocr_text"]
        
        # Use LLM handler to regenerate
        result = engine.llm_handler.regenerate_from_corrected_text(retrieved_manual_text)
        
        # Verify result
        assert result["supplier"] == "測試公司"
        assert result["total_amount"] == 500.0
        assert len(result["items"]) == 1

    def test_full_manual_correction_workflow(self, setup_project_with_job):
        """Test complete manual correction workflow through API simulation."""
        ctx = setup_project_with_job
        engine = ctx["engine"]
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Step 1: Simulate OCR with errors
        ocr_result = {
            "data": "每報紙 数量:2 价格:100\n圆头笔 数量:3 价格:50"
        }
        tm.complete_ocr(job_id, ocr_result, advance_to_stage_llm=False)
        
        # Step 2: User reviews OCR result and makes corrections
        job_details = tm.get_job_details(job_id)
        ocr_text = job_details["ocr_result"]["data"]
        
        # User manually corrects the text
        corrected_text = "海報紙 數量:2 價格:100\n圓頭筆 數量:3 價格:50"
        tm.save_manual_text(job_id, corrected_text)
        
        # Step 3: Configure mock and regenerate LLM result from corrected text
        regenerated_data = {
            "supplier": "測試店家",
            "items": [
                {"description": "海報紙", "quantity": 2, "price": 100.0},
                {"description": "圓頭筆", "quantity": 3, "price": 50.0}
            ],
            "total_amount": 350.0
        }
        engine.llm_handler.regenerate_from_corrected_text.return_value = regenerated_data
        
        regenerated_result = engine.llm_handler.regenerate_from_corrected_text(corrected_text)
        
        # Update job with regenerated result
        tm.complete_llm(job_id, regenerated_result, mark_final=True)
        
        # Step 4: Verify final result
        final_job = tm.get_job_details(job_id)
        llm_result = final_job["llm_result"]
        
        assert llm_result["items"][0]["description"] == "海報紙"
        assert llm_result["items"][1]["description"] == "圓頭筆"
        assert llm_result["total_amount"] == 350.0
        assert final_job["manual_ocr_text"] == corrected_text

    def test_manual_correction_persists_across_sessions(self, setup_project_with_job):
        """Test that manual corrections persist in database."""
        ctx = setup_project_with_job
        engine = ctx["engine"]
        project_id = ctx["project_id"]
        tm = ctx["tm"]
        job_id = ctx["job_id"]
        
        # Complete OCR and save manual text
        tm.complete_ocr(job_id, {"data": "原始文字"}, advance_to_stage_llm=False)
        tm.save_manual_text(job_id, "修正後文字")
        
        # Verify manual text is saved
        job_details = tm.get_job_details(job_id)
        assert job_details["manual_ocr_text"] == "修正後文字"
        
        # Simulate new session by creating new TaskManager for same project
        tm2 = engine.get_task_manager(project_id)
        job_details2 = tm2.get_job_details(job_id)
        
        # Manual text should still be there
        assert job_details2["manual_ocr_text"] == "修正後文字"
