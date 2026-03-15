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
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level cache so the probe runs at most once per process.
_JXL_AVAILABLE: bool | None = None


def is_jxl_available() -> bool:
    """Return *True* if pyvips is importable and capable of writing JPEG-XL."""
    global _JXL_AVAILABLE
    if _JXL_AVAILABLE is not None:
        return _JXL_AVAILABLE

    try:
        import pyvips  # noqa: F401

        # Build a tiny 2×2 grayscale image and attempt a real JXL write so we
        # catch systems where pyvips is installed but JXL support was not compiled
        # in (e.g. a libvips built without libjxl).
        img = pyvips.Image.new_from_array([[128, 128], [128, 128]])
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jxl")
        os.close(tmp_fd)
        try:
            img.write_to_file(tmp_path)
            _JXL_AVAILABLE = os.path.getsize(tmp_path) > 0
        except Exception:
            _JXL_AVAILABLE = False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except ImportError:
        _JXL_AVAILABLE = False

    if not _JXL_AVAILABLE:
        logger.debug("JXL encoder (pyvips) is not available on this platform.")
    return _JXL_AVAILABLE


def encode_to_jxl(source_path: str, output_path: str, quality: int = 85) -> Path:
    """
    Encode *source_path* image to JPEG-XL at *output_path*.

    Requires pyvips with JXL support compiled in.
    Raises ``RuntimeError`` if the encoder is not available.

    Parameters
    ----------
    source_path:
        Absolute path to the source image (any format pyvips can read).
    output_path:
        Destination ``.jxl`` file path.
    quality:
        JXL quality level, 1–100.  Passed as ``Q`` to pyvips.

    Returns
    -------
    Path
        The written output file.
    """
    if not is_jxl_available():
        raise RuntimeError(
            "JXL encoder is not available.  "
            "Install pyvips with JXL support (libjxl) to enable JXL output."
        )
    import pyvips

    image = pyvips.Image.new_from_file(source_path, access="sequential")
    image.write_to_file(output_path, Q=quality)
    return Path(output_path)
