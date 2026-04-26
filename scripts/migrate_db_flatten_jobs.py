"""Backfill persisted flattened job payloads for done jobs."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path

from backend.database import core as db_core
from backend.repositories.job_repository import JobRepository
from backend.repositories.project_repository import ProjectRepository
from backend.utils.config import load_config

logger = logging.getLogger("migrate_db_flatten_jobs")


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"processed": [], "updated_at": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed": [], "updated_at": 0}


def save_checkpoint(path: Path, processed: set[str]):
    payload = {"processed": sorted(processed), "updated_at": time.time()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_job_key(project_id: str, job_id: str) -> str:
    return f"{project_id}:{job_id}"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill persisted flattened_data for done jobs")
    parser.add_argument("--workspace-root", default=None, help="Override workspace root from config")
    parser.add_argument("--db-path", default=None, help="Override global DB path from config")
    parser.add_argument("--project-id", default=None, help="Only process a single project")
    parser.add_argument(
        "--checkpoint",
        default="scripts/.migrate_db_flatten_jobs.checkpoint.json",
        help="Checkpoint file path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB")
    parser.add_argument("--force", action="store_true", help="Rebuild even if flattened_data already exists")
    parser.add_argument("--resume", action="store_true", help="Skip jobs already recorded in checkpoint")
    parser.add_argument("--limit", type=int, default=0, help="Stop after processing N jobs")
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Checkpoint save interval",
    )
    parser.add_argument("--report-path", default=None, help="Write JSON summary report")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser


async def run_async(args: argparse.Namespace, session_factory=None) -> int:
    config = load_config()
    pm_settings = config.get("project_manager_settings", {})
    workspace_root = args.workspace_root or pm_settings.get("workspace_root", "workspace")

    if session_factory is None:
        db_path = Path(args.db_path).expanduser().resolve() if args.db_path else None
        await db_core.init_db(db_path)
        session_factory = db_core.AsyncSessionLocal

    project_repo = ProjectRepository(
        config={"workspace_root": workspace_root},
        session_factory=session_factory,
    )

    checkpoint_path = Path(args.checkpoint)
    checkpoint = load_checkpoint(checkpoint_path) if args.resume else {"processed": []}
    processed_keys = set(checkpoint.get("processed", []))

    projects = await project_repo.list_projects()
    if args.project_id:
        projects = [project for project in projects if project.get("project_id") == args.project_id]

    migrated = 0
    skipped = 0
    errors = 0
    processed = 0
    project_stats: dict[str, dict[str, int]] = {}
    failed_jobs: list[dict[str, str]] = []

    for project in projects:
        project_id = project.get("project_id")
        if not project_id:
            continue
        project_stats.setdefault(project_id, {"migrated": 0, "skipped": 0, "errors": 0, "processed": 0})
        job_repo = JobRepository(project_id, session_factory=session_factory)
        jobs = await job_repo.list_jobs(status="done")

        for job in jobs:
            if args.limit and processed >= args.limit:
                break

            job_id = job.get("job_id")
            if not job_id:
                skipped += 1
                project_stats[project_id]["skipped"] += 1
                continue

            checkpoint_key = build_job_key(project_id, job_id)
            if args.resume and checkpoint_key in processed_keys:
                skipped += 1
                project_stats[project_id]["skipped"] += 1
                continue

            try:
                current = await job_repo.get_job(job_id)
                if not current:
                    skipped += 1
                    project_stats[project_id]["skipped"] += 1
                    continue
                if not args.force and current.get("flattened_data") and current.get("flattening_status") == "done":
                    skipped += 1
                    project_stats[project_id]["skipped"] += 1
                else:
                    payload = await job_repo.refresh_flattened_data(
                        job_id,
                        force=args.force,
                        persist=not args.dry_run,
                    )
                    if payload is None:
                        skipped += 1
                        project_stats[project_id]["skipped"] += 1
                    else:
                        migrated += 1
                        project_stats[project_id]["migrated"] += 1

                processed += 1
                project_stats[project_id]["processed"] += 1
                processed_keys.add(checkpoint_key)
                if processed % max(args.checkpoint_interval, 1) == 0:
                    save_checkpoint(checkpoint_path, processed_keys)
            except Exception as exc:
                errors += 1
                processed += 1
                project_stats[project_id]["errors"] += 1
                project_stats[project_id]["processed"] += 1
                failed_jobs.append({"project_id": project_id, "job_id": job_id, "error": str(exc)})
                logger.exception("Failed to flatten %s/%s: %s", project_id, job_id, exc)

        if args.limit and processed >= args.limit:
            break

    save_checkpoint(checkpoint_path, processed_keys)

    summary = {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "processed": processed,
        "dry_run": args.dry_run,
        "timestamp": time.time(),
        "project_id": args.project_id,
        "force": args.force,
        "resume": args.resume,
        "checkpoint": str(checkpoint_path),
        "projects": project_stats,
        "failed_jobs": failed_jobs,
    }

    if args.report_path:
        Path(args.report_path).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return 1 if errors else 0


def run(args: argparse.Namespace, session_factory=None) -> int:
    return asyncio.run(run_async(args, session_factory=session_factory))


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
