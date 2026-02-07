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
        # 使用 INTER_CUBIC 插值減少鋸齒和變形
        # 使用 BORDER_REPLICATE 避免黑邊
        warped_img = cv2.warpPerspective(
            image, M, (maxWidth, maxHeight),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )

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

    def deskew_image(self, image: np.ndarray) -> np.ndarray:
        """
        自動偵測並校正圖像傾斜角度。
        
        使用 Hough 線段分析文字行方向，計算需要旋轉的角度。
        
        Args:
            image: 透視變換後的圖像
            
        Returns:
            旋轉校正後的圖像
        """
        if image.size == 0:
            return image
        
        # 灰階
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 偵測傾斜角度
        angle = self._detect_skew_angle(gray)
        
        if abs(angle) < 0.5:  # 小於 0.5 度不需要校正
            return image
        
        # 執行旋轉
        return self._rotate_image(image, angle)
    
    def _detect_skew_angle(self, gray: np.ndarray) -> float:
        """
        使用 Hough 線段偵測計算圖像傾斜角度。
        
        Args:
            gray: 灰階圖像
            
        Returns:
            傾斜角度 (度)，正值表示順時針傾斜
        """
        # 邊緣偵測
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # 膨脹讓線段更連續
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # Hough 線段偵測
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, 
            threshold=100, 
            minLineLength=gray.shape[1] // 8,  # 至少 1/8 圖寬
            maxLineGap=10
        )
        
        if lines is None or len(lines) == 0:
            return 0.0
        
        # 收集接近水平的線段角度
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 == 0:
                continue
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            
            # 只考慮接近水平的線段 (±45度)
            if abs(angle) < 45:
                angles.append(angle)
        
        if not angles:
            return 0.0
        
        # 取中位數角度（比平均值更穩健）
        median_angle = np.median(angles)
        
        return median_angle
    
    def _rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """
        以圖像中心旋轉指定角度。
        
        Args:
            image: 原始圖像
            angle: 旋轉角度 (度)，正值逆時針
            
        Returns:
            旋轉後的圖像（保持完整內容）
        """
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        
        # 計算旋轉矩陣（負角度因為我們要校正傾斜，即反向旋轉）
        M = cv2.getRotationMatrix2D(center, -angle, 1.0)
        
        # 計算新的圖像尺寸以容納旋轉後的內容
        cos = abs(M[0, 0])
        sin = abs(M[0, 1])
        new_w = int(h * sin + w * cos)
        new_h = int(h * cos + w * sin)
        
        # 調整旋轉矩陣的平移部分
        M[0, 2] += (new_w - w) / 2
        M[1, 2] += (new_h - h) / 2
        
        # 執行旋轉，使用白色背景
        rotated = cv2.warpAffine(
            image, M, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255)
        )
        
        return rotated
