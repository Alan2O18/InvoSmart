from pathlib import Path
from unittest.mock import patch

import numpy as np

from backend.processing.image_codec_adapter import ImageCodecAdapter


def test_codec_adapter_defaults_to_jpg():
    adapter = ImageCodecAdapter({})
    assert adapter.resolve_archival_extension() == "jpg"


def test_codec_adapter_jxl_falls_back_to_jpg_when_unavailable():
    import backend.processing.jxl_encoder_backend as jxl_mod

    with patch.object(jxl_mod, "is_jxl_available", return_value=False):
        adapter = ImageCodecAdapter({"archival_format": "jxl"})
        assert adapter.resolve_archival_extension() == "jpg"


def test_codec_adapter_jxl_resolves_to_jxl_when_available():
    import backend.processing.jxl_encoder_backend as jxl_mod

    with patch.object(jxl_mod, "is_jxl_available", return_value=True):
        adapter = ImageCodecAdapter({"archival_format": "jxl"})
        assert adapter.resolve_archival_extension() == "jxl"


def test_codec_adapter_write_fallback(tmp_path):
    adapter = ImageCodecAdapter({"archival_format": "webp"})
    image = np.zeros((20, 20, 3), dtype=np.uint8)

    output = tmp_path / "sample.webp"
    saved = adapter.write_archival_image(output, image)

    assert isinstance(saved, Path)
    assert saved.exists()
    assert saved.suffix in (".webp", ".jpg")


def test_codec_adapter_write_jxl_invokes_encoder(tmp_path):
    """When JXL encoder is available, write_archival_image calls encode_image_to_jxl."""
    import backend.processing.jxl_encoder_backend as jxl_mod

    image = np.zeros((10, 10, 3), dtype=np.uint8)
    output = tmp_path / "out.jxl"
    fake_encoded = output
    fake_encoded.touch()

    with patch.object(jxl_mod, "is_jxl_available", return_value=True), \
         patch.object(jxl_mod, "encode_image_to_jxl", return_value=fake_encoded) as mock_encode:

        adapter = ImageCodecAdapter({"archival_format": "jxl"})
        result = adapter.write_archival_image(output, image)

    mock_encode.assert_called_once()
    assert result == fake_encoded


def test_build_archival_path_preserves_dotted_stem_tokens(tmp_path):
    adapter = ImageCodecAdapter({"archival_format": "jpg"})

    stem1 = tmp_path / "114-2燕巢小宏遠一.1_split_0_1773989291000_abcd12"
    stem2 = tmp_path / "114-2燕巢小宏遠一.1_split_1_1773989291001_ef3456"

    p1 = adapter.build_archival_path(stem1)
    p2 = adapter.build_archival_path(stem2)

    assert p1.name.endswith(".jpg")
    assert p2.name.endswith(".jpg")
    assert p1.name != p2.name
    assert "split_0" in p1.name
    assert "split_1" in p2.name


