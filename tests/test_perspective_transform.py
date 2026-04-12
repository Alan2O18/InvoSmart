"""
perspective_transform.py 單元測試

測試 order_points, crop_by_rect 兩個核心函數。
使用合成圖片，不依賴任何真實圖片檔案。
"""
import pytest
import numpy as np
import cv2

from backend.processing.perspective_transform import (
    order_points,
    crop_by_rect,
)


# ============================================================================
# order_points 測試
# ============================================================================

class TestOrderPoints:
    """測試四點排序: TL → TR → BR → BL"""

    def test_standard_rect(self):
        """標準矩形：已按 TL, TR, BR, BL 排列"""
        pts = np.array([[10, 10], [100, 10], [100, 80], [10, 80]], dtype="float32")
        result = order_points(pts)
        np.testing.assert_array_almost_equal(result[0], [10, 10])   # TL
        np.testing.assert_array_almost_equal(result[1], [100, 10])  # TR
        np.testing.assert_array_almost_equal(result[2], [100, 80])  # BR
        np.testing.assert_array_almost_equal(result[3], [10, 80])   # BL

    def test_shuffled_points(self):
        """打亂順序的四個角點"""
        pts = np.array([[100, 80], [10, 10], [10, 80], [100, 10]], dtype="float32")
        result = order_points(pts)
        np.testing.assert_array_almost_equal(result[0], [10, 10])
        np.testing.assert_array_almost_equal(result[1], [100, 10])
        np.testing.assert_array_almost_equal(result[2], [100, 80])
        np.testing.assert_array_almost_equal(result[3], [10, 80])

    def test_rotated_rect(self):
        """旋轉矩形的頂點（菱形排列）"""
        pts = np.array([[50, 0], [100, 50], [50, 100], [0, 50]], dtype="float32")
        result = order_points(pts)
        # TL = 左上方的點
        assert result.shape == (4, 2)
        # 驗證 y 排序: top 兩點 y 小，bottom 兩點 y 大
        assert result[0][1] <= result[3][1]  # TL.y <= BL.y
        assert result[1][1] <= result[2][1]  # TR.y <= BR.y

    def test_output_is_float32(self):
        """輸出始終為 float32"""
        pts = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype="int32")
        result = order_points(pts)
        assert result.dtype == np.float32


# ============================================================================
# crop_by_rect 測試
# ============================================================================

class TestCropByRect:
    """測試 Direct Warp 裁切"""

    def _make_test_image(self, w=400, h=600):
        """建立包含白色矩形的黑色測試圖"""
        img = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (350, 550), (255, 255, 255), -1)
        return img

    def test_basic_crop(self):
        """基本裁切: 對齊的矩形"""
        img = self._make_test_image(400, 600)
        # minAreaRect 格式: ((cx, cy), (width, height), angle)
        rect = ((200, 300), (300, 500), 0)
        result = crop_by_rect(img, rect)
        assert result.size > 0
        assert len(result.shape) == 3  # 三通道

    def test_crop_portrait_output(self):
        """裁切結果應為直式 (h > w)"""
        img = self._make_test_image(400, 600)
        rect = ((200, 300), (300, 500), 0)
        result = crop_by_rect(img, rect)
        h, w = result.shape[:2]
        assert h >= w, f"預期直式 (h={h} >= w={w})"

    def test_crop_landscape_auto_rotate(self):
        """橫式矩形應自動旋轉為直式 (長邊校正)"""
        img = np.zeros((400, 800, 3), dtype=np.uint8)
        cv2.rectangle(img, (50, 50), (750, 350), (255, 255, 255), -1)
        # 橫向矩形: width > height
        rect = ((400, 200), (700, 300), 0)
        result = crop_by_rect(img, rect)
        h, w = result.shape[:2]
        assert h >= w, f"長邊校正失敗: h={h}, w={w}"

    def test_crop_rotated_rect(self):
        """旋轉矩形裁切"""
        img = np.zeros((500, 500, 3), dtype=np.uint8)
        # 畫一個旋轉的矩形
        center = (250, 250)
        size = (200, 300)
        angle = 30
        rect = (center, size, angle)
        box = cv2.boxPoints(rect)
        box = np.intp(box)
        cv2.fillConvexPoly(img, box, (255, 255, 255))

        result = crop_by_rect(img, rect)
        assert result.size > 0

    def test_crop_invalid_zero_size(self):
        """零尺寸矩形返回空陣列"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        rect = ((50, 50), (0, 0), 0)
        result = crop_by_rect(img, rect)
        assert result.size == 0

    def test_crop_content_preserved(self):
        """裁切不應丟失內容 (中心區域非全黑)"""
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        cv2.rectangle(img, (100, 100), (300, 300), (128, 128, 128), -1)
        rect = ((200, 200), (200, 200), 0)
        result = crop_by_rect(img, rect)
        # 裁切結果的中心區域不應全黑
        center_region = result[result.shape[0]//4:3*result.shape[0]//4,
                               result.shape[1]//4:3*result.shape[1]//4]
        assert np.mean(center_region) > 10, "裁切丟失了內容"


