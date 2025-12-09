# Contour Validator - 輪廓驗證功能
"""
輪廓驗證模組：驗證檢測到的輪廓是否符合發票的幾何特徵。
"""
import numpy as np
from typing import Tuple


class ContourValidator:
    """
    驗證輪廓的幾何屬性，包括角度和長寬比。
    """
    
    def __init__(self, angle_tolerance_deg: int = 3, 
                 aspect_ratio_range: Tuple[float, float] = (0.1, 0.9)):
        """
        初始化驗證器。
        
        Args:
            angle_tolerance_deg: 判定矩形時，內角與 90 度的最大容忍誤差（度）
            aspect_ratio_range: 發票有效長寬比範圍 (短邊/長邊)
        """
        self.angle_tolerance_deg = angle_tolerance_deg
        self.aspect_ratio_range = aspect_ratio_range

    def order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        對一個四邊形的四個頂點進行空間排序。

        順序為：左上 (TL) -> 右上 (TR) -> 右下 (BR) -> 左下 (BL)。
        此排序對於透視變換 (Perspective Transform) 至關重要。

        Args:
            pts: 形狀為 (4, 2) 的頂點陣列。

        Returns:
            排序後的頂點陣列，形狀為 (4, 2)，dtype 為 float32。
        """
        rect = np.zeros((4, 2), dtype="float32")

        # 1. 根據 y 座標排序，找出上方兩點與下方兩點
        y_sorted = pts[np.argsort(pts[:, 1]), :]
        top_points = y_sorted[:2, :]
        bottom_points = y_sorted[2:, :]

        # 2. 上方兩點根據 x 排序 -> 左上、右上
        top_points = top_points[np.argsort(top_points[:, 0]), :]
        rect[0] = top_points[0]  # 左上
        rect[1] = top_points[1]  # 右上

        # 3. 下方兩點根據 x 排序 -> 左下、右下
        bottom_points = bottom_points[np.argsort(bottom_points[:, 0]), :]
        rect[2] = bottom_points[1]  # 右下
        rect[3] = bottom_points[0]  # 左下

        return rect

    def validate_angles(self, pts: np.ndarray) -> bool:
        """
        驗證四邊形的四個內角是否接近 90 度。

        這是為了區分「真正的發票（通常是矩形）」與「背景雜訊產生的隨機四邊形」。

        Args:
            pts: 四邊形的四個頂點。

        Returns:
            若所有角度都在容忍範圍內 (90 ± tolerance) 則返回 True。
        """
        if pts.shape[0] != 4:
            return False

        p = self.order_points(pts)
        tl, tr, br, bl = p[0], p[1], p[2], p[3]

        # 定義四個邊的向量
        v_tl_tr = tr - tl
        v_tl_bl = bl - tl
        v_tr_tl = tl - tr
        v_tr_br = br - tr
        v_br_tr = tr - br
        v_br_bl = bl - br
        v_bl_br = br - bl
        v_bl_tl = tl - bl

        def angle_between_vectors(v1, v2):
            """計算兩向量夾角 (度)"""
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            if norm_v1 < 1e-6 or norm_v2 < 1e-6:
                return 180.0
            dot_product = np.dot(v1, v2)
            cos_angle = np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0)
            return np.degrees(np.arccos(cos_angle))

        angles = [
            angle_between_vectors(v_tl_tr, v_tl_bl),  # 左上角
            angle_between_vectors(v_tr_tl, v_tr_br),  # 右上角
            angle_between_vectors(v_br_tr, v_br_bl),  # 右下角
            angle_between_vectors(v_bl_br, v_bl_tl),  # 左下角
        ]

        min_angle = 90 - self.angle_tolerance_deg
        max_angle = 90 + self.angle_tolerance_deg

        return all(min_angle < angle < max_angle for angle in angles)

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
