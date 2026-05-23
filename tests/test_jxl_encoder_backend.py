"""Tests for backend/processing/jxl_encoder_backend.py"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import backend.processing.jxl_encoder_backend as jxl_mod
from backend.processing.jxl_encoder_backend import is_jxl_available


@pytest.fixture(autouse=True)
def reset_jxl_cache():
    """Reset the module-level availability cache between tests."""
    original = jxl_mod._JXL_AVAILABLE
    yield
    jxl_mod._JXL_AVAILABLE = original


def test_is_jxl_available_returns_bool():
    """is_jxl_available() must always return a plain bool."""
    result = is_jxl_available()
    assert isinstance(result, bool)


def test_is_jxl_available_result_is_cached():
    """Second call must not re-probe when result is already known."""
    jxl_mod._JXL_AVAILABLE = True
    result = is_jxl_available()
    assert result is True

    jxl_mod._JXL_AVAILABLE = False
    result = is_jxl_available()
    assert result is False


def test_is_jxl_unavailable_when_imagecodecs_missing():
    """must return False when imagecodecs is not installed."""
    jxl_mod._JXL_AVAILABLE = None
    with patch.dict("sys.modules", {"imagecodecs": None}):
        result = is_jxl_available()
    assert result is False


def test_encode_image_to_jxl_raises_when_unavailable():
    """encode_image_to_jxl must raise RuntimeError when encoder is absent."""
    import numpy as np

    with patch("backend.processing.jxl_encoder_backend.is_jxl_available", return_value=False):
        with pytest.raises(RuntimeError, match="JXL encoder"):
            jxl_mod.encode_image_to_jxl(np.zeros((5, 5, 3), dtype=np.uint8))


def test_encode_image_to_jxl_delegates_to_imagecodecs(tmp_path):
    """When encoder is available, encode_image_to_jxl calls imagecodecs.jpegxl_encode and returns bytes."""
    import numpy as np

    fake_imagecodecs = MagicMock()
    fake_imagecodecs.jpegxl_encode.return_value = b"fakejxl"

    img = np.zeros((10, 10, 3), dtype=np.uint8)

    with patch("backend.processing.jxl_encoder_backend.is_jxl_available", return_value=True), \
         patch.dict("sys.modules", {"imagecodecs": fake_imagecodecs}):
        result = jxl_mod.encode_image_to_jxl(img, lossless=True, effort=7)

    fake_imagecodecs.jpegxl_encode.assert_called_once()
    assert fake_imagecodecs.jpegxl_encode.call_args.kwargs.get("lossless") is True
    assert fake_imagecodecs.jpegxl_encode.call_args.kwargs.get("effort") == 7
    assert result == b"fakejxl"

