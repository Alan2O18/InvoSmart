from __future__ import annotations

import asyncio
import base64
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

from backend.database.models import Stamp
from backend.processing.stamp_processor import StampProcessor
from backend.repositories.stamp_repository import StampRepository


class StampService:
    """Service layer orchestrating stamp decode/process/store/repository flow."""

    def __init__(
        self,
        processor: StampProcessor | None = None,
        project_root: Path | None = None,
        storage_relative_dir: Path | None = None,
    ):
        self.processor = processor or StampProcessor()
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.storage_relative_dir = storage_relative_dir or (Path("backend") / "data" / "stamps")

    @property
    def storage_dir(self) -> Path:
        return self.project_root / self.storage_relative_dir

    def _ensure_storage_dir(self) -> Path:
        storage = self.storage_dir
        storage.mkdir(parents=True, exist_ok=True)
        return storage

    @staticmethod
    def decode_upload_image(raw_bytes: bytes) -> np.ndarray:
        if not raw_bytes:
            raise ValueError("Uploaded image is empty")

        np_bytes = np.frombuffer(raw_bytes, dtype=np.uint8)
        image = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Cannot decode uploaded image")
        return image

    def _write_stamp_image(self, image: np.ndarray) -> Path:
        filename = f"stamp_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png"
        output_path = self.storage_dir / filename
        if not cv2.imwrite(str(output_path), image):
            raise RuntimeError(f"Failed to write stamp image: {filename}")
        return output_path

    def _to_stored_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root)).replace("\\", "/")
        except ValueError:
            return str(path)

    @staticmethod
    def build_preview_base64(image: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> str | None:
        preview = image.copy()
        for x, y, w, h in boxes:
            cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 255), 2)
        ok, encoded = cv2.imencode(".png", preview)
        if not ok:
            return None
        return base64.b64encode(encoded.tobytes()).decode("ascii")

    async def register_stamps(
        self,
        raw_bytes: bytes,
        selections: list[dict],
        mode: str,
        repo: StampRepository,
    ) -> list[dict]:
        image = await asyncio.to_thread(self.decode_upload_image, raw_bytes)
        extracted = await asyncio.to_thread(self.processor.extract_stamps, image, selections, mode)
        await asyncio.to_thread(self._ensure_storage_dir)

        written_files: list[Path] = []
        entities: list[Stamp] = []
        try:
            for item in extracted:
                saved_path = await asyncio.to_thread(self._write_stamp_image, item["image"])
                written_files.append(saved_path)
                entities.append(
                    Stamp(
                        name=str(item.get("name") or "").strip(),
                        category=str(item.get("category") or "").strip(),
                        group_name=item.get("group_name"),
                        image_path=self._to_stored_path(saved_path),
                        created_at=time.time(),
                    )
                )

            return await repo.create_stamps(entities)
        except Exception:
            for file_path in written_files:
                await asyncio.to_thread(file_path.unlink, missing_ok=True)
            raise
