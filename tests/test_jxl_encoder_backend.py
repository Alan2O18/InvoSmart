"""Tests for backend/processing/jxl_encoder_backend.py"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import backend.processing.jxl_encoder_backend as jxl_mod
from backend.processing.jxl_encoder_backend import encode_to_jxl, is_jxl_available


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
            jxl_mod.encode_image_to_jxl(np.zeros((5, 5, 3), dtype=np.uint8), "/does/not/matter.jxl")


def test_encode_image_to_jxl_delegates_to_imagecodecs(tmp_path):
    """When encoder is available, encode_image_to_jxl calls imagecodecs.jpegxl_encode."""
    import numpy as np

    fake_imagecodecs = MagicMock()
    fake_imagecodecs.jpegxl_encode.return_value = b"fakejxl"

    output = tmp_path / "out.jxl"
    img = np.zeros((10, 10, 3), dtype=np.uint8)

    with patch("backend.processing.jxl_encoder_backend.is_jxl_available", return_value=True), \
         patch.dict("sys.modules", {"imagecodecs": fake_imagecodecs}):
        result = jxl_mod.encode_image_to_jxl(img, str(output))

    fake_imagecodecs.jpegxl_encode.assert_called_once()
    assert str(result) == str(output)
    assert output.exists()
    assert output.read_bytes() == b"fakejxl"


def test_encode_to_jxl_wrapper(tmp_path):
    """encode_to_jxl reads the file and delegates to encode_image_to_jxl."""
    import numpy as np
    output = tmp_path / "out.jxl"

    with patch("backend.utils.utils.cv_imread_chinese") as mock_imread, \
         patch.object(jxl_mod, "encode_image_to_jxl") as mock_encode:

        mock_imread.return_value = np.zeros((5, 5, 3))
        mock_encode.return_value = output

        result = encode_to_jxl("dummy.png", str(output))

        mock_imread.assert_called_once_with("dummy.png")
        mock_encode.assert_called_once()
        assert result == output

