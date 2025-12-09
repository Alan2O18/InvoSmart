# Perspective Transform - 透視變換功能
"""
透視變換模組：執行圖像的透視校正和去背處理。
"""
import cv2
import numpy as np
from typing import Optional


class PerspectiveTransformer:
    """
    執行透視變換和背景處理。
    """
    
    def __init__(self, contour_validator):
        """
        初始化透視變換器。
        
        Args:
            contour_validator: ContourValidator 實例，用於點排序
        """
        self.validator = contour_validator

    def transform(
        self,
        image: np.ndarray,
        pts: np.ndarray,
        padding: int,
        contour: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        執行透視變換，並支援去背 (Masking) 功能。
        
        Args:
            image: 原始圖像
            pts: 四邊形的四個頂點
            padding: 邊距像素
            contour: 原始輪廓（用於去背）
            
        Returns:
            變換後的圖像
        """
        rect = self.validator.order_points(pts)

        # 根據 padding 調整來源點位置
        if padding > 0:
            rect[0] += [-padding, -padding]
            rect[1] += [padding, -padding]
            rect[2] += [padding, padding]
            rect[3] += [-padding, padding]

        (tl, tr, br, bl) = rect

        # 計算目標圖片的寬高
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        if maxWidth <= 0 or maxHeight <= 0:
            return np.array([])

        # 定義目標圖片的四個角落
        dst = np.array(
            [
                [0, 0],
                [maxWidth - 1, 0],
                [maxWidth - 1, maxHeight - 1],
                [0, maxHeight - 1],
            ],
            dtype="float32",
        )

        # 計算變換矩陣
        M = cv2.getPerspectiveTransform(rect, dst)

        # 切割原始圖片
        warped_img = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        # 如果有提供輪廓，進行去背處理
        if contour is not None:
            return self._apply_mask(image, warped_img, contour, M, maxWidth, maxHeight)
        else:
            return warped_img
    
    def _apply_mask(
        self, 
        original: np.ndarray, 
        warped: np.ndarray, 
        contour: np.ndarray,
        transform_matrix: np.ndarray,
        width: int,
        height: int
    ) -> np.ndarray:
        """
        應用遮罩進行去背處理。
        
        Args:
            original: 原始圖像
            warped: 變換後的圖像
            contour: 輪廓
            transform_matrix: 變換矩陣
            width: 輸出寬度
            height: 輸出高度
            
        Returns:
            去背後的圖像
        """
        # 建立一個跟原圖一樣大的全黑遮罩
        mask = np.zeros(original.shape[:2], dtype=np.uint8)
        # 在遮罩上畫出發票的原始形狀 (白色填充)
        cv2.drawContours(mask, [contour], -1, 255, -1)

        # 對遮罩進行同樣的透視變換
        warped_mask = cv2.warpPerspective(mask, transform_matrix, (width, height))

        # 建立純白背景
        white_bg = np.ones_like(warped) * 255

        # 使用遮罩合成
        mask_inv = cv2.bitwise_not(warped_mask)

        # 前景(發票)
        img_fg = cv2.bitwise_and(warped, warped, mask=warped_mask)
        # 背景(補白)
        bg_fill = cv2.bitwise_and(white_bg, white_bg, mask=mask_inv)

        # 合併
        return cv2.add(img_fg, bg_fill)
