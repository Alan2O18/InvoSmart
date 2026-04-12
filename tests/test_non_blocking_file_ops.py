from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.engine.file_ops import FileOps


@pytest.mark.asyncio
async def test_add_project_files_non_image_copy_runs_in_to_thread(tmp_path):
    project_repo = MagicMock()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    project_repo._project_root.return_value = project_root
    project_repo.set_conversion_total = MagicMock()
    project_repo.inc_conversion_progress = MagicMock()

    engine_ref = MagicMock()
    engine_ref.config = {}
    engine_ref.enqueue_job = AsyncMock()
    engine_ref.get_job_repo = MagicMock(return_value=MagicMock(update_job=AsyncMock()))

    file_ops = FileOps(project_repo, receipt_splitter=MagicMock(), engine_ref=engine_ref)

    src = tmp_path / "note.txt"
    src.write_text("hello", encoding="utf-8")

    called_functions: list[str] = []

    async def fake_to_thread(fn, *args, **kwargs):
        called_functions.append(getattr(fn, "__name__", str(fn)))
        return fn(*args, **kwargs)

    with patch("backend.engine.file_ops.asyncio.to_thread", side_effect=fake_to_thread):
        result = await file_ops.add_project_files("proj1", [str(src)], type="raw")

    assert result["status"] == "added"
    assert (project_root / "原始輸入" / "note.txt").exists()
    assert any(name == "copy" for name in called_functions)
