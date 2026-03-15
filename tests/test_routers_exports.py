"""Tests for backend/routers/exports.py — Excel, Word, and Archive endpoints."""
import pathlib
from unittest.mock import AsyncMock, patch


def test_run_excel(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_excel = AsyncMock(return_value={"status": "excel generated"})
    response = mock_app_client.post("/api/projects/proj1/run_export")
    assert response.status_code == 200
    assert response.json() == {"status": "excel generated"}


def test_run_excel_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.run_excel = AsyncMock(side_effect=Exception("Export failed"))
    response = mock_app_client.post("/api/projects/proj1/run_export")
    assert response.status_code == 500


def test_archive_project(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.archive_project = AsyncMock(return_value={"status": "archived"})
    response = mock_app_client.post("/api/projects/proj1/run_archive")
    assert response.status_code == 200
    assert response.json() == {"status": "archived"}


def test_archive_project_error(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.archive_project = AsyncMock(side_effect=Exception("Archive failed"))
    response = mock_app_client.post("/api/projects/proj1/run_archive")
    assert response.status_code == 500


def test_run_word_export_success(mock_app_client, mock_engine_for_api):
    mock_export_handler = AsyncMock()
    mock_export_handler.run_word = AsyncMock(return_value="fake_path.docx")
    mock_engine_for_api.export_handler = mock_export_handler

    with patch("backend.routers.exports.pathlib.Path.exists", return_value=True), \
         patch("backend.routers.exports.os.path.exists", return_value=True), \
         patch("backend.routers.exports.FileResponse", return_value={"status": "word generated"}):
        response = mock_app_client.post("/api/projects/proj1/run_word_export")
        assert response.status_code == 200
        mock_export_handler.run_word.assert_called_once()


def test_run_word_export_template_not_found(mock_app_client, mock_engine_for_api):
    """Word export fails when template file is absent."""
    with patch("backend.routers.exports.pathlib.Path.exists", return_value=False):
        response = mock_app_client.post("/api/projects/proj1/run_word_export")
        assert response.status_code == 500


def test_run_word_export_output_not_found(mock_app_client, mock_engine_for_api):
    """Word export fails when generated output file is absent."""
    mock_export_handler = AsyncMock()
    mock_export_handler.run_word = AsyncMock(return_value="nonexistent.docx")
    mock_engine_for_api.export_handler = mock_export_handler

    with patch("backend.routers.exports.pathlib.Path.exists", return_value=True), \
         patch("backend.routers.exports.os.path.exists", return_value=False):
        response = mock_app_client.post("/api/projects/proj1/run_word_export")
        assert response.status_code == 500


def test_word_template_path_uses_assets_not_dev_data():
    """exports.py must point at backend/assets/templates, not dev_data."""
    import backend.routers.exports as exports_mod
    resolved = str(exports_mod._ASSETS_TEMPLATES)
    assert "dev_data" not in resolved
    assert "assets" in resolved and "templates" in resolved
