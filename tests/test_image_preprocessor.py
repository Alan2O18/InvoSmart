"""Unit tests for image preprocessor module."""

import cv2
import numpy as np

from backend.processing.image_preprocessor import ImagePreprocessor


def test_preprocess_returns_2d_uint8_image():
    pre = ImagePreprocessor()
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (140, 100), (255, 255, 255), 2)

    result = pre.preprocess(image)

    assert result.shape == (120, 160)
    assert result.dtype == np.uint8


def test_preprocess_detects_edges_for_simple_shape():
    pre = ImagePreprocessor(canny_threshold1=20, canny_threshold2=60)
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    cv2.rectangle(image, (15, 15), (65, 65), (255, 255, 255), 2)

    result = pre.preprocess(image)

    # Edge + dilation should produce non-zero pixels.
    assert int(np.count_nonzero(result)) > 0


def test_find_contours_sorted_by_area_desc():
    pre = ImagePreprocessor()
    binary = np.zeros((200, 200), dtype=np.uint8)

    # Large rectangle.
    cv2.rectangle(binary, (20, 20), (150, 150), 255, -1)
    # Small rectangle.
    cv2.rectangle(binary, (160, 160), (190, 190), 255, -1)

    contours = pre.find_contours(binary)

    assert len(contours) >= 2
    areas = [cv2.contourArea(c) for c in contours]
    assert areas[0] >= areas[1]


def test_find_contours_empty_image_returns_empty_list():
    pre = ImagePreprocessor()
    binary = np.zeros((64, 64), dtype=np.uint8)

    contours = pre.find_contours(binary)

    assert contours == []
