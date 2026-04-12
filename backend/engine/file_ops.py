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
from backend.processing.image_codec_adapter import ImageCodecAdapter
from backend.processing.perspective_transform import order_points
from backend.engine.cache_mixin import CacheMixin
from backend.utils import utils

logger = logging.getLogger(__name__)


class FileOps(CacheMixin):
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

    def _deferred_gc_queue(self) -> list[dict[str, Any]]:
        queue = getattr(self.engine, "_deferred_file_gc", None)
        if not isinstance(queue, list):
            queue = []
            setattr(self.engine, "_deferred_file_gc", queue)
        return queue

    def _enqueue_deferred_file_gc(self, project_id: str, root: Path, target: Optional[Path]):
        if target is None:
            return
        resolved = target.resolve(strict=False)
        if not self._is_within_root(root, resolved):
            return
        queue = self._deferred_gc_queue()
        key = str(resolved)
        for item in queue:
            if item.get("project_id") == project_id and item.get("path") == key:
                return
        queue.append({
            "project_id": project_id,
            "path": key,
            "created_at": time.time(),
        })

    async def flush_deferred_gc(self, project_id: str) -> dict[str, Any]:
        queue = self._deferred_gc_queue()
        if not queue:
            return {"deleted_files": [], "missing_files": [], "kept_referenced": []}

        root = self.project_repo._project_root(project_id)
        job_repo = self.engine.get_job_repo(project_id)
        jobs = await job_repo.list_jobs()

        referenced_paths: set[str] = set()
        for job in jobs:
            source = self._resolve_project_path(root, job.get("image_path"), preferred_dir="分割發票")
            if source is None:
                continue
            referenced_paths.add(str(source.resolve(strict=False)))

        deleted_files: list[str] = []
        missing_files: list[str] = []
        kept_referenced: list[str] = []

        remaining: list[dict[str, Any]] = []
        for item in queue:
            if item.get("project_id") != project_id:
                remaining.append(item)
                continue

            path = Path(str(item.get("path") or "")).resolve(strict=False)
            key = str(path)
            if key in referenced_paths:
                kept_referenced.append(key)
                remaining.append(item)
                continue

            self._safe_delete_file(root, path, deleted_files, missing_files)

        queue.clear()
        queue.extend(remaining)
        return {
            "deleted_files": deleted_files,
            "missing_files": missing_files,
            "kept_referenced": kept_referenced,
        }

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
            files_to_process = await asyncio.to_thread(
                lambda: [f.name for f in raw_input_dir.iterdir() if f.is_file()]
            )

        for image_name in files_to_process:
            try:
                image_path = raw_input_dir / image_name
                if not await asyncio.to_thread(image_path.exists):
                    logger.warning(f"File not found: {image_path}")
                    continue

                if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.jxl')):
                    continue

                async with self._optional_semaphore():
                    image = await asyncio.to_thread(utils.cv_imread_chinese, str(image_path))
                    if image is None:
                        logger.error(f"Failed to read image: {image_path}")
                        continue
                    cropped_images = await asyncio.to_thread(
                        self.receipt_splitter.split,
                        image,
                        debug=False,
                        headless=True,
                    )

                cropped_paths = []
                codec = self._codec_adapter()
                for i, img in enumerate(cropped_images):
                    # Use high-resolution timestamp + random suffix to prevent filename collisions
                    # when multiple sources share the same stem or are split within the same second.
                    unique_token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
                    save_stem = split_output_dir / f"{image_path.stem}_split_{i}_{unique_token}"
                    archival_path = codec.build_archival_path(save_stem)
                    async with self._optional_semaphore():
                        saved_path = await asyncio.to_thread(codec.write_archival_image, archival_path, img)
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

            await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)

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
                        await asyncio.to_thread(shutil.copy, file_path, dest_path)
                        self.project_repo.inc_conversion_progress(project_id)
                        continue

                    archival_stem = target_dir / base_stem
                    archival_path = codec.build_archival_path(archival_stem)

                    async with self._optional_semaphore():
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
                    await asyncio.to_thread(shutil.copy, file_path, dest_path)

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

            image = await asyncio.to_thread(utils.cv_imread_chinese, str(image_path))
            if image is None:
                raise ValueError("Failed to read image")

            def _rotate_image_sync(raw: np.ndarray, rotate_angle: int) -> np.ndarray:
                if rotate_angle == 90:
                    return cv2.rotate(raw, cv2.ROTATE_90_CLOCKWISE)
                if rotate_angle == -90 or rotate_angle == 270:
                    return cv2.rotate(raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
                if rotate_angle == 180:
                    return cv2.rotate(raw, cv2.ROTATE_180)
                return raw

            image = await asyncio.to_thread(_rotate_image_sync, image, angle)

            await asyncio.to_thread(utils.cv_imwrite_chinese, str(image_path), image)
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

    async def delete_job_files(self, project_id: str, job_id: str) -> dict[str, Any]:
        root = self.project_repo._project_root(project_id)
        job_repo = self.engine.get_job_repo(project_id)
        job = await job_repo.get_job(job_id)
        if not job:
            return {
                "job_found": False,
                "deleted_files": [],
                "missing_files": [],
                "deferred_files": [],
                "skipped_shared_files": [],
            }

        deleted_files: list[str] = []
        missing_files: list[str] = []
        deferred_files: list[str] = []
        skipped_shared_files: list[str] = []
        targets: list[Optional[Path]] = [
            self._resolve_project_path(root, job.get("image_path"), preferred_dir="分割發票"),
            self._resolve_project_path(root, job.get("source_pdf_path"), preferred_dir="原始輸入"),
            self._resolve_project_path(root, job.get("compressed_pdf_path"), preferred_dir="輸出結果"),
            self._resolve_project_path(root, job.get("preview_cache_path"), preferred_dir="快取影像/voucher_preview"),
        ]

        image_target = targets[0]
        if image_target is not None:
            image_key = str(image_target.resolve(strict=False))
            self._enqueue_deferred_file_gc(project_id, root, image_target)
            deferred_files.append(image_key)

            for row in await job_repo.list_jobs():
                if row.get("job_id") == job_id:
                    continue
                other = self._resolve_project_path(root, row.get("image_path"), preferred_dir="分割發票")
                if other is None:
                    continue
                if str(other.resolve(strict=False)) == image_key:
                    skipped_shared_files.append(image_key)
                    break

            if not skipped_shared_files:
                self.invalidate_preview_cache(project_id, str(image_target))

        seen: set[str] = set()
        for target in targets[1:]:
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
            "deferred_files": deferred_files,
            "skipped_shared_files": skipped_shared_files,
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

                    async with self._optional_semaphore():
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
        await asyncio.to_thread(split_dir.mkdir, parents=True, exist_ok=True)

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
            token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
            stem = split_dir / f"{source.stem}_resplit_{idx}_{token}"
            archival_path = codec.build_archival_path(stem)

            async with self._optional_semaphore():
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
            root = self.project_repo._project_root(project_id)
            raw_dir = root / "原始輸入"
            split_dir = root / "分割發票"

            await asyncio.to_thread(raw_dir.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(split_dir.mkdir, parents=True, exist_ok=True)

            # Initialize conversion progress
            self.project_repo.set_conversion_total(project_id, len(files))

            codec = self._codec_adapter()

            for file_path in files:
                # 1. 複製原始 PDF 檔案
                filename = Path(file_path).name
                dest_pdf_path = raw_dir / filename
                await asyncio.to_thread(shutil.copy, file_path, dest_pdf_path)

                # 2. 渲染首頁並透過 codec 轉檔
                try:
                    img_bgr = await asyncio.to_thread(self._render_pdf_first_page_to_bgr, str(dest_pdf_path))

                    ts = int(time.time())
                    stem = Path(filename).stem
                    save_stem = split_dir / f"{stem}_page0_{ts}"
                    archival_path = codec.build_archival_path(save_stem)

                    async with self._optional_semaphore():
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
