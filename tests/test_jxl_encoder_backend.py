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


def test_is_jxl_unavailable_when_pyvips_missing():
    """must return False when pyvips is not installed."""
    jxl_mod._JXL_AVAILABLE = None
    with patch.dict("sys.modules", {"pyvips": None}):
        result = is_jxl_available()
    assert result is False


def test_encode_to_jxl_raises_when_unavailable():
    """encode_to_jxl must raise RuntimeError when encoder is absent."""
    with patch("backend.processing.jxl_encoder_backend.is_jxl_available", return_value=False):
        with pytest.raises(RuntimeError, match="JXL encoder"):
            encode_to_jxl("/does/not/matter.png", "/does/not/matter.jxl")


def test_encode_to_jxl_delegates_to_pyvips(tmp_path):
    """When encoder is available, encode_to_jxl calls pyvips write_to_file."""
    fake_img = MagicMock()
    fake_pyvips = MagicMock()
    fake_pyvips.Image.new_from_file.return_value = fake_img

    output = tmp_path / "out.jxl"

    with patch("backend.processing.jxl_encoder_backend.is_jxl_available", return_value=True), \
         patch.dict("sys.modules", {"pyvips": fake_pyvips}):
        result = encode_to_jxl(str(tmp_path / "src.png"), str(output))

    fake_img.write_to_file.assert_called_once_with(str(output), Q=85)
    assert str(result) == str(output)

