import time
import logging
import asyncio
import uuid
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Any

from backend.utils import utils
from backend.processing.perspective_transform import order_points
from backend.engine.resplit_source import (
    job_matches_raw_filename,
    resolve_raw_source_by_filename,
    resolve_resplit_raw_source,
)

logger = logging.getLogger(__name__)


class ResplitService:
    def __init__(self, project_repo, receipt_splitter, engine_ref, image_service):
        self.project_repo = project_repo
        self.receipt_splitter = receipt_splitter
        self.engine = engine_ref
        self.image_service = image_service

    def _codec_adapter(self):
        return self.image_service._codec_adapter()

    def _thumb_max_width(self) -> int:
        return self.image_service._thumb_max_width()

    def _optional_semaphore(self):
        return self.image_service._optional_semaphore()

    def _resolve_project_path(self, root: Path, raw_path: Optional[str], preferred_dir: Optional[str] = None) -> Optional[Path]:
        return self.image_service._resolve_project_path(root, raw_path, preferred_dir)

    def _is_within_root(self, root: Path, target: Path) -> bool:
        return self.image_service._is_within_root(root, target)

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
            logger.info(f"[ResplitService] run_splitting started for {project_id}, target_files={target_files}")
            root = self.project_repo._project_root(project_id)

            await self._prepare_tasks(root, project_id, target_files=target_files)

            await self.project_repo.update_project_status(project_id, "SPLIT")
            logger.info(f"[ResplitService] run_splitting completed for {project_id}")
            return {"status": "split_completed"}
        except Exception as e:
            logger.error(f"[ResplitService] Error splitting for {project_id}: {e}", exc_info=True)
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
                    unique_token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
                    save_stem = split_output_dir / f"{image_path.stem}_split_{i}_{unique_token}"
                    archival_path = codec.build_archival_path(save_stem)
                    async with self._optional_semaphore():
                        saved_path = await asyncio.to_thread(codec.write_archival_image, archival_path, img)
                    cropped_paths.append(saved_path)

                logger.info(f"[ResplitService] Saved {len(cropped_paths)} split images for {image_name}")

                for path in cropped_paths:
                    abs_path = str(path.resolve())
                    preview = None
                    try:
                        max_width = self._thumb_max_width()
                        preview = await self.image_service.ensure_preview_cache(project_id, abs_path, max_width=max_width)
                    except Exception as preview_err:
                        logger.warning(f"[ResplitService] preview cache warmup failed for {abs_path}: {preview_err}")
                    job_id = await self.engine.enqueue_job(project_id, abs_path)
                    try:
                        await self.engine.get_job_repo(project_id).update_job(
                            job_id,
                            source_format=path.suffix.lstrip(".") or "jpg",
                            preview_cache_path=preview["path"] if preview else None,
                        )
                    except Exception as meta_err:
                        logger.warning(f"[ResplitService] asset metadata update failed for {abs_path}: {meta_err}")
                    logger.debug(f"[ResplitService] Enqueued job with absolute path: {abs_path}")

            except Exception as e:
                logger.error(f"Error preparing tasks for {image_name}: {e}")

    async def _create_resplit_jobs_from_source(
        self,
        project_id: str,
        source: Path,
        image: np.ndarray,
        sub_rects: list[dict[str, Any]],
    ) -> tuple[list[str], list[str]]:
        codec = self._codec_adapter()
        job_repo = self.engine.get_job_repo(project_id)
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
            stem = (self.project_repo._project_root(project_id) / "分割發票") / f"{source.stem}_resplit_{idx}_{token}"
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
                preview = await self.image_service.ensure_preview_cache(
                    project_id,
                    abs_path,
                    max_width=self._thumb_max_width(),
                )
            except Exception as preview_err:  # noqa: BLE001
                logger.warning(f"[ResplitService] preview cache warmup failed for resplit {abs_path}: {preview_err}")

            new_job_id = await self.engine.enqueue_job(project_id, abs_path)
            await job_repo.update_job(
                new_job_id,
                source_format=Path(saved_path).suffix.lstrip(".") or "jpg",
                preview_cache_path=preview["path"] if preview else None,
            )

            new_job_ids.append(new_job_id)
            new_paths.append(abs_path)

        return new_job_ids, new_paths

    async def detect_job_sub_rects(self, project_id: str, job_id: str) -> list[dict[str, Any]]:
        root = self.project_repo._project_root(project_id)
        job_repo = self.engine.get_job_repo(project_id)
        job = await job_repo.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        source = await asyncio.to_thread(
            resolve_resplit_raw_source,
            root,
            job,
            self._resolve_project_path,
            logger,
        )
        if source is None or not source.exists():
            raise FileNotFoundError(f"Image not found for job {job_id}")

        image = await asyncio.to_thread(utils.cv_imread_chinese, str(source))
        if image is None:
            raise ValueError(f"Failed to read image for job {job_id}")

        return self.receipt_splitter.detect_only(image)

    async def detect_raw_sub_rects(self, project_id: str, raw_filename: str) -> dict[str, Any]:
        root = self.project_repo._project_root(project_id)
        source = await asyncio.to_thread(resolve_raw_source_by_filename, root, raw_filename)
        if source is None or not source.exists():
            raise FileNotFoundError(f"Raw image not found: {raw_filename}")

        image = await asyncio.to_thread(utils.cv_imread_chinese, str(source))
        if image is None:
            raise ValueError(f"Failed to read raw image: {raw_filename}")

        rects = self.receipt_splitter.detect_only(image)
        full_height, full_width = image.shape[:2]
        return {
            "rects": rects,
            "full_width": int(full_width),
            "full_height": int(full_height),
        }

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

        source = await asyncio.to_thread(
            resolve_resplit_raw_source,
            root,
            job,
            self._resolve_project_path,
            logger,
        )
        if source is None or not source.exists():
            raise FileNotFoundError(f"Image not found for job {job_id}")

        image = await asyncio.to_thread(utils.cv_imread_chinese, str(source))
        if image is None:
            raise ValueError(f"Failed to read source image for job {job_id}")

        new_job_ids, new_paths = await self._create_resplit_jobs_from_source(
            project_id=project_id,
            source=source,
            image=image,
            sub_rects=sub_rects,
        )

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

    async def apply_raw_resplit(self, project_id: str, raw_filename: str, sub_rects: list[dict[str, Any]]) -> dict[str, Any]:
        if not sub_rects:
            raise ValueError("sub_rects cannot be empty")

        root = self.project_repo._project_root(project_id)
        split_dir = root / "分割發票"
        await asyncio.to_thread(split_dir.mkdir, parents=True, exist_ok=True)

        source = await asyncio.to_thread(resolve_raw_source_by_filename, root, raw_filename)
        if source is None or not source.exists():
            raise FileNotFoundError(f"Raw image not found: {raw_filename}")

        image = await asyncio.to_thread(utils.cv_imread_chinese, str(source))
        if image is None:
            raise ValueError(f"Failed to read raw image: {raw_filename}")

        job_repo = self.engine.get_job_repo(project_id)
        existing_jobs = await job_repo.list_jobs()
        replaced_job_ids = [
            str(job.get("job_id"))
            for job in existing_jobs
            if job.get("job_id") and job_matches_raw_filename(job, raw_filename)
        ]

        new_job_ids, new_paths = await self._create_resplit_jobs_from_source(
            project_id=project_id,
            source=source,
            image=image,
            sub_rects=sub_rects,
        )
        if not new_job_ids:
            raise ValueError("No valid sub-rect generated any image")

        delete_results = []
        for old_job_id in replaced_job_ids:
            delete_results.append(await self.engine.delete_job(project_id, old_job_id))

        return {
            "status": "resplit_applied",
            "raw_filename": Path(str(raw_filename)).name,
            "replaced_job_ids": replaced_job_ids,
            "new_job_ids": new_job_ids,
            "new_paths": new_paths,
            "delete_old": delete_results,
        }
