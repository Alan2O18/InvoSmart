from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

from PIL import Image

from backend.utils.utils import cv_imread_chinese
from backend.processing.jxl_encoder_backend import encode_image_to_jxl, is_jxl_available

logger = logging.getLogger("migrate_images_to_jxl_avif")

SUPPORTED_INPUT_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def configure_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(message)s")


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


def build_preview_path(project_root: Path, source: Path, max_width: int, ext: str) -> Path:
    stat = source.stat()
    sig = f"{stat.st_mtime_ns}_{stat.st_size}_{max_width}"
    cache_dir = project_root / "快取影像" / "voucher_preview"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{source.stem}_{sig}.{ext}"


def generate_preview(source: Path, preview_path: Path, max_width: int, fmt: str):
    with Image.open(source) as image:
        image = image.convert("RGB")
        if image.width > max_width:
            new_height = int((max_width / image.width) * image.height)
            image = image.resize((max_width, max(1, new_height)), Image.Resampling.LANCZOS)

        if fmt.upper() == "WEBP":
            image.save(preview_path, format="WEBP", quality=85)
        elif fmt.upper() == "AVIF":
            image.save(preview_path, format="AVIF", quality=60)
        else:
            image.save(preview_path, format="JPEG", quality=90)


def iter_project_images(workspace_root: Path):
    for project_root in workspace_root.iterdir():
        if not project_root.is_dir():
            continue
        for sub in ("原始輸入", "分割發票"):
            data_dir = project_root / sub
            if not data_dir.exists():
                continue
            for source in data_dir.rglob("*"):
                if not source.is_file():
                    continue
                if source.suffix.lower() in SUPPORTED_INPUT_EXTS:
                    yield project_root, source


def run(args) -> int:
    workspace_root = Path(args.workspace_root)
    if not workspace_root.exists():
        logger.error("Workspace root does not exist: %s", workspace_root)
        return 2

    checkpoint_path = Path(args.checkpoint)
    checkpoint = load_checkpoint(checkpoint_path)
    processed = set(checkpoint.get("processed", []))

    preview_fmt = args.preview_format.lower()
    if preview_fmt not in ("avif", "webp", "jpeg"):
        logger.error("Unsupported preview format: %s", preview_fmt)
        return 2

    archival_format = args.archival_format.lower()
    jxl_enabled = archival_format == "jxl" and is_jxl_available()
    if archival_format == "jxl" and not jxl_enabled:
        logger.warning(
            "JXL archival requested but encoder is unavailable; keeping original files as archival source"
        )

    canary_limit: int = getattr(args, "canary_limit", 0)
    report_path_str: str | None = getattr(args, "report_path", None)

    migrated = 0
    skipped = 0
    errors = 0
    # Track newly generated files so caller can roll back if needed.
    new_files: list[str] = []

    rollback_path = checkpoint_path.with_suffix(".rollback.json")

    for project_root, source in iter_project_images(workspace_root):
        # Canary-limit: stop after processing N images.
        if canary_limit > 0 and migrated >= canary_limit:
            logger.info("Canary limit reached (%d); stopping early.", canary_limit)
            break

        key = str(source.resolve())
        if args.resume and key in processed:
            skipped += 1
            continue

        preview_path = build_preview_path(project_root, source, args.preview_max_width, preview_fmt)

        if args.dry_run:
            logger.info("[DRY-RUN] preview %s -> %s", source, preview_path)
            if archival_format == "jxl":
                logger.info("[DRY-RUN] archival target would be %s", source.with_suffix(".jxl"))
        else:
            try:
                if not preview_path.exists():
                    generate_preview(source, preview_path, args.preview_max_width, preview_fmt)
                    new_files.append(str(preview_path.resolve()))
                if archival_format == "jxl" and jxl_enabled:
                    jxl_path = source.with_suffix(".jxl")
                    if not jxl_path.exists():
                        img_arr = cv_imread_chinese(str(source))
                        if img_arr is not None:
                            jxl_bytes = encode_image_to_jxl(img_arr)
                            jxl_path.write_bytes(jxl_bytes)
                            new_files.append(str(jxl_path.resolve()))
            except Exception as exc:
                logger.error("Failed to process %s: %s", source, exc)
                errors += 1
                continue

        processed.add(key)
        migrated += 1
        if migrated % args.checkpoint_interval == 0:
            save_checkpoint(checkpoint_path, processed)
            _write_rollback(rollback_path, new_files)

    save_checkpoint(checkpoint_path, processed)
    _write_rollback(rollback_path, new_files)

    logger.info(
        "Migration done. migrated=%s skipped=%s errors=%s dry_run=%s",
        migrated,
        skipped,
        errors,
        args.dry_run,
    )

    if report_path_str:
        _write_report(
            Path(report_path_str),
            migrated=migrated,
            skipped=skipped,
            errors=errors,
            dry_run=args.dry_run,
            canary_limit=canary_limit,
            new_files=new_files,
        )

    return 0 if errors == 0 else 1


def _write_rollback(path: Path, new_files: list[str]):
    """Persist newly created files for rollback support."""
    payload = {"generated_files": new_files, "updated_at": time.time()}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write rollback list to %s: %s", path, exc)


def _write_report(
    path: Path,
    *,
    migrated: int,
    skipped: int,
    errors: int,
    dry_run: bool,
    canary_limit: int,
    new_files: list[str],
):
    """Write structured JSON summary report."""
    payload = {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
        "canary_limit": canary_limit,
        "new_files_count": len(new_files),
        "timestamp": time.time(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Report written to %s", path)
    except Exception as exc:
        logger.warning("Could not write report to %s: %s", path, exc)


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate historical receipt images to preview cache and planned JXL targets")
    parser.add_argument(
        "--workspace-root",
        default="backend/data/projects",
        help="Projects root directory",
    )
    parser.add_argument(
        "--checkpoint",
        default="scripts/.migrate_images_to_jxl_avif.checkpoint.json",
        help="Checkpoint file path",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    parser.add_argument("--resume", action="store_true", help="Skip files already in checkpoint")
    parser.add_argument("--archival-format", default="jxl", choices=["jxl", "jpg"], help="Target archival format")
    parser.add_argument("--preview-format", default="webp", choices=["avif", "webp", "jpeg"], help="Preview format")
    parser.add_argument("--preview-max-width", type=int, default=800, help="Preview max width")
    parser.add_argument("--checkpoint-interval", type=int, default=100, help="Checkpoint save interval")
    parser.add_argument(
        "--canary-limit",
        type=int,
        default=0,
        metavar="N",
        help="Stop after processing N images (0 = unlimited)",
    )
    parser.add_argument(
        "--report-path",
        default=None,
        metavar="FILE",
        help="Write a JSON summary report to this path after the run",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    configure_logging(cli_args.verbose)
    raise SystemExit(run(cli_args))
