"""Backward-compatible FileOps facade.

This shim keeps the historical `backend.engine.file_ops` import path working
after the v0.0.18 service split. Runtime code uses `ImageService` directly,
while legacy tests and scripts can continue importing `FileOps`.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from backend.processing.image_codec_adapter import ImageCodecAdapter
from backend.utils import utils

from .cache_service import CacheService
from .file_service import FileService
from .image_service import ImageService

logger = logging.getLogger(__name__)

# Keep these module attributes available for legacy patch paths in tests.
_LEGACY_TEST_EXPORTS = (time, uuid, ImageCodecAdapter)


class FileOps(ImageService):
    """Compatibility wrapper over `ImageService`.

    Keeps constructor/signature and helper statics expected by legacy tests.
    """

    def __init__(self, project_repo, receipt_splitter, engine_ref):
        file_service = getattr(engine_ref, "file_service", None)
        if not isinstance(file_service, FileService):
            file_service = FileService(project_repo)

        cache_service = getattr(engine_ref, "cache_service", None)
        if not isinstance(cache_service, CacheService):
            cache_service = CacheService(project_repo, engine_ref)

        super().__init__(
            project_repo,
            receipt_splitter,
            engine_ref,
            file_service=file_service,
            cache_service=cache_service,
        )

    @staticmethod
    def _render_preview(source_path: str, cache_path: str, pil_format: str, max_width: int):
        return CacheService._render_preview(source_path, cache_path, pil_format, max_width)

    @staticmethod
    def _render_pdf_first_page_to_bgr(pdf_path: str) -> np.ndarray:
        return CacheService._render_pdf_first_page_to_bgr(pdf_path)

    async def rotate_image(self, project_id: str, filename: str, angle: int = 90):
        """Legacy-compatible rotate reset behavior used by older tests.

        New runtime logic lives in `ImageService.rotate_image`; this shim keeps
        the historical update payload (`vlm_result_json/manual_json_text` clears).
        """
        try:
            root = self.project_repo._project_root(project_id)
            safe_filename = Path(filename).name
            image_path = root / "分割發票" / safe_filename
            if not image_path.exists():
                raise FileNotFoundError(f"Image {safe_filename} not found in splits")

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

            write_ok = await asyncio.to_thread(utils.cv_imwrite_chinese, str(image_path), image)
            if not write_ok:
                raise IOError(f"Failed to write rotated image: {image_path}")
            self.invalidate_preview_cache(project_id, str(image_path))
            try:
                max_width = self._thumb_max_width()
                await self.ensure_preview_cache(project_id, str(image_path), max_width=max_width)
            except Exception as preview_err:  # noqa: BLE001
                logger.warning("[FileOps] preview cache rebuild failed for %s: %s", image_path, preview_err)

            job_repo = self.engine.get_job_repo(project_id)
            jobs = await job_repo.list_jobs()
            rotated_abs_path = str(image_path.resolve())
            reset_job_ids = []
            for job in jobs:
                job_path = str(job.get("image_path") or "")
                if not job_path:
                    continue
                job_path_abs = str(Path(job_path).resolve())
                if job_path_abs == rotated_abs_path or Path(job_path).name == safe_filename:
                    await job_repo.update_job(
                        job["job_id"],
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
            logger.error("Error rotating image %s: %s", filename, e)
            raise e
