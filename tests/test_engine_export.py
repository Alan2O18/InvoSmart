"""Unit tests for export facade handler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.engine.export import ExportHandler


@pytest.mark.asyncio
async def test_run_excel_delegates_to_excel_exporter():
    repo = MagicMock()
    handler = ExportHandler(repo)
    handler._excel_exporter.run_excel = AsyncMock(return_value={"status": "excel_exported"})

    result = await handler.run_excel("proj1")

    assert result["status"] == "excel_exported"
    handler._excel_exporter.run_excel.assert_awaited_once_with("proj1")


@pytest.mark.asyncio
async def test_archive_to_excel_delegates_with_custom_name():
    repo = MagicMock()
    handler = ExportHandler(repo)
    handler._excel_exporter.archive_to_excel = AsyncMock(return_value="out.xlsx")

    result = await handler.archive_to_excel("proj1", excel_name="named.xlsx")

    assert result == "out.xlsx"
    handler._excel_exporter.archive_to_excel.assert_awaited_once_with("proj1", "named.xlsx")


@pytest.mark.asyncio
async def test_run_word_requires_engine():
    repo = MagicMock()
    handler = ExportHandler(repo, engine=None)

    with pytest.raises(ValueError, match="Engine instance is required"):
        await handler.run_word("proj1", "template.docx")


@pytest.mark.asyncio
async def test_run_word_delegates_to_word_exporter():
    repo = MagicMock()
    engine = MagicMock()
    job_repo = MagicMock()
    engine.get_job_repo.return_value = job_repo

    handler = ExportHandler(repo, engine=engine)
    handler._word_exporter.process_export = MagicMock(return_value="report.docx")

    result = await handler.run_word("proj1", "template.docx")

    assert result == "report.docx"
    engine.get_job_repo.assert_called_once_with("proj1")
    handler._word_exporter.process_export.assert_called_once_with("proj1", "template.docx", job_repo)


@pytest.mark.asyncio
async def test_seal_project_delegates_to_archive_handler():
    repo = MagicMock()
    handler = ExportHandler(repo)
    handler._archive_handler.seal_project = AsyncMock(return_value={"success": True, "method": "zip"})

    result = await handler.seal_project("proj1", include_raw=False, debug=True)

    assert result["success"] is True
    handler._archive_handler.seal_project.assert_awaited_once_with("proj1", None, False, True)
