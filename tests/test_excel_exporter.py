"""
excel_exporter.py 單元測試

測試 ExcelExporter 的 archive_to_excel 與 _generate_text_from_llm_result。
"""
import pytest
import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock

from backend.engine.excel_exporter import ExcelExporter


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_project_repo(tmp_path):
    """建立帶有 jobs.db 的 mock project repo"""
    repo = MagicMock()
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    repo._project_root.return_value = project_root
    repo.workspace_root = tmp_path
    return repo


def _create_jobs_db(project_root, jobs=None):
    """在 project_root 中建立 jobs.db 並插入測試資料"""
    db_path = project_root / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            image_path TEXT,
            status TEXT,
            ocr_result_json TEXT,
            llm_result_json TEXT,
            ocr_stats TEXT,
            llm_stats TEXT,
            created_at REAL,
            updated_at REAL
        )
    """)

    if jobs:
        for j in jobs:
            cursor.execute("""
                INSERT INTO jobs (job_id, image_path, status, ocr_result_json,
                                  llm_result_json, ocr_stats, llm_stats,
                                  created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                j.get("job_id", "j1"),
                j.get("image_path", "/tmp/img.jpg"),
                j.get("status", "done"),
                j.get("ocr_result_json"),
                j.get("llm_result_json"),
                j.get("ocr_stats"),
                j.get("llm_stats"),
                j.get("created_at", time.time() - 10),
                j.get("updated_at", time.time()),
            ))

    conn.commit()
    conn.close()
    return db_path


# ============================================================================
# archive_to_excel 測試
# ============================================================================

class TestArchiveToExcel:
    """測試 Excel 匯出"""

    def test_export_empty_project(self, mock_project_repo):
        """空專案匯出空 Excel"""
        root = mock_project_repo._project_root.return_value
        _create_jobs_db(root, jobs=[])

        exporter = ExcelExporter(mock_project_repo)
        result_path = exporter.archive_to_excel("test_project")

        assert Path(result_path).exists()
        assert result_path.endswith(".xlsx")

    def test_export_with_jobs(self, mock_project_repo):
        """含有 jobs 的專案匯出"""
        root = mock_project_repo._project_root.return_value
        llm_json = json.dumps({
            "receipt_type": "electronic",
            "header": {"supplier": "Test Store", "date": "2025-01-01"},
            "items": [{"description": "Item A", "quantity": 1, "price": 100}],
            "summary": {"total": 100},
        }, ensure_ascii=False)

        _create_jobs_db(root, jobs=[{
            "job_id": "j1",
            "image_path": "/tmp/receipt1.jpg",
            "status": "done",
            "llm_result_json": llm_json,
            "ocr_stats": json.dumps({"total_time_s": 1.5}),
            "llm_stats": json.dumps([{"total_time_s": 2.3}]),
        }])

        exporter = ExcelExporter(mock_project_repo)
        result_path = exporter.archive_to_excel("test_project")

        assert Path(result_path).exists()

        # 驗證工作表名稱
        import pandas as pd
        xls = pd.ExcelFile(result_path)
        assert "主表" in xls.sheet_names
        assert "細項表" in xls.sheet_names

    def test_export_with_custom_name(self, mock_project_repo):
        """自訂匯出檔名"""
        root = mock_project_repo._project_root.return_value
        _create_jobs_db(root, jobs=[])

        exporter = ExcelExporter(mock_project_repo)
        result_path = exporter.archive_to_excel("test_project", excel_name="custom_name.xlsx")

        assert "custom_name.xlsx" in result_path

    def test_export_nonexistent_project(self, mock_project_repo):
        """專案不存在 → FileNotFoundError"""
        nonexistent = mock_project_repo._project_root.return_value / "ghost"
        mock_project_repo._project_root.return_value = nonexistent

        exporter = ExcelExporter(mock_project_repo)
        with pytest.raises(FileNotFoundError):
            exporter.archive_to_excel("ghost_project")

    def test_export_no_db(self, mock_project_repo):
        """專案存在但無 jobs.db → FileNotFoundError"""
        # root 目錄存在但沒有 jobs.db
        exporter = ExcelExporter(mock_project_repo)
        with pytest.raises(FileNotFoundError, match="jobs.db"):
            exporter.archive_to_excel("test_project")


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
        # 不應崩潰
        assert text is not None
