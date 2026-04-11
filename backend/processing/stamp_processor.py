"""Stamp detection and background removal utilities."""

from __future__ import annotations

from typing import Iterable

import cv2
import numpy as np


class StampProcessor:
    """Detect stamp candidates and generate transparent PNG crops."""

    def __init__(self, min_area: int = 700, padding: int = 6):
        self.min_area = min_area
        self.padding = padding

    def detect_stamps(self, image: np.ndarray, mode: str = "red") -> list[tuple[int, int, int, int]]:
        """Detect stamp boxes on an image using color or edge mode."""
        if image is None or image.size == 0:
            return []
        clean_mode = (mode or "red").strip().lower()
        if clean_mode not in {"red", "edge"}:
            raise ValueError("Unsupported detect mode")

        if clean_mode == "red":
            mask = self._build_red_mask(image)
        else:
            mask = self._build_edge_mask(image)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        raw_boxes: list[tuple[int, int, int, int]] = []
        img_h, img_w = image.shape[:2]

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w < 10 or h < 10:
                continue

            x0 = max(0, x - self.padding)
            y0 = max(0, y - self.padding)
            x1 = min(img_w, x + w + self.padding)
            y1 = min(img_h, y + h + self.padding)
            raw_boxes.append((x0, y0, x1 - x0, y1 - y0))

        return self._suppress_overlaps(raw_boxes)

    def crop_and_remove_background(
        self,
        image: np.ndarray,
        rect: Iterable[int],
        mode: str = "red",
    ) -> np.ndarray:
        """Crop one stamp and return BGRA image with transparent background."""
        if image is None or image.size == 0:
            raise ValueError("image cannot be empty")

        x, y, w, h = [int(v) for v in rect]
        if w <= 0 or h <= 0:
            raise ValueError("Invalid rectangle size")

        img_h, img_w = image.shape[:2]
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(img_w, x + w)
        y1 = min(img_h, y + h)
        if x0 >= x1 or y0 >= y1:
            raise ValueError("Rectangle is out of image bounds")

        crop = image[y0:y1, x0:x1]
        clean_mode = (mode or "red").strip().lower()
        if clean_mode == "red":
            foreground_mask = self._build_red_mask(crop)
        else:
            foreground_mask = self._build_binary_foreground_mask(crop)

        if int(np.count_nonzero(foreground_mask)) < max(20, int(foreground_mask.size * 0.01)):
            foreground_mask = self._build_binary_foreground_mask(crop)

        result = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = foreground_mask
        return result

    def _build_red_mask(self, image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_red_1 = np.array([0, 45, 45], dtype=np.uint8)
        upper_red_1 = np.array([12, 255, 255], dtype=np.uint8)
        lower_red_2 = np.array([165, 45, 45], dtype=np.uint8)
        upper_red_2 = np.array([180, 255, 255], dtype=np.uint8)

        mask1 = cv2.inRange(hsv, lower_red_1, upper_red_1)
        mask2 = cv2.inRange(hsv, lower_red_2, upper_red_2)
        mask = cv2.bitwise_or(mask1, mask2)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.medianBlur(mask, 5)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask

    def _build_edge_mask(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, threshold1=40, threshold2=140)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        mask = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

    def _build_binary_foreground_mask(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask

    def _suppress_overlaps(self, boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        if not boxes:
            return []

        sorted_boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        kept: list[tuple[int, int, int, int]] = []
        for box in sorted_boxes:
            if all(self._iou(box, existing) < 0.55 for existing in kept):
                kept.append(box)

        return sorted(kept, key=lambda b: (b[1], b[0]))

    def _iou(self, a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b

        ax2, ay2 = ax + aw, ay + ah
        bx2, by2 = bx + bw, by + bh

        inter_x1 = max(ax, bx)
        inter_y1 = max(ay, by)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        area_a = aw * ah
        area_b = bw * bh
        union = area_a + area_b - inter_area
        if union <= 0:
            return 0.0
        return inter_area / union
