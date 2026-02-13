# Contour Validator - 輪廓驗證功能 (V10 簡化版)
"""
輪廓驗證模組：提供頂點排序與長寬比驗證。

V10 重構：移除 validate_angles, refine_corners, check_parallelism。
保留 order_points 與 validate_aspect_ratio。
"""
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ContourValidator:
    """
    驗證輪廓的幾何屬性。V10 僅保留長寬比驗證。
    """

    def __init__(self, aspect_ratio_range: Tuple[float, float] = (0.1, 0.9)):
        """
        初始化驗證器。

        Args:
            aspect_ratio_range: 發票有效長寬比範圍 (短邊/長邊)
        """
        self.aspect_ratio_range = aspect_ratio_range

    def order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        對一個四邊形的四個頂點進行空間排序。

        順序為：左上 (TL) -> 右上 (TR) -> 右下 (BR) -> 左下 (BL)。

        Args:
            pts: 形狀為 (4, 2) 的頂點陣列。

        Returns:
            排序後的頂點陣列，形狀為 (4, 2)，dtype 為 float32。
        """
        rect = np.zeros((4, 2), dtype="float32")

        # 根據 y 座標排序，找出上方兩點與下方兩點
        y_sorted = pts[np.argsort(pts[:, 1]), :]
        top_points = y_sorted[:2, :]
        bottom_points = y_sorted[2:, :]

        # 上方兩點根據 x 排序 -> 左上、右上
        top_points = top_points[np.argsort(top_points[:, 0]), :]
        rect[0] = top_points[0]  # 左上
        rect[1] = top_points[1]  # 右上

        # 下方兩點根據 x 排序 -> 左下、右下
        bottom_points = bottom_points[np.argsort(bottom_points[:, 0]), :]
        rect[2] = bottom_points[1]  # 右下
        rect[3] = bottom_points[0]  # 左下

        return rect

    def validate_aspect_ratio(self, rect_wh: Tuple[float, float]) -> bool:
        """
        驗證矩形的長寬比是否符合一般發票的形狀。

        Args:
            rect_wh: 矩形的 (寬, 高)。

        Returns:
            若比例在 aspect_ratio_range 範圍內則返回 True。
        """
        w, h = rect_wh
        if w <= 0 or h <= 0:
            return False

        # 計算長寬比 (短邊 / 長邊)，使其與旋轉方向無關
        aspect_ratio = min(w, h) / max(w, h)

        return self.aspect_ratio_range[0] <= aspect_ratio <= self.aspect_ratio_range[1]
