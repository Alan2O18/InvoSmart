import cv2
import numpy as np
import pytest

from backend.processing.stamp_processor import StampProcessor


def test_extract_stamps_manual_boxes_returns_payload():
    image = np.full((220, 220, 3), 255, dtype=np.uint8)
    cv2.circle(image, (80, 90), 34, (0, 0, 220), -1)
    cv2.circle(image, (160, 160), 28, (20, 20, 20), -1)

    processor = StampProcessor(min_area=300)
    payload = processor.extract_stamps(
        image,
        [
            {"x": 40, "y": 50, "w": 90, "h": 90, "name": "red", "category": "社團"},
            {"x": 125, "y": 125, "w": 70, "h": 70, "name": "dark", "category": "稽核"},
        ],
        mode="edge",
    )

    assert len(payload) == 2
    assert payload[0]["name"] == "red"
    assert payload[1]["category"] == "稽核"
    assert payload[0]["image"].shape[2] == 4


def test_crop_and_remove_background_outputs_alpha_channel():
    image = np.full((180, 180, 3), 255, dtype=np.uint8)
    cv2.circle(image, (90, 90), 42, (0, 0, 230), -1)

    processor = StampProcessor(min_area=300)
    cropped = processor.crop_and_remove_background(image, rect=(35, 35, 110, 110), mode="red")

    assert cropped.shape[2] == 4
    alpha = cropped[:, :, 3]
    assert int(np.count_nonzero(alpha == 0)) > 0
    assert int(np.count_nonzero(alpha > 0)) > 0


def test_extract_stamps_rejects_empty_selection():
    processor = StampProcessor(min_area=300)
    image = np.full((100, 100, 3), 255, dtype=np.uint8)

    with pytest.raises(ValueError):
        processor.extract_stamps(image, [], mode="red")
