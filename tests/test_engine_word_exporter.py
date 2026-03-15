import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from docx import Document
from backend.engine.word_exporter import WordExporter

@pytest.fixture
def word_exporter():
    # Provide a simple mock for the project repository
    project_repo_mock = MagicMock()
    return WordExporter(project_repo_mock)

def test_replace_text_in_paragraph(word_exporter):
    doc = Document()
    p = doc.add_paragraph("This is a {{test_key}} paragraph.")
    
    replacements = {"{{test_key}}": "successful"}
    word_exporter._replace_text_in_paragraph(p, replacements, mark_unfilled_red=False)
    
    assert "successful" in p.text
    assert "{{test_key}}" not in p.text

def test_replace_text_hardcoded_coordinator(word_exporter):
    doc = Document()
    p = doc.add_paragraph("負責人是 活動總務：李天旭 先生")
    
    replacements = {"{{活動總務}}": "王小明"}
    word_exporter._replace_text_in_paragraph(p, replacements, mark_unfilled_red=False)
    
    assert "活動總務：王小明" in p.text
    assert "李天旭" not in p.text

def test_highlight_unfilled_placeholders(word_exporter):
    doc = Document()
    p = doc.add_paragraph("Missing {{data_key}} here.")
    
    # mark_unfilled_red=True triggers _highlight_unfilled_placeholders 
    # if a {{ tag still remains in the text string
    word_exporter._replace_text_in_paragraph(p, {}, mark_unfilled_red=True)
    
    # Because _highlight_unfilled_placeholders clears p.text and rebuilds custom Runs with colors
    # We investigate the actual runs generated
    assert len(p.runs) > 1
    # Check if the red RGB color is applied to the placeholder run
    red_found = False
    from docx.shared import RGBColor
    for r in p.runs:
        if "{{data_key}}" in r.text and r.font.color and r.font.color.rgb == RGBColor(255, 0, 0):
            red_found = True
            break
            
    assert red_found

def test_replace_text_in_table(word_exporter):
    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    cell.text = "Data: {{val}}"
    
    word_exporter._replace_text_in_table(table, {"{{val}}": "100"})
    
    assert "100" in cell.text

def test_find_row_with_placeholder(word_exporter):
    doc = Document()
    table = doc.add_table(rows=2, cols=1)
    table.cell(0, 0).text = "Row 1 text"
    table.cell(1, 0).text = "Placeholder {{TARGET}}"
    
    row_idx = word_exporter._find_row_with_placeholder(table, "{{TARGET}}")
    assert row_idx == 1

def test_find_row_with_placeholder_not_found(word_exporter):
    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "No target here"
    
    res = word_exporter._find_row_with_placeholder(table, "{{TARGET}}")
    assert res == -1

def test_set_cell_text_formatted(word_exporter):
    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    
    word_exporter._set_cell_text_formatted(cell, "Formatted Text")
    assert cell.text == "Formatted Text"
    
def test_format_roc_date(word_exporter):
    assert word_exporter._format_roc_date("2024-05-12") == "113年5月12日"
    assert word_exporter._format_roc_date("invalid_date") == "invalid_date"

