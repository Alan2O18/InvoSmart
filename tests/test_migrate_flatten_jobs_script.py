"""Tests for scripts/migrate_db_flatten_jobs.py."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from backend.database.models import Project
from backend.repositories.job_repository import JobRepository


def _make_args(workspace_root: str, **overrides) -> argparse.Namespace:
    defaults = dict(
        workspace_root=workspace_root,
        db_path=None,
        project_id=None,
        checkpoint=str(Path(workspace_root) / ".flatten_checkpoint.json"),
        dry_run=False,
        force=False,
        resume=False,
        limit=0,
        checkpoint_interval=100,
        report_path=None,
        verbose=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.migrate_db_flatten_jobs import run_async  # noqa: E402


@pytest.mark.asyncio
async def test_run_backfills_done_jobs(async_session_factory, tmp_path):
    repo = JobRepository("proj1", session_factory=async_session_factory)
    async with async_session_factory() as session:
        session.add(Project(project_id="proj1", root_path=str(tmp_path / "proj1"), meta_data={"group": "教材費"}))
        await session.commit()

    await repo.insert_job("job1", "img.jpg", "ready")
    await repo.complete_vlm(
        "job1",
        {"header": {"voucher_id": "V001"}, "items": [{"category": "文具", "name": "筆", "total": 25}]},
    )
    await repo.update_job("job1", flattened_data=None, flattening_status=None, status="done")

    rc = await run_async(_make_args(str(tmp_path)), session_factory=async_session_factory)
    assert rc == 0

    job = await repo.get_job("job1")
    assert job["flattening_status"] == "done"
    payload = json.loads(job["flattened_data"])
    assert payload["projectGroup"] == "教材費"
    assert payload["items"][0]["name"] == "筆"


@pytest.mark.asyncio
async def test_run_dry_run_does_not_persist(async_session_factory, tmp_path):
    repo = JobRepository("proj2", session_factory=async_session_factory)
    async with async_session_factory() as session:
        session.add(Project(project_id="proj2", root_path=str(tmp_path / "proj2"), meta_data={"group": "雜支"}))
        await session.commit()

    await repo.insert_job("job2", "img.jpg", "done")
    await repo.update_job(
        "job2",
        vlm_result_json=json.dumps({"items": [{"name": "紙", "total": 12}]}, ensure_ascii=False),
        status="done",
    )

    report_path = tmp_path / "flatten_report.json"
    rc = await run_async(
        _make_args(str(tmp_path), dry_run=True, report_path=str(report_path)),
        session_factory=async_session_factory,
    )
    assert rc == 0

    job = await repo.get_job("job2")
    assert job["flattened_data"] is None
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["migrated"] == 1
    assert report["dry_run"] is True


@pytest.mark.asyncio
async def test_run_resume_skips_checkpointed_job(async_session_factory, tmp_path):
    repo = JobRepository("proj3", session_factory=async_session_factory)
    async with async_session_factory() as session:
        session.add(Project(project_id="proj3", root_path=str(tmp_path / "proj3"), meta_data={"group": "雜支"}))
        await session.commit()

    await repo.insert_job("job3", "img.jpg", "done")
    await repo.update_job(
        "job3",
        vlm_result_json=json.dumps({"items": [{"name": "紙", "total": 12}]}, ensure_ascii=False),
        status="done",
    )

    checkpoint_path = tmp_path / ".flatten_checkpoint.json"
    checkpoint_path.write_text(
        json.dumps({"processed": ["proj3:job3"], "updated_at": 0}, ensure_ascii=False),
        encoding="utf-8",
    )

    rc = await run_async(
        _make_args(str(tmp_path), resume=True, checkpoint=str(checkpoint_path)),
        session_factory=async_session_factory,
    )

    assert rc == 0
    job = await repo.get_job("job3")
    assert job["flattened_data"] is None


@pytest.mark.asyncio
async def test_run_writes_checkpoint_entries(async_session_factory, tmp_path):
    repo = JobRepository("proj4", session_factory=async_session_factory)
    async with async_session_factory() as session:
        session.add(Project(project_id="proj4", root_path=str(tmp_path / "proj4"), meta_data={"group": "教材費"}))
        await session.commit()

    await repo.insert_job("job4", "img.jpg", "done")
    await repo.update_job(
        "job4",
        vlm_result_json=json.dumps({"items": [{"name": "筆", "total": 20}]}, ensure_ascii=False),
        status="done",
    )

    checkpoint_path = tmp_path / ".flatten_checkpoint.json"
    rc = await run_async(
        _make_args(str(tmp_path), checkpoint=str(checkpoint_path), checkpoint_interval=1),
        session_factory=async_session_factory,
    )

    assert rc == 0
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert "proj4:job4" in checkpoint["processed"]