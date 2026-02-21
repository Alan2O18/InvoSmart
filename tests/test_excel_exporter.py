"""
excel_exporter.py 單元測試

測試 ExcelExporter 的 archive_to_excel 與 _generate_text_from_llm_result。
Phase 2 更新：改用 mock.patch 攔截 JobRepository，不再依賴 per-project jobs.db。
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.engine.excel_exporter import ExcelExporter


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_project_repo(tmp_path):
    """建立 mock project repo (Phase 2：不需要 jobs.db 檔案)"""
    repo = MagicMock()
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    repo._project_root.return_value = project_root
    repo.workspace_root = tmp_path
    return repo


def _make_job(**kwargs):
    """建立測試用 job dict（模擬 JobRepository.list_jobs() 的回傳格式）"""
    defaults = {
        "job_id": "j1",
        "project_id": "test_project",
        "image_path": "/tmp/receipt.jpg",
        "status": "done",
        "vlm_result_json": None,
        "vlm_stats": None,
        "validation_json": None,
        "manual_json_text": None,
        "qr_verified": 0,
        "created_at": time.time() - 10,
        "updated_at": time.time(),
    }
    defaults.update(kwargs)
    return defaults


# ============================================================================
# archive_to_excel 測試
# ============================================================================

class TestArchiveToExcel:
    """測試 Excel 匯出"""

    @patch("backend.engine.excel_exporter.JobRepository")
    def test_export_empty_project(self, MockJobRepo, mock_project_repo):
        """空專案（無 jobs）→ FileNotFoundError: No jobs found"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.list_jobs.return_value = []
        MockJobRepo.return_value = mock_repo_instance

        exporter = ExcelExporter(mock_project_repo)
        with pytest.raises(FileNotFoundError, match="No jobs found"):
            exporter.archive_to_excel("test_project")

    @patch("backend.engine.excel_exporter.JobRepository")
    def test_export_with_jobs(self, MockJobRepo, mock_project_repo):
        """含有 jobs 的專案正常匯出 Excel"""
        vlm_json = json.dumps({
            "receipt_type": "electronic",
            "header": {"supplier": "Test Store", "date": "2025-01-01"},
            "items": [{"description": "Item A", "quantity": 1, "price": 100}],
            "summary": {"total": 100},
        }, ensure_ascii=False)

        mock_repo_instance = MagicMock()
        mock_repo_instance.list_jobs.return_value = [
            _make_job(job_id="j1", vlm_result_json=vlm_json,
                      vlm_stats=json.dumps({"processing_time_ms": 1500}))
        ]
        MockJobRepo.return_value = mock_repo_instance

        exporter = ExcelExporter(mock_project_repo)
        result_path = exporter.archive_to_excel("test_project")

        assert Path(result_path).exists()

        import pandas as pd
        xls = pd.ExcelFile(result_path)
        assert "主表" in xls.sheet_names
        assert "細項表" in xls.sheet_names

    @patch("backend.engine.excel_exporter.JobRepository")
    def test_export_with_custom_name(self, MockJobRepo, mock_project_repo):
        """自訂匯出檔名"""
        mock_repo_instance = MagicMock()
        mock_repo_instance.list_jobs.return_value = [_make_job()]
        MockJobRepo.return_value = mock_repo_instance

        exporter = ExcelExporter(mock_project_repo)
        result_path = exporter.archive_to_excel("test_project", excel_name="custom_name.xlsx")

        assert "custom_name.xlsx" in result_path

    def test_export_nonexistent_project(self, mock_project_repo):
        """專案資料夾不存在 → FileNotFoundError"""
        nonexistent = mock_project_repo._project_root.return_value / "ghost"
        mock_project_repo._project_root.return_value = nonexistent

        exporter = ExcelExporter(mock_project_repo)
        with pytest.raises(FileNotFoundError):
            exporter.archive_to_excel("ghost_project")


# ============================================================================
# _generate_text_from_llm_result 測試
# ============================================================================

class TestGenerateText:
    """測試 LLM 結果轉文字"""

    def test_generate_text_with_flat_structure(self, mock_project_repo):
        """從扁平結構生成文字"""
        exporter = ExcelExporter(mock_project_repo)
        parsed_llm = {
            "header": {"supplier": "Store ABC", "date": "2025-01-15"},
            "items": [
                {"description": "Tea", "quantity": 2, "price": 50},
                {"description": "Coffee", "quantity": 1, "price": 80},
            ],
            "summary": {"total": 180},
        }
        text = exporter._generate_text_from_llm_result(parsed_llm)
        assert text is not None
        assert len(text) > 0

    def test_generate_text_empty(self, mock_project_repo):
        """空 LLM 結果"""
        exporter = ExcelExporter(mock_project_repo)
        text = exporter._generate_text_from_llm_result({})
        assert text is not None
