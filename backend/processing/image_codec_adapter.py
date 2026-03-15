from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

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
                "JXL archival requested but encoder (pyvips) is not available; falling back to JPG"
            )
            return "jpg"
        return fmt

    def build_archival_path(self, path_stem: Path) -> Path:
        ext = self.resolve_archival_extension()
        return path_stem.with_suffix(f".{ext}")

    def write_archival_image(self, output_path: Path, image) -> Path:
        if output_path.suffix.lower() == ".jxl":
            import os as _os
            import tempfile

            from backend.processing.jxl_encoder_backend import encode_to_jxl, is_jxl_available

            if is_jxl_available():
                tmp_fd, tmp_png = tempfile.mkstemp(suffix=".png")
                _os.close(tmp_fd)
                try:
                    ok = utils.cv_imwrite_chinese(tmp_png, image)
                    if ok:
                        return encode_to_jxl(tmp_png, str(output_path))
                    logger.warning("Intermediate PNG write failed for JXL encoding; falling back to JPG")
                finally:
                    try:
                        _os.unlink(tmp_png)
                    except OSError:
                        pass
            # JXL encoder unavailable — redirect to JPG
            output_path = output_path.with_suffix(".jpg")

        ok = utils.cv_imwrite_chinese(str(output_path), image)
        if ok:
            return output_path

        fallback = output_path.with_suffix(".jpg")
        logger.warning("Failed to write image as %s, retrying as JPG: %s", output_path.suffix, fallback)
        ok_fallback = utils.cv_imwrite_chinese(str(fallback), image)
        if not ok_fallback:
            raise IOError(f"Failed to write archival image: {fallback}")
        return fallback
