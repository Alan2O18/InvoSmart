import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.engine.regeneration_handler import RegenerationHandler

@pytest.fixture
def mock_project_repo():
    repo = MagicMock()
    repo._project_root.return_value = MagicMock()
    return repo

@pytest.fixture
def mock_excel_exporter():
    exporter = AsyncMock()
    exporter.archive_to_excel = AsyncMock(return_value="new_archive.xlsx")
    return exporter

@pytest.fixture
def regeneration_handler(mock_project_repo, mock_excel_exporter):
    return RegenerationHandler(mock_project_repo, mock_excel_exporter)

@pytest.mark.asyncio
@patch('backend.engine.regeneration_handler.openpyxl.load_workbook')
async def test_regenerate_missing_column(mock_load_workbook, regeneration_handler):
    wb = MagicMock()
    wb.sheetnames = ["主表"]
    ws = MagicMock()
    ws.iter_rows.return_value = iter([
        ("檔名",),
        ("file1.jpg",)
    ])
    wb.__getitem__.return_value = ws
    mock_load_workbook.return_value = wb
    
    result = await regeneration_handler.regenerate_from_archive("proj1", "fake.xlsx", {})
    assert result is None

@pytest.mark.asyncio
@patch('backend.engine.regeneration_handler.openpyxl.load_workbook')
async def test_regenerate_read_error(mock_load_workbook, regeneration_handler):
    mock_load_workbook.side_effect = Exception("Excel format error")
    
    result = await regeneration_handler.regenerate_from_archive("proj1", "fake.xlsx", {})
    assert result is None

@pytest.mark.asyncio
@patch('backend.engine.regeneration_handler.openpyxl.load_workbook')
@patch('backend.processing.llm_handler.LLMHandler')
@patch('backend.repositories.job_repository.JobRepository')
async def test_regenerate_success(mock_job_repo_class, mock_llm_handler_class, mock_load_workbook, regeneration_handler):
    # Mock workbook with valid rows
    wb = MagicMock()
    wb.sheetnames = ["主表"]
    ws = MagicMock()
    ws.iter_rows.return_value = iter([
        ("檔名", "人工修正"),
        ("file1.jpg", "corrected1"),
        ("file2.jpg", None)
    ])
    wb.__getitem__.return_value = ws
    mock_load_workbook.return_value = wb
    
    # Mock inner LLMHandler behavior
    mock_llm_handler = MagicMock()
    mock_llm_handler.regenerate_from_corrected_text.return_value = {
        "receipt_type": "receipt",
        "header": {"buyer": "TEST"},
        "items": [],
        "summary": {}
    }
    mock_llm_handler_class.return_value = mock_llm_handler
    
    # Mock JobRepository
    mock_job_repo = AsyncMock()
    mock_job_repo.list_jobs.return_value = [
        {"job_id": "j1", "image_path": "path/to/file1.jpg"},
        {"job_id": "j2", "image_path": "path/to/other.jpg"}
    ]
    mock_job_repo.update_job = AsyncMock()
    mock_job_repo_class.return_value = mock_job_repo
    
    result = await regeneration_handler.regenerate_from_archive("proj1", "fake.xlsx", {})
    
    # Assertions
    assert result == "new_archive.xlsx"
    mock_llm_handler.regenerate_from_corrected_text.assert_called_once_with("corrected1")
    # Only job j1 should match correctly and invoke update_job
    mock_job_repo.update_job.assert_called_once()
    args, kwargs = mock_job_repo.update_job.call_args
    assert args[0] == "j1"
    assert kwargs["status"] == "human_correct"
    assert "TEST" in kwargs["vlm_result_json"]

@pytest.mark.asyncio
@patch('backend.engine.regeneration_handler.openpyxl.load_workbook')
@patch('backend.processing.llm_handler.LLMHandler')
@patch('backend.repositories.job_repository.JobRepository')
async def test_regenerate_job_mismatch(mock_job_repo_class, mock_llm_handler_class, mock_load_workbook, regeneration_handler):
    wb = MagicMock()
    wb.sheetnames = ["主表"]
    ws = MagicMock()
    ws.iter_rows.return_value = iter([
        ("檔名", "人工修正"),
        ("unmatched.jpg", "corrected")
    ])
    wb.__getitem__.return_value = ws
    mock_load_workbook.return_value = wb
    
    mock_llm_handler_class.return_value = MagicMock()
    
    mock_job_repo = AsyncMock()
    mock_job_repo.list_jobs.return_value = [
        {"job_id": "j1", "image_path": "path/to/file1.jpg"}
    ]
    mock_job_repo_class.return_value = mock_job_repo
    
    result = await regeneration_handler.regenerate_from_archive("proj1", "fake.xlsx", {})
    
    assert result == "new_archive.xlsx" # Re-archiving still happens
    mock_job_repo.update_job.assert_not_called()
