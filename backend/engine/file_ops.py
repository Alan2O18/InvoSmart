import os
import time
import shutil
import logging
import asyncio
import uuid
from collections import Counter
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Any
from PIL import Image, features
from backend.processing.image_codec_adapter import ImageCodecAdapter
from backend.processing.perspective_transform import order_points, fix_orientation
from backend.utils import utils

logger = logging.getLogger(__name__)


class FileOps:
    def __init__(self, project_repo, receipt_splitter, engine_ref):
        self.project_repo = project_repo
        self.receipt_splitter = receipt_splitter
        self.engine = engine_ref

    def _engine_config(self) -> dict:
        config = getattr(self.engine, "config", {})
        return config if isinstance(config, dict) else {}

    def _thumb_max_width(self) -> int:
        config = self._engine_config()
        return int(config.get("voucher_settings", {}).get("thumb_max_width", 800))

    def _image_semaphore(self):
        semaphore = getattr(self.engine, "image_processing_semaphore", None)
        return semaphore if isinstance(semaphore, asyncio.Semaphore) else None

    def _codec_adapter(self) -> ImageCodecAdapter:
        settings = self._engine_config().get("processing_settings", {})
        return ImageCodecAdapter(settings)

    def _resolve_project_path(self, root: Path, raw_path: Optional[str], preferred_dir: Optional[str] = None) -> Optional[Path]:
        if not raw_path:
            return None

        path = Path(str(raw_path))
        candidates: list[Path] = []
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.append(root / path)
            if preferred_dir:
                candidates.append(root / preferred_dir / path.name)

        for candidate in candidates:
            resolved = candidate.resolve(strict=False)
            if resolved.exists():
                return resolved

        if candidates:
            return candidates[0].resolve(strict=False)
        return None

    @staticmethod
    def _is_within_root(root: Path, target: Path) -> bool:
        try:
            target.resolve(strict=False).relative_to(root.resolve(strict=False))
            return True
        except Exception:
            return False

    def _safe_delete_file(self, root: Path, target: Optional[Path], deleted_files: list[str], missing_files: list[str]):
        if target is None:
            return
        resolved = target.resolve(strict=False)
        if not self._is_within_root(root, resolved):
            logger.warning(f"[FileOps] skip deleting path outside project root: {resolved}")
            return
        if resolved.exists() and resolved.is_file():
            resolved.unlink()
            deleted_files.append(str(resolved))
        else:
            missing_files.append(str(resolved))

    @staticmethod
    def _warp_by_points(image: np.ndarray, points: np.ndarray) -> np.ndarray:
        ordered = order_points(points.astype("float32"))

        width_a = np.linalg.norm(ordered[2] - ordered[3])
        width_b = np.linalg.norm(ordered[1] - ordered[0])
        height_a = np.linalg.norm(ordered[1] - ordered[2])
        height_b = np.linalg.norm(ordered[0] - ordered[3])

        dst_w = max(1, int(round(max(width_a, width_b))))
        dst_h = max(1, int(round(max(height_a, height_b))))

        if dst_w > dst_h:
            src_pts = np.array([ordered[1], ordered[2], ordered[3], ordered[0]], dtype="float32")
            dst_w, dst_h = dst_h, dst_w
        else:
            src_pts = ordered

        dst_pts = np.array(
            [
                [0, 0],
                [dst_w, 0],
                [dst_w, dst_h],
                [0, dst_h],
            ],
            dtype="float32",
        )

        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        return cv2.warpPerspective(
            image,
            matrix,
            (dst_w, dst_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    async def run_splitting(self, project_id: str, target_files: Optional[list[str]] = None):
        try:
            logger.info(f"[FileOps] run_splitting started for {project_id}, target_files={target_files}")
            root = self.project_repo._project_root(project_id)

            await self._prepare_tasks(root, project_id, target_files=target_files)

            await self.project_repo.update_project_status(project_id, "SPLIT")
            logger.info(f"[FileOps] run_splitting completed for {project_id}")
            return {"status": "split_completed"}
        except Exception as e:
            logger.error(f"[FileOps] Error splitting for {project_id}: {e}", exc_info=True)
            raise e

    async def _prepare_tasks(self, project_root: Path, project_id: str, target_files: Optional[list[str]] = None):
        raw_input_dir = project_root / "原始輸入"
        split_output_dir = project_root / "分割發票"

        if not raw_input_dir.exists():
            return

        files_to_process = []
        if target_files:
            files_to_process = target_files
        else:
            files_to_process = [f.name for f in raw_input_dir.iterdir() if f.is_file()]

        for image_name in files_to_process:
            try:
                image_path = raw_input_dir / image_name
                if not image_path.exists():
                    logger.warning(f"File not found: {image_path}")
                    continue

                if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.jxl')):
                    continue

                semaphore = getattr(self.engine, "image_processing_semaphore", None)
                if semaphore is not None:
                    async with semaphore:
                        image = utils.cv_imread_chinese(str(image_path))
                        if image is None:
                            logger.error(f"Failed to read image: {image_path}")
                            continue
                        cropped_images = self.receipt_splitter.split(image, debug=False, headless=True)
                else:
                    image = utils.cv_imread_chinese(str(image_path))
                    if image is None:
                        logger.error(f"Failed to read image: {image_path}")
                        continue
                    cropped_images = self.receipt_splitter.split(image, debug=False, headless=True)

                cropped_paths = []
                codec = self._codec_adapter()
                for i, img in enumerate(cropped_images):
                    # Use high-resolution timestamp + random suffix to prevent filename collisions
                    # when multiple sources share the same stem or are split within the same second.
                    unique_token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
                    save_stem = split_output_dir / f"{image_path.stem}_split_{i}_{unique_token}"
                    archival_path = codec.build_archival_path(save_stem)
                    saved_path = codec.write_archival_image(archival_path, img)
                    cropped_paths.append(saved_path)

                logger.info(f"[FileOps] Saved {len(cropped_paths)} split images for {image_name}")

                # Enqueue with ABSOLUTE paths
                for path in cropped_paths:
                    abs_path = str(path.resolve())
                    preview = None
                    try:
                        max_width = self._thumb_max_width()
                        preview = await self.ensure_preview_cache(project_id, abs_path, max_width=max_width)
                    except Exception as preview_err:
                        logger.warning(f"[FileOps] preview cache warmup failed for {abs_path}: {preview_err}")
                    job_id = await self.engine.enqueue_job(project_id, abs_path)
                    try:
                        await self.engine.get_job_repo(project_id).update_job(
                            job_id,
                            source_format=path.suffix.lstrip(".") or "jpg",
                            preview_cache_path=preview["path"] if preview else None,
                        )
                    except Exception as meta_err:
                        logger.warning(f"[FileOps] asset metadata update failed for {abs_path}: {meta_err}")
                    logger.debug(f"[FileOps] Enqueued job with absolute path: {abs_path}")

            except Exception as e:
                logger.error(f"Error preparing tasks for {image_name}: {e}")

    def get_raw_files(self, project_id: str):
        try:
            root = self.project_repo._project_root(project_id)
            raw_dir = root / "原始輸入"
            split_dir = root / "分割發票"

            if not raw_dir.exists():
                return []

            raw_files = []
            for f in os.listdir(raw_dir):
                if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.jxl')):
                    continue

                base_name = os.path.splitext(f)[0]
                split_count = 0
                if split_dir.exists():
                    for sf in os.listdir(split_dir):
                        if sf.startswith(base_name + "_split_"):
                            split_count += 1

                raw_files.append({
                    "filename": f,
                    "path": str(raw_dir / f),
                    "split_count": split_count
                })
            return raw_files
        except Exception as e:
            logger.error(f"Error getting raw files for {project_id}: {e}")
            return []

    async def add_project_files(self, project_id: str, files: list[str], type: str = "raw"):
        try:
            root = self.project_repo._project_root(project_id)
            if type == "raw":
                target_dir = root / "原始輸入"
            elif type == "split":
                target_dir = root / "分割發票"
            else:
                raise ValueError("Invalid type")

            target_dir.mkdir(parents=True, exist_ok=True)

            # Initialize conversion progress
            image_files = [
                f for f in files
                if Path(f).suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.jxl')
            ]
            self.project_repo.set_conversion_total(project_id, len(image_files))

            codec = self._codec_adapter()

            for file_path in files:
                src = Path(file_path)
                original_suffix = src.suffix.lower() or ".jpg"

                if type == "split":
                    stem = src.stem
                    unique_token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
                    base_stem = f"{stem}_split_manual_{unique_token}"
                else:
                    base_stem = src.stem

                # Only convert image files through codec
                if original_suffix in ('.png', '.jpg', '.jpeg', '.bmp', '.jxl'):
                    try:
                        image = await asyncio.to_thread(
                            utils.cv_imread_chinese, str(file_path)
                        )
                    except Exception as read_err:
                        logger.warning(
                            f"[FileOps] Failed to read {file_path} for conversion, "
                            f"falling back to copy: {read_err}"
                        )
                        dest_path = target_dir / f"{base_stem}{original_suffix}"
                        shutil.copy(file_path, dest_path)
                        self.project_repo.inc_conversion_progress(project_id)
                        continue

                    archival_stem = target_dir / base_stem
                    archival_path = codec.build_archival_path(archival_stem)

                    semaphore = self._image_semaphore()
                    if semaphore is not None:
                        async with semaphore:
                            dest_path = await asyncio.to_thread(
                                codec.write_archival_image,
                                archival_path,
                                image,
                                original_suffix,
                            )
                    else:
                        dest_path = await asyncio.to_thread(
                            codec.write_archival_image,
                            archival_path,
                            image,
                            original_suffix,
                        )

                    self.project_repo.inc_conversion_progress(project_id)
                else:
                    # Non-image file: just copy
                    dest_path = target_dir / f"{base_stem}{original_suffix}"
                    shutil.copy(file_path, dest_path)

                if type == "split":
                    # Enqueue with ABSOLUTE path
                    abs_path = str(Path(dest_path).resolve())
                    preview = None
                    try:
                        max_width = self._thumb_max_width()
                        preview = await self.ensure_preview_cache(project_id, abs_path, max_width=max_width)
                    except Exception as preview_err:
                        logger.warning(f"[FileOps] preview cache warmup failed for {abs_path}: {preview_err}")
                    job_id = await self.engine.enqueue_job(project_id, abs_path)
                    try:
                        await self.engine.get_job_repo(project_id).update_job(
                            job_id,
                            source_format=Path(dest_path).suffix.lstrip(".") or "jpg",
                            preview_cache_path=preview["path"] if preview else None,
                        )
                    except Exception as meta_err:
                        logger.warning(f"[FileOps] asset metadata update failed for {abs_path}: {meta_err}")
                    logger.debug(f"[FileOps] Enqueued split file with absolute path: {abs_path}")

            return {"status": "added"}
        except Exception as e:
            logger.error(f"Error adding files to {project_id}: {e}")
            raise e

    async def rotate_image(self, project_id: str, filename: str, angle: int = 90):
        try:
            root = self.project_repo._project_root(project_id)
            image_path = root / "分割發票" / filename
            if not image_path.exists():
                raise FileNotFoundError(f"Image {filename} not found in splits")

            image = utils.cv_imread_chinese(str(image_path))
            if image is None:
                raise ValueError("Failed to read image")

            if angle == 90:
                image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            elif angle == -90 or angle == 270:
                image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif angle == 180:
                image = cv2.rotate(image, cv2.ROTATE_180)

            utils.cv_imwrite_chinese(str(image_path), image)
            self.invalidate_preview_cache(project_id, str(image_path))
            try:
                max_width = self._thumb_max_width()
                await self.ensure_preview_cache(project_id, str(image_path), max_width=max_width)
            except Exception as preview_err:  # noqa: BLE001
                logger.warning(f"[FileOps] preview cache rebuild failed for {image_path}: {preview_err}")

            job_repo = self.engine.get_job_repo(project_id)
            jobs = await job_repo.list_jobs()
            rotated_abs_path = str(image_path.resolve())
            reset_job_ids = []
            for job in jobs:
                job_path = str(job.get("image_path") or "")
                if not job_path:
                    continue
                job_path_abs = str(Path(job_path).resolve())
                if job_path_abs == rotated_abs_path or Path(job_path).name == filename:
                    await job_repo.update_job(
                        job["job_id"],
                        # Rotation invalidates extracted results, but does not enqueue processing.
                        # Keep status as ready so UI/queue semantics remain consistent.
                        status="ready",
                        vlm_result_json=None,
                        manual_json_text=None,
                        validation_json=None,
                        vlm_stats=None,
                        qr_verified=0,
                    )
                    reset_job_ids.append(job["job_id"])

            return {"status": "rotated", "path": str(image_path), "reset_jobs": reset_job_ids}
        except Exception as e:
            logger.error(f"Error rotating image {filename}: {e}")
            raise e

    def _get_preview_cache_dir(self, project_id: str) -> Path:
        root = self.project_repo._project_root(project_id)
        cache_dir = root / "快取影像" / "voucher_preview"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_preview_format(self) -> tuple[str, str, str]:
        configured = self._engine_config().get("processing_settings", {}).get("preview_formats", ["avif", "webp", "jpeg"])
        candidates = [str(fmt).lower() for fmt in configured if str(fmt).strip()]
        if not candidates:
            candidates = ["avif", "webp", "jpeg"]

        for fmt in candidates:
            if fmt == "avif":
                try:
                    if features.check("avif"):
                        return ("AVIF", "avif", "image/avif")
                except Exception:
                    pass
            if fmt == "webp":
                try:
                    if features.check("webp"):
                        return ("WEBP", "webp", "image/webp")
                except Exception:
                    pass
            if fmt in ("jpg", "jpeg"):
                return ("JPEG", "jpg", "image/jpeg")

        return ("JPEG", "jpg", "image/jpeg")

    def _build_preview_cache_path(self, project_id: str, image_path: str, max_width: int, extension: str) -> Path:
        source = Path(image_path)
        stat = source.stat()
        sig = f"{stat.st_mtime_ns}_{stat.st_size}_{max_width}"
        return self._get_preview_cache_dir(project_id) / f"{source.stem}_{sig}.{extension}"

    @staticmethod
    def _render_preview(source_path: str, cache_path: str, pil_format: str, max_width: int):
        image = ImageCodecAdapter().read_image_pil(source_path)
        if image.width > max_width:
            new_height = int((max_width / image.width) * image.height)
            image = image.resize((max_width, max(1, new_height)), Image.Resampling.LANCZOS)

        save_kwargs = {}
        if pil_format == "AVIF":
            save_kwargs = {"quality": 60}
        elif pil_format == "WEBP":
            save_kwargs = {"quality": 85}
        elif pil_format == "JPEG":
            save_kwargs = {"quality": 90}

        image.save(cache_path, format=pil_format, **save_kwargs)

    async def ensure_preview_cache(self, project_id: str, image_path: str, max_width: int = 800) -> Optional[dict]:
        source = Path(image_path)
        if not source.exists() or not source.is_file():
            return None

        pil_format, extension, media_type = self._get_preview_format()
        cache_path = self._build_preview_cache_path(project_id, image_path, max_width, extension)
        if cache_path.exists():
            return {"path": str(cache_path), "media_type": media_type, "cache_hit": True}

        semaphore = self._image_semaphore()
        if semaphore is not None:
            async with semaphore:
                await asyncio.to_thread(
                    self._render_preview,
                    str(source),
                    str(cache_path),
                    pil_format,
                    max_width,
                )
        else:
            await asyncio.to_thread(
                self._render_preview,
                str(source),
                str(cache_path),
                pil_format,
                max_width,
            )

        return {"path": str(cache_path), "media_type": media_type, "cache_hit": False}

    def invalidate_preview_cache(self, project_id: str, image_path: str):
        source = Path(image_path)
        cache_dir = self._get_preview_cache_dir(project_id)
        for cached in cache_dir.glob(f"{source.stem}_*"):
            try:
                cached.unlink()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[FileOps] failed to delete preview cache {cached}: {exc}")

    async def cleanup_project_cache(self, project_id: str, max_age_hours: int = 24) -> dict[str, Any]:
        root = self.project_repo._project_root(project_id)
        cache_root = root / "快取影像"
        if not cache_root.exists():
            return {
                "project_id": project_id,
                "deleted_files": 0,
                "missing_cache_root": True,
            }

        cutoff = time.time() - max(1, int(max_age_hours)) * 3600
        deleted_files = 0

        for file_path in cache_root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    deleted_files += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[FileOps] cache cleanup failed for {file_path}: {exc}")

        for dir_path in sorted((p for p in cache_root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            try:
                dir_path.rmdir()
            except OSError:
                pass

        return {
            "project_id": project_id,
            "deleted_files": deleted_files,
            "missing_cache_root": False,
        }

    async def cleanup_all_projects_cache(self, max_age_hours: int = 24) -> dict[str, Any]:
        projects = await self.project_repo.list_projects()
        summaries = []
        total_deleted = 0
        for project in projects:
            project_id = project.get("project_id") or project.get("id")
            if not project_id:
                continue
            summary = await self.cleanup_project_cache(project_id, max_age_hours=max_age_hours)
            summaries.append(summary)
            total_deleted += int(summary.get("deleted_files", 0))

        return {
            "status": "completed",
            "projects": len(summaries),
            "deleted_files": total_deleted,
            "details": summaries,
        }

    async def delete_job_files(self, project_id: str, job_id: str) -> dict[str, Any]:
        root = self.project_repo._project_root(project_id)
        job_repo = self.engine.get_job_repo(project_id)
        job = await job_repo.get_job(job_id)
        if not job:
            return {
                "job_found": False,
                "deleted_files": [],
                "missing_files": [],
            }

        deleted_files: list[str] = []
        missing_files: list[str] = []
        targets: list[Optional[Path]] = [
            self._resolve_project_path(root, job.get("image_path"), preferred_dir="分割發票"),
            self._resolve_project_path(root, job.get("source_pdf_path"), preferred_dir="原始輸入"),
            self._resolve_project_path(root, job.get("compressed_pdf_path"), preferred_dir="輸出結果"),
            self._resolve_project_path(root, job.get("preview_cache_path"), preferred_dir="快取影像/voucher_preview"),
        ]

        image_target = targets[0]
        if image_target is not None:
            self.invalidate_preview_cache(project_id, str(image_target))

        seen: set[str] = set()
        for target in targets:
            if target is None:
                continue
            key = str(target.resolve(strict=False))
            if key in seen:
                continue
            seen.add(key)
            self._safe_delete_file(root, target, deleted_files, missing_files)

        return {
            "job_found": True,
            "deleted_files": deleted_files,
            "missing_files": missing_files,
        }

    async def optimize_jxl_storage(self, project_id: str, force: bool = False) -> dict[str, Any]:
        root = self.project_repo._project_root(project_id)
        job_repo = self.engine.get_job_repo(project_id)
        jobs = await job_repo.list_jobs()
        if not jobs:
            return {
                "project_id": project_id,
                "optimized_jobs": 0,
                "skipped_jobs": 0,
                "failed_jobs": 0,
                "deleted_legacy_files": 0,
            }

        processing_settings = dict(self._engine_config().get("processing_settings", {}))
        processing_settings["archival_format"] = "jxl"
        codec = ImageCodecAdapter(processing_settings)
        if codec.resolve_archival_extension() != "jxl":
            return {
                "project_id": project_id,
                "optimized_jobs": 0,
                "skipped_jobs": len(jobs),
                "failed_jobs": 0,
                "deleted_legacy_files": 0,
                "reason": "jxl_unavailable",
            }

        path_ref_counts: Counter[str] = Counter()
        resolved_paths: dict[str, Optional[Path]] = {}
        for job in jobs:
            source = self._resolve_project_path(root, job.get("image_path"), preferred_dir="分割發票")
            resolved_paths[job["job_id"]] = source
            if source is not None:
                path_ref_counts[str(source.resolve(strict=False))] += 1

        optimized_jobs = 0
        skipped_jobs = 0
        failed_jobs = 0
        deleted_legacy_files = 0

        for job in jobs:
            job_id = job["job_id"]
            source = resolved_paths.get(job_id)
            if source is None:
                skipped_jobs += 1
                continue

            src_abs = source.resolve(strict=False)
            src_suffix = src_abs.suffix.lower()
            if src_suffix == ".jxl" and not force:
                skipped_jobs += 1
                continue

            target = src_abs.with_suffix(".jxl")
            try:
                if target.exists() and not force:
                    saved = target
                else:
                    image = await asyncio.to_thread(utils.cv_imread_chinese, str(src_abs))
                    if image is None:
                        failed_jobs += 1
                        continue

                    semaphore = self._image_semaphore()
                    if semaphore is not None:
                        async with semaphore:
                            saved = await asyncio.to_thread(
                                codec.write_archival_image,
                                target,
                                image,
                                src_abs.suffix or ".jpg",
                            )
                    else:
                        saved = await asyncio.to_thread(
                            codec.write_archival_image,
                            target,
                            image,
                            src_abs.suffix or ".jpg",
                        )

                saved_abs = Path(saved).resolve(strict=False)
                if saved_abs.suffix.lower() != ".jxl":
                    failed_jobs += 1
                    continue

                self.invalidate_preview_cache(project_id, str(src_abs))
                preview = None
                try:
                    preview = await self.ensure_preview_cache(
                        project_id,
                        str(saved_abs),
                        max_width=self._thumb_max_width(),
                    )
                except Exception as preview_err:  # noqa: BLE001
                    logger.warning(f"[FileOps] preview cache warmup failed after optimize for {saved_abs}: {preview_err}")

                await job_repo.update_job(
                    job_id,
                    image_path=str(saved_abs),
                    source_format="jxl",
                    preview_cache_path=preview["path"] if preview else None,
                )
                optimized_jobs += 1

                if saved_abs != src_abs:
                    key = str(src_abs)
                    path_ref_counts[key] -= 1
                    if path_ref_counts[key] <= 0 and src_abs.exists() and self._is_within_root(root, src_abs):
                        try:
                            src_abs.unlink()
                            deleted_legacy_files += 1
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(f"[FileOps] failed deleting legacy source {src_abs}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failed_jobs += 1
                logger.warning(f"[FileOps] optimize_jxl_storage failed for job {job_id}: {exc}")

        return {
            "project_id": project_id,
            "optimized_jobs": optimized_jobs,
            "skipped_jobs": skipped_jobs,
            "failed_jobs": failed_jobs,
            "deleted_legacy_files": deleted_legacy_files,
        }

    async def detect_job_sub_rects(self, project_id: str, job_id: str) -> list[dict[str, Any]]:
        root = self.project_repo._project_root(project_id)
        job_repo = self.engine.get_job_repo(project_id)
        job = await job_repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        source = self._resolve_project_path(root, job.get("image_path"), preferred_dir="分割發票")
        if source is None or not source.exists():
            raise FileNotFoundError(f"Image not found for job {job_id}")

        image = await asyncio.to_thread(utils.cv_imread_chinese, str(source))
        if image is None:
            raise ValueError(f"Failed to read image for job {job_id}")

        return self.receipt_splitter.detect_only(image)

    async def apply_job_resplit(self, project_id: str, job_id: str, sub_rects: list[dict[str, Any]]) -> dict[str, Any]:
        if not sub_rects:
            raise ValueError("sub_rects cannot be empty")

        root = self.project_repo._project_root(project_id)
        split_dir = root / "分割發票"
        split_dir.mkdir(parents=True, exist_ok=True)

        job_repo = self.engine.get_job_repo(project_id)
        job = await job_repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        source = self._resolve_project_path(root, job.get("image_path"), preferred_dir="分割發票")
        if source is None or not source.exists():
            raise FileNotFoundError(f"Image not found for job {job_id}")

        image = await asyncio.to_thread(utils.cv_imread_chinese, str(source))
        if image is None:
            raise ValueError(f"Failed to read source image for job {job_id}")

        codec = self._codec_adapter()
        new_job_ids: list[str] = []
        new_paths: list[str] = []

        for idx, item in enumerate(sub_rects):
            points_raw = item.get("points") if isinstance(item, dict) else None
            if not isinstance(points_raw, list) or len(points_raw) != 4:
                continue

            try:
                points = np.array(points_raw, dtype=np.float32)
                if points.shape != (4, 2):
                    continue
            except Exception:
                continue

            crop = self._warp_by_points(image, points)
            if crop.size == 0:
                continue

            crop = fix_orientation(crop)
            token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
            stem = split_dir / f"{source.stem}_resplit_{idx}_{token}"
            archival_path = codec.build_archival_path(stem)

            semaphore = self._image_semaphore()
            if semaphore is not None:
                async with semaphore:
                    saved_path = await asyncio.to_thread(
                        codec.write_archival_image,
                        archival_path,
                        crop,
                        source.suffix or ".jpg",
                    )
            else:
                saved_path = await asyncio.to_thread(
                    codec.write_archival_image,
                    archival_path,
                    crop,
                    source.suffix or ".jpg",
                )

            abs_path = str(Path(saved_path).resolve())
            preview = None
            try:
                preview = await self.ensure_preview_cache(
                    project_id,
                    abs_path,
                    max_width=self._thumb_max_width(),
                )
            except Exception as preview_err:  # noqa: BLE001
                logger.warning(f"[FileOps] preview cache warmup failed for resplit {abs_path}: {preview_err}")

            new_job_id = await self.engine.enqueue_job(project_id, abs_path)
            await job_repo.update_job(
                new_job_id,
                source_format=Path(saved_path).suffix.lstrip(".") or "jpg",
                preview_cache_path=preview["path"] if preview else None,
            )

            new_job_ids.append(new_job_id)
            new_paths.append(abs_path)

        if not new_job_ids:
            raise ValueError("No valid sub-rect generated any image")

        delete_result = await self.engine.delete_job(project_id, job_id)
        return {
            "status": "resplit_applied",
            "old_job_id": job_id,
            "new_job_ids": new_job_ids,
            "new_paths": new_paths,
            "delete_old": delete_result,
        }

    async def add_pdf_files(self, project_id: str, files: list[str]):
        """
        處理 PDF 檔案上傳。
        將 PDF 第一頁渲染為圖片，透過 ImageCodecAdapter 轉檔後建立 Job。
        """
        try:
            import fitz
            import numpy as np
            root = self.project_repo._project_root(project_id)
            raw_dir = root / "原始輸入"
            split_dir = root / "分割發票"

            raw_dir.mkdir(parents=True, exist_ok=True)
            split_dir.mkdir(parents=True, exist_ok=True)

            # Initialize conversion progress
            self.project_repo.set_conversion_total(project_id, len(files))

            codec = self._codec_adapter()

            for file_path in files:
                # 1. 複製原始 PDF 檔案
                filename = Path(file_path).name
                dest_pdf_path = raw_dir / filename
                shutil.copy(file_path, dest_pdf_path)

                # 2. 渲染首頁並透過 codec 轉檔
                try:
                    doc = fitz.open(str(dest_pdf_path))
                    page = doc[0]
                    zoom_matrix = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=zoom_matrix)

                    # Convert pixmap to numpy BGR array
                    img_data = pix.samples
                    if pix.n == 4:  # RGBA
                        img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.h, pix.w, 4)
                        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                    else:  # RGB
                        img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.h, pix.w, 3)
                        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    doc.close()

                    ts = int(time.time())
                    stem = Path(filename).stem
                    save_stem = split_dir / f"{stem}_page0_{ts}"
                    archival_path = codec.build_archival_path(save_stem)

                    semaphore = self._image_semaphore()
                    if semaphore is not None:
                        async with semaphore:
                            dest_img_path = await asyncio.to_thread(
                                codec.write_archival_image,
                                archival_path,
                                img_bgr,
                                ".png",  # fallback to PNG for PDF renders
                            )
                    else:
                        dest_img_path = await asyncio.to_thread(
                            codec.write_archival_image,
                            archival_path,
                            img_bgr,
                            ".png",
                        )

                    self.project_repo.inc_conversion_progress(project_id)

                    # 3. 建立 Job
                    await self.engine.enqueue_pdf_upload(
                        project_id,
                        str(dest_pdf_path.resolve()),
                        str(Path(dest_img_path).resolve())
                    )
                    logger.debug(f"[FileOps] 處理 PDF {filename} 並轉存為 {dest_img_path}")
                except Exception as ex:
                    logger.error(f"[FileOps] 處理 PDF 渲染/轉檔失敗: {ex}")
                    self.project_repo.inc_conversion_progress(project_id)

            return {"status": "added"}
        except Exception as e:
            logger.error(f"Error adding pdf files to {project_id}: {e}")
            raise e
