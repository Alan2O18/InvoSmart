# Hough Corner Detector - 基於線段偵測的角點精確定位
"""
使用 Hough 線段偵測找到發票邊緣線，再計算交點得到精確角落。
這比 approxPolyDP 更精確，因為它基於實際邊緣線而非輪廓逼近。
"""
import cv2
import numpy as np
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class HoughCornerDetector:
    """
    使用 Hough 線段偵測計算精確角點。
    
    相比 approxPolyDP：
    - 更精確：基於實際邊緣線計算交點
    - 更穩定：不受輪廓噪點影響
    """
    
    def __init__(self, 
                 rho: float = 1,
                 theta: float = np.pi / 180,
                 threshold: int = 50,
                 min_line_length: int = 100,
                 max_line_gap: int = 10):
        """
        Args:
            rho: 距離解析度 (像素)
            theta: 角度解析度 (弧度)
            threshold: 累加器閾值
            min_line_length: 最小線段長度
            max_line_gap: 允許的最大線段間隙
        """
        self.rho = rho
        self.theta = theta
        self.threshold = threshold
        self.min_line_length = min_line_length
        self.max_line_gap = max_line_gap
    
    def detect_corners(self, 
                       image: np.ndarray, 
                       contour: np.ndarray) -> Optional[np.ndarray]:
        """
        在給定輪廓區域內偵測精確角點。
        
        Args:
            image: 原始圖像
            contour: 粗略輪廓 (用於限制搜索區域)
            
        Returns:
            精確的四個角點，形狀 (4, 2)，若失敗返回 None
        """
        # 1. 建立遮罩，只處理輪廓區域
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        
        # 擴大遮罩區域一點點
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # 2. 灰階 + 邊緣偵測
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # 只保留遮罩區域
        gray_masked = cv2.bitwise_and(gray, gray, mask=mask)
        
        # 雙邊濾波去噪
        gray_filtered = cv2.bilateralFilter(gray_masked, 9, 75, 75)
        
        # Canny 邊緣偵測
        edges = cv2.Canny(gray_filtered, 50, 150)
        
        # 3. Hough 線段偵測
        lines = cv2.HoughLinesP(
            edges,
            self.rho,
            self.theta,
            self.threshold,
            minLineLength=self.min_line_length,
            maxLineGap=self.max_line_gap
        )
        
        if lines is None or len(lines) < 4:
            logger.debug("Hough 線段不足，無法計算角點")
            return None
        
        # 4. 將線段分類為水平/垂直
        horizontal_lines = []
        vertical_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            
            # 水平線：角度接近 0 或 180
            if abs(angle) < 30 or abs(angle) > 150:
                horizontal_lines.append(line[0])
            # 垂直線：角度接近 90 或 -90
            elif 60 < abs(angle) < 120:
                vertical_lines.append(line[0])
        
        if len(horizontal_lines) < 2 or len(vertical_lines) < 2:
            logger.debug(f"線段分類不足: H={len(horizontal_lines)}, V={len(vertical_lines)}")
            return None
        
        # 5. 合併相近的線段
        top_line = self._get_extreme_line(horizontal_lines, 'top')
        bottom_line = self._get_extreme_line(horizontal_lines, 'bottom')
        left_line = self._get_extreme_line(vertical_lines, 'left')
        right_line = self._get_extreme_line(vertical_lines, 'right')
        
        if any(l is None for l in [top_line, bottom_line, left_line, right_line]):
            logger.debug("無法確定四條邊界線")
            return None
        
        # 6. 計算四個交點
        corners = []
        corners.append(self._line_intersection(top_line, left_line))     # 左上
        corners.append(self._line_intersection(top_line, right_line))    # 右上
        corners.append(self._line_intersection(bottom_line, right_line)) # 右下
        corners.append(self._line_intersection(bottom_line, left_line))  # 左下
        
        if any(c is None for c in corners):
            logger.debug("線段交點計算失敗")
            return None
        
        result = np.array(corners, dtype=np.float32)
        
        # 驗證：確保角點在圖片範圍內
        h, w = image.shape[:2]
        if not all(0 <= c[0] <= w and 0 <= c[1] <= h for c in result):
            logger.debug("角點超出圖片範圍")
            return None
        
        logger.debug(f"Hough 角點偵測成功: {result.tolist()}")
        return result
    
    def _get_extreme_line(self, 
                          lines: List[np.ndarray], 
                          position: str) -> Optional[Tuple[int, int, int, int]]:
        """
        從一組線段中取得最上/下/左/右的線段。
        
        Args:
            lines: 線段列表
            position: 'top', 'bottom', 'left', 'right'
        """
        if not lines:
            return None
        
        if position == 'top':
            # Y 座標最小的線段
            return min(lines, key=lambda l: (l[1] + l[3]) / 2)
        elif position == 'bottom':
            # Y 座標最大的線段
            return max(lines, key=lambda l: (l[1] + l[3]) / 2)
        elif position == 'left':
            # X 座標最小的線段
            return min(lines, key=lambda l: (l[0] + l[2]) / 2)
        elif position == 'right':
            # X 座標最大的線段
            return max(lines, key=lambda l: (l[0] + l[2]) / 2)
        return None
    
    def _line_intersection(self, 
                           line1: np.ndarray, 
                           line2: np.ndarray) -> Optional[Tuple[float, float]]:
        """
        計算兩條線段的交點。
        
        使用參數式直線方程求解。
        """
        x1, y1, x2, y2 = line1
        x3, y3, x4, y4 = line2
        
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        
        if abs(denom) < 1e-10:
            # 平行線，無交點
            return None
        
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        
        return (px, py)
