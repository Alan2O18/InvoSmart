"""Stamp extraction and background removal utilities."""

from __future__ import annotations

from typing import Iterable

import cv2
import numpy as np


class StampProcessor:
    """Generate transparent PNG crops from manually selected regions."""

    def __init__(self, min_area: int = 700, padding: int = 6):
        self.min_area = min_area
        self.padding = padding

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

    def extract_stamps(
        self,
        image: np.ndarray,
        selections: list[dict],
        mode: str = "red",
    ) -> list[dict]:
        """Extract multiple stamp crops from one image without touching filesystem or DB."""
        if image is None or image.size == 0:
            raise ValueError("image cannot be empty")
        if not isinstance(selections, list) or not selections:
            raise ValueError("selections must be a non-empty list")

        payload: list[dict] = []
        for idx, item in enumerate(selections):
            if not isinstance(item, dict):
                raise ValueError(f"selection {idx} must be an object")

            rect = (
                int(item.get("x", 0)),
                int(item.get("y", 0)),
                int(item.get("w", 0)),
                int(item.get("h", 0)),
            )
            cropped = self.crop_and_remove_background(image, rect=rect, mode=mode)
            payload.append(
                {
                    "image": cropped,
                    "name": str(item.get("name") or "").strip(),
                    "category": str(item.get("category") or "").strip(),
                    "group_name": item.get("group_name"),
                }
            )

        return payload

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

    def _build_binary_foreground_mask(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask
