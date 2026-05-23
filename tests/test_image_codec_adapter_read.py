import sys
import types
from unittest.mock import patch

import numpy as np
from PIL import Image

from backend.engine.image_codec_adapter import ImageCodecAdapter
from backend.utils.utils import cv_imread_chinese


def test_read_image_delegates_to_utils_cv_imread_chinese():
    adapter = ImageCodecAdapter({})
    fake_image = np.zeros((8, 8, 3), dtype=np.uint8)

    with patch("backend.engine.image_codec_adapter.utils.cv_imread_chinese", return_value=fake_image) as mock_read:
        result = adapter.read_image("sample.jpg")

    mock_read.assert_called_once_with("sample.jpg")
    assert result is fake_image


def test_read_image_pil_decodes_jxl_with_imagecodecs(tmp_path):
    source = tmp_path / "sample.jxl"
    source.write_bytes(b"fake-jxl")

    rgb = np.zeros((4, 5, 3), dtype=np.uint8)
    rgb[..., 0] = 255  # red
    fake_module = types.SimpleNamespace(jpegxl_decode=lambda _raw: rgb)

    with patch.dict(sys.modules, {"imagecodecs": fake_module}):
        image = ImageCodecAdapter({}).read_image_pil(source)

    assert image.mode == "RGB"
    assert image.size == (5, 4)
    assert image.getpixel((0, 0)) == (255, 0, 0)


def test_read_image_pil_non_jxl_uses_pillow(tmp_path):
    source = tmp_path / "sample.jpg"
    Image.new("RGB", (9, 7), color=(10, 20, 30)).save(source)

    image = ImageCodecAdapter({}).read_image_pil(source)

    assert image.mode == "RGB"
    assert image.size == (9, 7)


def test_cv_imread_chinese_decodes_jxl_to_bgr(tmp_path):
    source = tmp_path / "sample.jxl"
    source.write_bytes(b"fake-jxl")

    rgb = np.array([[[10, 20, 30]]], dtype=np.uint8)
    fake_module = types.SimpleNamespace(jpegxl_decode=lambda _raw: rgb)

    with patch.dict(sys.modules, {"imagecodecs": fake_module}):
        image = cv_imread_chinese(str(source))

    assert image.shape == (1, 1, 3)
    assert image.dtype == np.uint8
    assert image[0, 0].tolist() == [30, 20, 10]
