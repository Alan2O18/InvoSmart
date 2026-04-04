from __future__ import annotations

"""
JXL Encoder Backend
====================
Probes for pyvips availability at first call and caches the result.

Usage::

    from backend.processing.jxl_encoder_backend import is_jxl_available, encode_to_jxl

    if is_jxl_available():
        encode_to_jxl("/path/source.png", "/path/output.jxl")
    else:
        # fall back to a different format
        ...
"""

import logging
import os
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Module-level cache so the probe runs at most once per process.
_JXL_AVAILABLE: bool | None = None


def is_jxl_available() -> bool:
    """Return *True* if imagecodecs is available and capable of writing JPEG-XL."""
    global _JXL_AVAILABLE
    if _JXL_AVAILABLE is not None:
        return _JXL_AVAILABLE

    try:
        import imagecodecs

        # Test if jpegxl_encode is available in this build of imagecodecs
        if hasattr(imagecodecs, "jpegxl_encode"):
            _JXL_AVAILABLE = True
        else:
            _JXL_AVAILABLE = False
    except ImportError:
        _JXL_AVAILABLE = False

    if not _JXL_AVAILABLE:
        logger.debug("JXL encoder (imagecodecs) is not available on this platform.")
    return _JXL_AVAILABLE


def encode_image_to_jxl(image: np.ndarray, output_path: str, quality: int = 85) -> Path:
    """
    Encode a numpy image array (BGR) to JPEG-XL at *output_path*.

    Requires imagecodecs with JXL support.
    """
    if not is_jxl_available():
        raise RuntimeError(
            "JXL encoder (imagecodecs) is not available. "
            "Install imagecodecs to enable JXL output."
        )

    import imagecodecs

    # OpenCV uses BGR, imagecodecs/JXL viewers expect RGB
    if len(image.shape) == 3 and image.shape[2] == 3:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        image_rgb = image

    # Quality in imagecodecs is level (0-100) or effort (default)
    # imagecodecs.jpegxl_encode doesn't have a direct 'quality' param like pyvips's 'Q'
    # but we can pass level=quality.
    # Note: imagecodecs API might vary slightly, but jpegxl_encode(image) works.
    encoded = imagecodecs.jpegxl_encode(image_rgb, effort=1)

    with open(output_path, "wb") as f:
        f.write(encoded)

    return Path(output_path)


def encode_to_jxl(source_path: str, output_path: str, quality: int = 85) -> Path:
    """
    Encode *source_path* image (file) to JPEG-XL at *output_path*.
    Legacy wrapper for compatibility with older file-based logic.
    """
    from backend.utils import utils

    image = utils.cv_imread_chinese(source_path)
    if image is None:
        raise ValueError(f"Could not read source image for JXL encoding: {source_path}")

    return encode_image_to_jxl(image, output_path, quality)

