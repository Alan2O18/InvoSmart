# Perspective Transform - 透視變換功能 (V10 重構版)
"""
透視變換模組：執行圖像的旋轉裁切和方向校正。

V10 重構：
- crop_by_rect: 使用 Direct Warp 直接從原圖裁切旋轉矩形區域
- fix_orientation: 使用投影輪廓 (Projection Profile) 校正文字方向
"""
import cv2
import numpy as np
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def order_points(pts: np.ndarray) -> np.ndarray:
    """
    對四個頂點進行空間排序：左上 (TL) -> 右上 (TR) -> 右下 (BR) -> 左下 (BL)。

    Args:
        pts: 形狀為 (4, 2) 的頂點陣列。

    Returns:
        排序後的頂點陣列，形狀為 (4, 2)，dtype 為 float32。
    """
    pts = np.array(pts, dtype="float32")
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


def crop_by_rect(image: np.ndarray, rect) -> np.ndarray:
    """
    使用 Direct Warp 從原圖中裁切出旋轉矩形區域。

    不旋轉整張大圖，而是直接將 minAreaRect 的 4 個頂點映射到正向矩形，
    僅輸出裁切後的小圖。

    Args:
        image: 原始圖像 (BGR)。
        rect: cv2.minAreaRect 的輸出 ((cx, cy), (w, h), angle)。

    Returns:
        裁切並轉正後的小圖。若裁切失敗則回傳空陣列。
    """
    box = cv2.boxPoints(rect)
    box = np.array(box, dtype="float32")

    # 排序頂點為 [TL, TR, BR, BL]
    ordered = order_points(box)

    # 計算邊長
    width = np.linalg.norm(ordered[1] - ordered[0])   # TL -> TR
    height = np.linalg.norm(ordered[2] - ordered[1])   # TR -> BR

    dst_w = int(round(width))
    dst_h = int(round(height))

    if dst_w <= 0 or dst_h <= 0:
        return np.array([])

    # 長邊校正 (Long-side Alignment):
    # 若 width > height (橫向)，位移頂點使輸出為直式
    if dst_w > dst_h:
        # 頂點位移: [TR, BR, BL, TL] 對應到 [TL, TR, BR, BL]
        src_pts = np.array([ordered[1], ordered[2], ordered[3], ordered[0]],
                           dtype="float32")
        dst_w, dst_h = dst_h, dst_w
    else:
        src_pts = ordered

    # 定義目標座標
    dst_pts = np.array([
        [0, 0],
        [dst_w, 0],
        [dst_w, dst_h],
        [0, dst_h],
    ], dtype="float32")

    # 計算透視變換矩陣並裁切
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)
    crop = cv2.warpPerspective(
        image, M, (dst_w, dst_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )

    return crop


def fix_orientation(image: np.ndarray) -> np.ndarray:
    """
    使用二值化投影輪廓 (Binarized Projection Profile) 校正文字方向。

    若偵測到文字行是垂直排列的 (var_v > var_h * 1.5)，則旋轉 90 度。
    無法偵測 180 度倒置 (已知限制)。

    Args:
        image: 裁切後的圖像 (BGR 或灰階)。

    Returns:
        方向校正後的圖像。
    """
    if image.size == 0:
        return image

    # 灰階
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Otsu 二值化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 計算黑色像素的水平/垂直投影變異數
    # 水平投影: 每行黑色像素數量的變異數 (文字水平排列時，行間留白大，變異數大)
    h_proj = np.sum(binary == 0, axis=1).astype(float)
    v_proj = np.sum(binary == 0, axis=0).astype(float)

    var_h = np.var(h_proj) if len(h_proj) > 0 else 0
    var_v = np.var(v_proj) if len(v_proj) > 0 else 0

    logger.debug(f"方向校正: var_h={var_h:.1f}, var_v={var_v:.1f}, "
                 f"ratio={var_v/var_h:.2f}" if var_h > 0 else
                 f"方向校正: var_h={var_h:.1f}, var_v={var_v:.1f}")

    # 若垂直投影變異數顯著大於水平，表示文字行是垂直排列的
    if var_h > 0 and var_v > var_h * 1.5:
        logger.info("偵測到文字垂直排列，旋轉 90 度")
        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)

    return image
