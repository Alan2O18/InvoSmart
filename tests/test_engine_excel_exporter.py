import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from backend.engine.excel_exporter import ExcelExporter


def test_generate_text_from_vlm_result_formats_markdown_summary():
    exporter = ExcelExporter(MagicMock())

    text = exporter._generate_text_from_vlm_result(
        {
            "header": {
                "supplier": "測試供應商",
                "invoice_id": "AB12345678",
                "date": "2026-03-09",
            },
            "items": [
                {"category": "文具", "name": "原子筆", "qty": 2, "price": 10, "total": 20}
            ],
            "summary": {"total": 20},
        }
    )

    assert "# 測試供應商" in text
    assert "發票號碼: AB12345678" in text
    assert "| 文具 | 10 | 2 | 20 | 原子筆 |" in text
    assert "**合計**: 20" in text


@pytest.mark.asyncio
async def test_archive_to_excel_raises_when_project_has_no_jobs(tmp_path):
    project_root = tmp_path / "proj1"
    project_root.mkdir()

    project_repo = MagicMock()
    project_repo._project_root.return_value = project_root
    project_repo.update_project_status = AsyncMock()

    exporter = ExcelExporter(project_repo)
    mock_job_repo = MagicMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=[])

    with patch("backend.engine.excel_exporter.JobRepository", return_value=mock_job_repo):
        with pytest.raises(FileNotFoundError, match="No jobs found"):
            await exporter.archive_to_excel("proj1")


@pytest.mark.asyncio
async def test_archive_to_excel_writes_main_and_detail_sheets(tmp_path):
    project_root = tmp_path / "proj1"
    project_root.mkdir()

    project_repo = MagicMock()
    project_repo._project_root.return_value = project_root
    project_repo.update_project_status = AsyncMock()

    exporter = ExcelExporter(project_repo)
    jobs_list = [
        {
            "image_path": str(project_root / "invoice-1.jpg"),
            "vlm_stats": json.dumps({"total_time_s": 1.5}),
            "created_at": 100.0,
            "updated_at": 102.5,
            "vlm_result_json": json.dumps(
                {
                    "header": {
                        "supplier": "供應商甲",
                        "invoice_id": "AB12345678",
                        "date": "2026-03-09",
                    },
                    "items": [
                        {
                            "category": "文具",
                            "name": "原子筆",
                            "qty": 2,
                            "price": 10,
                            "total": 20,
                        }
                    ],
                    "summary": {"total": 20},
                },
                ensure_ascii=False,
            ),
            "manual_json_text": "",
            "status": "done",
        }
    ]
    mock_job_repo = MagicMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=jobs_list)

    with patch("backend.engine.excel_exporter.JobRepository", return_value=mock_job_repo):
        out_path = await exporter.archive_to_excel("proj1", excel_name="report.xlsx")

    report_path = Path(out_path)
    assert report_path.exists()

    main_sheet = pd.read_excel(report_path, sheet_name="主表")
    detail_sheet = pd.read_excel(report_path, sheet_name="細項表")

    assert main_sheet.loc[0, "供應商"] == "供應商甲"
    assert main_sheet.loc[0, "金額"] == 20
    assert detail_sheet.loc[0, "品項名稱"] == "原子筆"
    assert detail_sheet.loc[0, "報帳名目"] == "文具"
    project_repo.update_project_status.assert_awaited_once_with("proj1", "ARCHIVED")