@pytest.mark.asyncio
async def test_process_export(word_exporter, tmp_path):
    import json
    import os
    
    # 1. Setup mock repos
    job_repo = AsyncMock()
    
    mock_jobs = [
        {
            "job_id": "job1",
            "vlm_result_json": json.dumps({
                "header": {"voucher_id": "V1", "date": "2024-05-12", "seller_name": "TestStore1", "buyer_name": "NKNU", "tax_type": "", "invoice_number": "AB12345678", "total_amount": 100},
                "items": [{"category": "文具", "name": "Item A", "qty": 2, "price": 50, "total": 100, "remark": "R1"}]
            })
        },
        {
            "job_id": "job2",
            "vlm_result_json": json.dumps({
                "header": {"voucher_id": "V2", "date": "2024-05-13", "seller_name": "TestStore2", "buyer_name": "NKNU", "tax_type": "", "invoice_number": "CD12345678", "total_amount": 200},
                "items": [{"category": "文具", "name": "Item B", "qty": 2, "price": 100, "total": 200, "remark": "R2"}]
            })
        }
    ]
    job_repo.list_jobs.return_value = mock_jobs
    job_repo.get_job = AsyncMock(side_effect=[None, None])
    job_repo.refresh_flattened_data = AsyncMock(return_value=None)
    job_repo.get_display_result = AsyncMock(side_effect=[
        json.loads(mock_jobs[0]["vlm_result_json"]),
        json.loads(mock_jobs[1]["vlm_result_json"]),
    ])
    
    word_exporter.project_repo = AsyncMock()
    word_exporter.project_repo.get_project.return_value = {
        "metadata": {
            "name": "Test Activity",
            "coordinator": "Test Coord",
            "budgetAmount": "1000", 
            "subsidyAmount": "500",
            "budgetIncome": [{"amount": "500", "item": "Registration"}],
            "budgetExpense": [{"total": "200", "item": "Food"}, {"total": "300", "item": "Prizes"}]
        },
        "root_path": str(tmp_path)
    }
    
    # Needs a mock _project_root returning Path
    from unittest.mock import MagicMock
    word_exporter.project_repo._project_root = MagicMock(return_value=tmp_path)
    
    # 2. Setup Template
    template_path = tmp_path / "template.docx"
    doc = Document()
    doc.add_paragraph("Activity: {{活動名稱}}")
    doc.add_paragraph("Coord: {{活動總召}}")
    doc.add_paragraph("Date Start: {{startDate}}")
    doc.add_paragraph("Budget: {{預算總額}}")
    
    # Add an Expense budget table
    table = doc.add_table(rows=1, cols=4)
    table.cell(0, 0).text = "{{BUDGET_EXPENSE_TABLE_START}}"
    doc.save(str(template_path))
    
    # 3. Export
    out_path = await word_exporter.process_export("proj_123", str(template_path), job_repo)
    
    # 4. Verify
    assert os.path.exists(out_path)
    res_doc = Document(out_path)
    full_text = "\\n".join(p.text for p in res_doc.paragraphs)
    
    assert "Activity: Test Activity" in full_text
    assert "Coord: Test Coord" in full_text
    assert "Budget: 500" in full_text


@pytest.mark.asyncio
async def test_ensure_flatten_cache_prefers_persisted_payload(tmp_path):
    project_repo = AsyncMock()
    project_repo.get_project.return_value = {"metadata": {"group": "教材費"}}
    project_repo._project_root = MagicMock(return_value=tmp_path)
    exporter = WordExporter(project_repo)

    persisted_payload = {
        "version": 1,
        "jobId": "job1",
        "categories": ["文具"],
        "items": [{"category": "文具", "name": "筆", "qty": 1, "price": 25, "total": 25, "voucher_id": "V1"}],
        "sumTotal": 25,
    }

    job_repo = AsyncMock()
    job_repo.project_id = "proj_persisted"
    job_repo.list_jobs.return_value = [{"job_id": "job1", "updated_at": 10}]
    job_repo.get_job.return_value = {
        "job_id": "job1",
        "flattening_status": "done",
        "flattened_data": json.dumps(persisted_payload, ensure_ascii=False),
    }
    job_repo.refresh_flattened_data = AsyncMock()
    job_repo.get_display_result = AsyncMock()

    payload = await exporter.ensure_flatten_cache("proj_persisted", job_repo)

    assert payload["sumTotal"] == 25
    assert payload["payloadSources"]["persisted"] == 1
    job_repo.refresh_flattened_data.assert_not_awaited()
    job_repo.get_display_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_flatten_cache_refreshes_missing_payload(tmp_path):
    project_repo = AsyncMock()
    project_repo.get_project.return_value = {"metadata": {"group": "教材費"}}
    project_repo._project_root = MagicMock(return_value=tmp_path)
    exporter = WordExporter(project_repo)

    job_repo = AsyncMock()
    job_repo.project_id = "proj_refresh"
    job_repo.list_jobs.return_value = [{"job_id": "job1", "updated_at": 20}]
    job_repo.get_job.return_value = {"job_id": "job1", "flattening_status": None, "flattened_data": None}
    job_repo.refresh_flattened_data = AsyncMock(return_value={
        "version": 1,
        "jobId": "job1",
        "categories": ["文具"],
        "items": [{"category": "文具", "name": "紙", "qty": 1, "price": 12, "total": 12, "voucher_id": "V2"}],
        "sumTotal": 12,
    })
    job_repo.get_display_result = AsyncMock()

    payload = await exporter.ensure_flatten_cache("proj_refresh", job_repo)

    assert payload["sumTotal"] == 12
    assert payload["payloadSources"]["refreshed"] == 1
    job_repo.refresh_flattened_data.assert_awaited_once_with("job1", persist=True)

@pytest.mark.asyncio
async def test_process_export_no_project(word_exporter):
    from unittest.mock import AsyncMock
    word_exporter.project_repo = AsyncMock()
    word_exporter.project_repo.get_project.return_value = None
    
    with pytest.raises(ValueError, match="Project not found: 123"):
        await word_exporter.process_export("123", "dummy", AsyncMock())
