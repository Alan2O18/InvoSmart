from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from backend.utils import utils

logger = logging.getLogger(__name__)


class ImageCodecAdapter:
    """
    Pluggable codec selector for archival image writes.

    Current behavior is conservative: defaults to JPG and only changes format
    when explicitly configured. Requested JXL is accepted as intent but falls
    back to JPG unless an external encoder is integrated in a later phase.
    """

    def __init__(self, processing_settings: dict[str, Any] | None = None):
        self.processing_settings = processing_settings or {}

    def read_image(self, path: str | Path) -> np.ndarray:
        """Read an image from any supported format and return OpenCV-style ndarray (BGR)."""
        return utils.cv_imread_chinese(str(path))

    def read_image_pil(self, path: str | Path) -> Image.Image:
        """Read an image from any supported format and return PIL RGB image."""
        source = Path(path)
        if source.suffix.lower() == ".jxl":
            import imagecodecs

            arr = imagecodecs.jpegxl_decode(source.read_bytes())
            return Image.fromarray(arr).convert("RGB")

        with Image.open(source) as image:
            return image.convert("RGB")

    def preferred_archival_format(self) -> str:
        fmt = str(self.processing_settings.get("archival_format", "jpg")).strip().lower()
        if fmt in ("jpg", "jpeg", "png", "webp", "jxl"):
            return fmt
        return "jpg"

    def resolve_archival_extension(self) -> str:
        fmt = self.preferred_archival_format()
        if fmt == "jpeg":
            return "jpg"
        if fmt == "jxl":
            from backend.processing.jxl_encoder_backend import is_jxl_available

            if is_jxl_available():
                return "jxl"
            logger.warning(
                "JXL archival requested but encoder (imagecodecs) is not available; falling back to JPG"
            )
            return "jpg"
        return fmt

    def build_archival_path(self, path_stem: Path) -> Path:
        ext = self.resolve_archival_extension()
        # path_stem can include dots from source names (e.g. "foo.1_split_0_...").
        # Using with_suffix() would treat trailing segments as a suffix and collapse
        # different split outputs into the same filename.
        return path_stem.parent / f"{path_stem.name}.{ext}"

    def _jxl_encode_options(self) -> dict[str, Any]:
        block = self.processing_settings.get("jxl_encode", {})
        if not isinstance(block, dict):
            block = {}

        lossless_raw = block.get(
            "lossless",
            self.processing_settings.get("jxl_lossless", False),
        )
        effort_raw = block.get(
            "effort",
            self.processing_settings.get("jxl_effort", 1),
        )

        try:
            effort = int(effort_raw)
        except (TypeError, ValueError):
            effort = 1
        effort = max(1, min(9, effort))

        return {
            "lossless": bool(lossless_raw),
            "effort": effort,
        }

    def write_archival_image(
        self,
        output_path: Path,
        image,
        fallback_suffix: str = ".jpg",
        max_retries: int = 3,
    ) -> Path:
        if output_path.suffix.lower() == ".jxl":
            from backend.processing.jxl_encoder_backend import encode_image_to_jxl, is_jxl_available

            if is_jxl_available():
                jxl_options = self._jxl_encode_options()
                last_err: Exception | None = None
                for attempt in range(1, max_retries + 1):
                    try:
                        # Use direct numpy-to-jxl encoding (no intermediate PNG), return raw bytes and write to disk
                        encoded_bytes = encode_image_to_jxl(
                            image,
                            lossless=jxl_options["lossless"],
                            effort=jxl_options["effort"],
                        )
                        output_path.write_bytes(encoded_bytes)
                        return output_path
                    except Exception as exc:
                        last_err = exc
                        logger.warning(
                            "JXL encode attempt %d/%d failed: %s",
                            attempt,
                            max_retries,
                            exc,
                        )

                # All retries exhausted — fall back to original format
                logger.warning(
                    "JXL encoding failed after %d attempts (last error: %s); "
                    "saving in original format (%s)",
                    max_retries,
                    last_err,
                    fallback_suffix,
                )

            # JXL encoder unavailable or retries exhausted — use original format
            output_path = output_path.with_suffix(fallback_suffix)

        ok = utils.cv_imwrite_chinese(str(output_path), image)
        if ok:
            return output_path

        # Last-resort fallback: try the caller-specified original format
        fallback = output_path.with_suffix(fallback_suffix)
        if fallback != output_path:
            logger.warning(
                "Failed to write image as %s, retrying as %s: %s",
                output_path.suffix,
                fallback_suffix,
                fallback,
            )
            ok_fallback = utils.cv_imwrite_chinese(str(fallback), image)
            if ok_fallback:
                return fallback

        raise IOError(f"Failed to write archival image: {output_path}")
