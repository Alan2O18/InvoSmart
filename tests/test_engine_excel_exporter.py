import json
import os
import re
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
    project_repo.get_project = AsyncMock(return_value={"project_id": "proj1", "name": "測試專案"})

    exporter = ExcelExporter(project_repo)

    base_jobs = [{"job_id": "job-1"}]
    job_row = {
        "job_id": "job-1",
        "image_path": str(project_root / "invoice-1.jpg"),
        "vlm_stats": json.dumps({"total_time_s": 1.5}),
        "created_at": 100.0,
        "updated_at": 102.5,
        "vlm_result_json": json.dumps({"header": {}, "items": [], "summary": {}}, ensure_ascii=False),
        "status": "done",
        "supplier": "供應商甲",
        "total_amount": 20,
        "invoice_date": "2026-03-09",
        "voucher_id": "AB12345678",
    }
    display_result = {
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
    }

    mock_job_repo = MagicMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=base_jobs)
    mock_job_repo.get_job = AsyncMock(return_value=job_row)
    mock_job_repo.get_display_result = AsyncMock(return_value=display_result)

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


@pytest.mark.asyncio
async def test_archive_to_excel_uses_v18_filename_convention(tmp_path):
    project_root = tmp_path / "proj1"
    project_root.mkdir()

    project_repo = MagicMock()
    project_repo._project_root.return_value = project_root
    project_repo.update_project_status = AsyncMock()
    project_repo.get_project = AsyncMock(return_value={"project_id": "proj1", "name": "成果/發表:測試?*"})

    exporter = ExcelExporter(project_repo)

    mock_job_repo = MagicMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "job-1"}])
    mock_job_repo.get_job = AsyncMock(
        return_value={
            "job_id": "job-1",
            "image_path": str(project_root / "invoice-1.jpg"),
            "vlm_stats": None,
            "created_at": 10.0,
            "updated_at": 20.0,
            "vlm_result_json": json.dumps({"header": {}, "items": [], "summary": {}}, ensure_ascii=False),
            "status": "done",
            "supplier": "",
            "total_amount": "",
            "invoice_date": "",
            "voucher_id": "",
        }
    )
    mock_job_repo.get_display_result = AsyncMock(return_value={"header": {}, "items": [], "summary": {}})

    with patch("backend.engine.excel_exporter.JobRepository", return_value=mock_job_repo):
        out_path = await exporter.archive_to_excel("proj1")

    out_name = os.path.basename(out_path)
    assert re.match(r"^proj1「成果_發表_測試__」_預結算表_\d{8}_\d{6}\.xlsx$", out_name)
