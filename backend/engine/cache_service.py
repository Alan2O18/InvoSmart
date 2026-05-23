from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image, features

from backend.engine.image_codec_adapter import ImageCodecAdapter

logger = logging.getLogger(__name__)


class CacheService:
    """Preview/cache operations extracted from legacy FileOps cache mixin."""

    def __init__(self, project_repo, engine_ref):
        self.project_repo = project_repo
        self.engine = engine_ref

    def _engine_config(self) -> dict:
        config = getattr(self.engine, "config", {})
        return config if isinstance(config, dict) else {}

    def _image_semaphore(self):
        semaphore = getattr(self.engine, "image_processing_semaphore", None)
        return semaphore if isinstance(semaphore, asyncio.Semaphore) else None

    @asynccontextmanager
    async def _optional_semaphore(self):
        """Acquire image semaphore only when configured."""
        sem = self._image_semaphore()
        if sem is not None:
            async with sem:
                yield
            return
        yield

    def _get_preview_cache_dir(self, project_id: str) -> Path:
        root = self.project_repo._project_root(project_id)
        cache_dir = root / "快取影像" / "voucher_preview"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_preview_format(self) -> tuple[str, str, str]:
        configured = self._engine_config().get("processing_settings", {}).get(
            "preview_formats", ["avif", "webp", "jpeg"]
        )
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

    @staticmethod
    def _render_pdf_first_page_to_bgr(pdf_path: str) -> np.ndarray:
        import fitz

        with fitz.open(pdf_path) as doc:
            if doc.page_count <= 0:
                raise ValueError("PDF has no pages")
            page = doc[0]
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=zoom_matrix)

        img_data = pix.samples
        if pix.n == 4:
            img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.h, pix.w, 4)
            return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

        img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    async def ensure_preview_cache(self, project_id: str, image_path: str, max_width: int = 800) -> Optional[dict]:
        source = Path(image_path)
        if not source.exists() or not source.is_file():
            return None

        pil_format, extension, media_type = self._get_preview_format()
        cache_path = self._build_preview_cache_path(project_id, image_path, max_width, extension)
        if cache_path.exists():
            return {"path": str(cache_path), "media_type": media_type, "cache_hit": True}

        async with self._optional_semaphore():
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
                logger.warning("[FileOps] failed to delete preview cache %s: %s", cached, exc)

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
                logger.warning("[FileOps] cache cleanup failed for %s: %s", file_path, exc)

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
