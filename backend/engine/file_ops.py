import os
import time
import shutil
import logging
import asyncio
import uuid
import cv2
from pathlib import Path
from typing import Optional
from PIL import Image, features
from backend.processing.image_codec_adapter import ImageCodecAdapter
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

                if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
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
                if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
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

            for file_path in files:
                filename = Path(file_path).name
                if type == "split":
                    stem = Path(filename).stem
                    suffix = Path(filename).suffix or ".jpg"
                    unique_token = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
                    filename = f"{stem}_split_manual_{unique_token}{suffix}"

                dest_path = target_dir / filename
                shutil.copy(file_path, dest_path)

                if type == "split":
                    # Enqueue with ABSOLUTE path
                    abs_path = str(dest_path.resolve())
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
                            source_format=dest_path.suffix.lstrip(".") or "jpg",
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
        with Image.open(source_path) as image:
            image = image.convert("RGB")
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

    async def add_pdf_files(self, project_id: str, files: list[str]):
        """
        ??銝??PDF 瑼???
        撠?PDF 摮??憪撓?乓?銝血?蝚砌??葡?? JPG 摮???脩蟡具?
        ?箏?撱箇? Job ??蝬? source_pdf_path ??PDF ??頝臬???
        """
        try:
            import fitz
            root = self.project_repo._project_root(project_id)
            raw_dir = root / "原始輸入"
            split_dir = root / "分割發票"

            raw_dir.mkdir(parents=True, exist_ok=True)
            split_dir.mkdir(parents=True, exist_ok=True)

            for file_path in files:
                # 1. 撠??喟? PDF 摮?
                filename = Path(file_path).name
                dest_pdf_path = raw_dir / filename
                shutil.copy(file_path, dest_pdf_path)

                # 2. ?瑕?蝚砌??? VLM (Gemini) 霅??
                try:
                    doc = fitz.open(str(dest_pdf_path))
                    page = doc[0]
                    # 閫??摨血???(matrix), 1.0 => 72 DPI, 2.0 => 144 DPI (?踹?摮云蝟?
                    zoom_matrix = fitz.Matrix(2.0, 2.0)
                    pix = page.get_pixmap(matrix=zoom_matrix)

                    ts = int(time.time())
                    # ?踹??舀???銴?撠?.pdf ?? _page0_xxx.jpg
                    stem = Path(filename).stem
                    jpg_filename = f"{stem}_page0_{ts}.jpg"
                    dest_jpg_path = split_dir / jpg_filename

                    pix.save(str(dest_jpg_path))
                    doc.close()

                    # 3. 撠?PDF ?洵銝???臬????Job 銝?
                    await self.engine.enqueue_pdf_upload(
                        project_id,
                        str(dest_pdf_path.resolve()),
                        str(dest_jpg_path.resolve())
                    )
                    logger.debug(f"[FileOps] ???? PDF {filename} ??閬賢? {jpg_filename}")
                except Exception as ex:
                    logger.error(f"[FileOps] 頧? PDF 蝚砌??仃?? {ex}")
                    # 憒?憭望?撠曹?撱箇? Job

            return {"status": "added"}
        except Exception as e:
            logger.error(f"Error adding pdf files to {project_id}: {e}")
            raise e
