import cv2
import numpy as np
import pytest

from backend.processing.stamp_processor import StampProcessor


def _build_image() -> np.ndarray:
    image = np.full((220, 220, 3), 255, dtype=np.uint8)
    cv2.circle(image, (70, 80), 32, (0, 0, 220), -1)
    cv2.circle(image, (150, 150), 28, (0, 0, 210), -1)
    return image


def test_extract_stamps_returns_bgra_payloads():
    processor = StampProcessor(min_area=300)
    image = _build_image()

    payload = processor.extract_stamps(
        image,
        [
            {"x": 30, "y": 40, "w": 80, "h": 80, "name": "章一", "category": "社章", "group_name": "A"},
            {"x": 115, "y": 115, "w": 70, "h": 70, "name": "章二", "category": "職章", "group_name": None},
        ],
        mode="red",
    )

    assert len(payload) == 2
    assert payload[0]["name"] == "章一"
    assert payload[0]["category"] == "社章"
    assert payload[0]["image"].shape[2] == 4
    assert payload[1]["image"].shape[2] == 4


def test_extract_stamps_rejects_empty_selection():
    processor = StampProcessor()
    image = _build_image()

    with pytest.raises(ValueError):
        processor.extract_stamps(image, [], mode="red")
