import cv2
import numpy as np

from backend.processing.stamp_processor import StampProcessor


def test_detect_stamps_red_mode_finds_red_regions():
    image = np.full((280, 280, 3), 255, dtype=np.uint8)
    cv2.circle(image, (80, 90), 34, (0, 0, 220), -1)
    cv2.circle(image, (200, 180), 30, (0, 0, 210), -1)

    processor = StampProcessor(min_area=400)
    boxes = processor.detect_stamps(image, mode="red")

    assert len(boxes) >= 2
    for _, _, w, h in boxes:
        assert w > 0
        assert h > 0


def test_detect_stamps_edge_mode_finds_dark_stamp_outline():
    image = np.full((220, 220, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (50, 70), (170, 160), (20, 20, 20), thickness=5)

    processor = StampProcessor(min_area=300)
    boxes = processor.detect_stamps(image, mode="edge")

    assert len(boxes) >= 1
    x, y, w, h = boxes[0]
    assert x <= 55
    assert y <= 75
    assert w >= 100
    assert h >= 70


def test_crop_and_remove_background_outputs_alpha_channel():
    image = np.full((180, 180, 3), 255, dtype=np.uint8)
    cv2.circle(image, (90, 90), 42, (0, 0, 230), -1)

    processor = StampProcessor(min_area=300)
    cropped = processor.crop_and_remove_background(image, rect=(35, 35, 110, 110), mode="red")

    assert cropped.shape[2] == 4
    alpha = cropped[:, :, 3]
    assert int(np.count_nonzero(alpha == 0)) > 0
    assert int(np.count_nonzero(alpha > 0)) > 0
