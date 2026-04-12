from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.engine.file_ops import FileOps


@pytest.mark.asyncio
async def test_deferred_gc_only_deletes_when_unreferenced(tmp_path):
    project_repo = MagicMock()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    project_repo._project_root.return_value = project_root

    engine_ref = MagicMock()
    engine_ref.config = {}

    job_repo = MagicMock()
    job_repo.get_job = AsyncMock()
    job_repo.list_jobs = AsyncMock()
    engine_ref.get_job_repo = MagicMock(return_value=job_repo)

    file_ops = FileOps(project_repo, receipt_splitter=MagicMock(), engine_ref=engine_ref)

    shared = project_root / "分割發票" / "shared.jpg"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_bytes(b"img")

    job_repo.get_job.return_value = {
        "job_id": "job-1",
        "image_path": str(shared),
        "source_pdf_path": None,
        "compressed_pdf_path": None,
        "preview_cache_path": None,
    }
    job_repo.list_jobs.return_value = [
        {"job_id": "job-1", "image_path": str(shared)},
        {"job_id": "job-2", "image_path": str(shared)},
    ]

    stage1 = await file_ops.delete_job_files("proj1", "job-1")
    assert stage1["deferred_files"]
    assert shared.exists()

    stage2 = await file_ops.flush_deferred_gc("proj1")
    assert stage2["kept_referenced"]
    assert shared.exists()

    job_repo.list_jobs.return_value = []
    stage3 = await file_ops.flush_deferred_gc("proj1")
    assert stage3["deleted_files"]
    assert not shared.exists()
