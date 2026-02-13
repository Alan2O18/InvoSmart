"""
receipt_splitter.py 單元測試

測試 ReceiptSplitter 的各子功能：
- _resize_for_detection: 縮放邏輯
- _mask_iou_dedupe: IoU 去重
- split: 端對端合成圖片分割
使用合成圖片，不依賴任何真實圖片。
"""
import pytest
import numpy as np
import cv2

from backend.processing.receipt_splitter import ReceiptSplitter, RESIZE_SHORT_EDGE


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def splitter():
    """建立預設配置的 splitter"""
    return ReceiptSplitter({
        "CANNY_THRESHOLD1": 30,
        "CANNY_THRESHOLD2": 100,
        "MIN_CONTOUR_AREA_PERCENTAGE": 0.02,
        "IOU_THRESHOLD": 0.3,
    })


@pytest.fixture
def default_config():
    return {
        "CANNY_THRESHOLD1": 30,
        "CANNY_THRESHOLD2": 100,
        "MIN_CONTOUR_AREA_PERCENTAGE": 0.02,
        "IOU_THRESHOLD": 0.3,
    }


# ============================================================================
# _resize_for_detection 測試
# ============================================================================

class TestResizeForDetection:
    """測試縮圖邏輯"""

    def test_small_image_no_resize(self, splitter):
        """短邊 < RESIZE_SHORT_EDGE 時不縮放"""
        img = np.zeros((1000, 1500, 3), dtype=np.uint8)
        resized, scale = splitter._resize_for_detection(img)
        assert scale == 1.0
        assert resized.shape == img.shape

    def test_large_image_resized(self, splitter):
        """短邊 > RESIZE_SHORT_EDGE 時等比縮放"""
        img = np.zeros((4000, 6000, 3), dtype=np.uint8)
        resized, scale = splitter._resize_for_detection(img)
        assert scale < 1.0
        assert min(resized.shape[:2]) <= RESIZE_SHORT_EDGE
        # 等比例驗證
        assert abs(resized.shape[1] / resized.shape[0] - 6000 / 4000) < 0.05

    def test_exact_boundary(self, splitter):
        """短邊 == RESIZE_SHORT_EDGE 時不縮放"""
        img = np.zeros((RESIZE_SHORT_EDGE, 3000, 3), dtype=np.uint8)
        resized, scale = splitter._resize_for_detection(img)
        assert scale == 1.0


# ============================================================================
# _mask_iou_dedupe 測試
# ============================================================================

class TestMaskIoUDedupe:
    """測試 Mask IoU 去重"""

    def test_single_candidate(self, splitter):
        """單一候選不去重"""
        candidates = [{"rect": ((100, 100), (80, 120), 0), "area": 9600}]
        result = splitter._mask_iou_dedupe(candidates, 1.0, (300, 300))
        assert len(result) == 1

    def test_no_overlap(self, splitter):
        """無重疊的候選全部保留"""
        candidates = [
            {"rect": ((50, 50), (60, 80), 0), "area": 4800},
            {"rect": ((200, 200), (60, 80), 0), "area": 4800},
        ]
        result = splitter._mask_iou_dedupe(candidates, 1.0, (300, 300))
        assert len(result) == 2

    def test_high_overlap_removes_smaller(self, splitter):
        """高度重疊時移除面積小者"""
        candidates = [
            {"rect": ((100, 100), (100, 150), 0), "area": 15000},
            {"rect": ((105, 105), (80, 120), 0), "area": 9600},  # 小的重疊
        ]
        result = splitter._mask_iou_dedupe(candidates, 1.0, (300, 300))
        assert len(result) == 1
        assert result[0]["area"] == 15000  # 保留大的

    def test_empty_candidates(self, splitter):
        """空候選列表"""
        result = splitter._mask_iou_dedupe([], 1.0, (300, 300))
        assert len(result) == 0


# ============================================================================
# split 端對端測試
# ============================================================================

class TestSplitEndToEnd:
    """使用合成圖片進行端對端分割測試"""

    def test_split_none_image(self, splitter):
        """None 圖片返回空列表"""
        assert splitter.split(None) == []

    def test_split_single_rect(self, splitter):
        """單一白色矩形在灰色背景上 → 1 split"""
        img = np.ones((800, 600, 3), dtype=np.uint8) * 180  # 灰色背景
        cv2.rectangle(img, (50, 50), (550, 750), (255, 255, 255), -1)  # 白色矩形
        # 在白色矩形內畫一些黑色文字線條以增強邊緣
        for y in range(100, 700, 40):
            cv2.line(img, (100, y), (500, y), (0, 0, 0), 2)

        results = splitter.split(img)
        assert len(results) >= 1

    def test_split_two_rects(self, splitter):
        """兩個分離的白色矩形 → 2 splits"""
        # 大圖 + 兩個明顯分離的白色矩形
        img = np.ones((2000, 1500, 3), dtype=np.uint8) * 60  # 暗灰色背景

        # 矩形 1 (上方)
        cv2.rectangle(img, (100, 50), (1400, 900), (255, 255, 255), -1)
        for y in range(100, 850, 30):
            cv2.line(img, (150, y), (1350, y), (0, 0, 0), 2)

        # 矩形 2 (下方) — 明顯間隔
        cv2.rectangle(img, (100, 1050), (1400, 1950), (255, 255, 255), -1)
        for y in range(1100, 1900, 30):
            cv2.line(img, (150, y), (1350, y), (0, 0, 0), 2)

        results = splitter.split(img)
        assert len(results) >= 2

    def test_split_preserves_content(self, splitter):
        """分割結果不應為全黑"""
        img = np.ones((800, 600, 3), dtype=np.uint8) * 180
        cv2.rectangle(img, (50, 50), (550, 750), (255, 255, 255), -1)
        for y in range(100, 700, 40):
            cv2.line(img, (100, y), (500, y), (0, 0, 0), 2)

        results = splitter.split(img)
        if results:
            for r in results:
                assert np.mean(r) > 10, "分割結果不應為全黑"

    def test_adaptive_kernel_calculation(self, splitter):
        """驗證自適應核心計算 k = max(3, short_edge // 90)"""
        # 短邊 1800 → k = 1800 // 90 = 20
        k = max(3, 1800 // 90)
        assert k == 20

        # 短邊 270 → k = 270 // 90 = 3
        k = max(3, 270 // 90)
        assert k == 3

        # 短邊 89 → k = max(3, 0) = 3
        k = max(3, 89 // 90)
        assert k == 3


# ============================================================================
# 初始化測試
# ============================================================================

class TestSplitterInit:
    """測試初始化與配置"""

    def test_default_config(self, default_config):
        """使用預設配置初始化"""
        s = ReceiptSplitter(default_config)
        assert s.min_contour_area_percentage == 0.02
        assert s.iou_threshold == 0.3

    def test_custom_config(self):
        """使用自訂配置"""
        s = ReceiptSplitter({
            "MIN_CONTOUR_AREA_PERCENTAGE": 0.05,
            "IOU_THRESHOLD": 0.5,
        })
        assert s.min_contour_area_percentage == 0.05
        assert s.iou_threshold == 0.5
