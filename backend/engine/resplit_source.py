from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional


def derive_raw_stem_from_split_filename(filename: str) -> str:
    stem = Path(filename).stem
    for marker in ("_split_manual_", "_resplit_", "_split_"):
        if marker in stem:
            return stem.split(marker, 1)[0]
    return stem


def resolve_resplit_raw_source(
    root: Path,
    job: dict[str, Any],
    resolve_project_path: Callable[[Path, Optional[str], Optional[str]], Optional[Path]],
    logger: logging.Logger | None = None,
) -> Optional[Path]:
    raw_dir = root / "原始輸入"
    job_path = str(job.get("image_path") or "")
    split_source = resolve_project_path(root, job_path, "分割發票")

    name_hint = Path(job_path).name or (split_source.name if split_source else "")
    raw_stem = derive_raw_stem_from_split_filename(name_hint)
    if raw_dir.exists() and raw_stem:
        candidates = [item for item in raw_dir.iterdir() if item.is_file() and item.stem == raw_stem]
        if candidates:
            candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            return candidates[0].resolve(strict=False)

    explicit_raw = resolve_project_path(root, job.get("raw_image_path"), "原始輸入")
    if explicit_raw is not None and explicit_raw.exists():
        return explicit_raw

    if split_source is not None and split_source.exists():
        if logger is not None:
            logger.warning(
                "[FileOps] RAW source not found for job=%s, fallback to split image=%s",
                job.get("job_id"),
                split_source,
            )
        return split_source

    return None


def resolve_raw_source_by_filename(root: Path, filename: str) -> Optional[Path]:
    raw_dir = root / "原始輸入"
    if not raw_dir.exists():
        return None

    token = Path(str(filename)).name
    direct = raw_dir / token
    if direct.exists() and direct.is_file():
        return direct.resolve(strict=False)

    token_stem = Path(token).stem
    candidates = [
        item
        for item in raw_dir.iterdir()
        if item.is_file() and (item.name == token or item.stem == token or item.stem == token_stem)
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0].resolve(strict=False)


def job_matches_raw_filename(job: dict[str, Any], raw_filename: str) -> bool:
    raw_stem = Path(str(raw_filename)).stem
    job_name = Path(str(job.get("image_path") or "")).name
    if not raw_stem or not job_name:
        return False
    return derive_raw_stem_from_split_filename(job_name) == raw_stem
