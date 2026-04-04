# Receipt Splitter - 發票分割主模組 (V10 重構版)
"""
ReceiptSplitter (V10)

使用 minAreaRect + Direct Warp 裁切，搭配 Mask IoU 去重與投影方向校正。
不再使用透視變換、Hough 角點偵測或角度驗證。

流程：
1. 縮圖偵測輪廓 (Adaptive Kernel)
2. 座標映射回原圖 → 面積過濾
3. Mask IoU 去重
4. Direct Warp 裁切 (含長邊校正)
5. 投影方向校正
"""
import logging
import cv2
import numpy as np
from typing import List, Dict, Tuple

from backend.processing.image_preprocessor import ImagePreprocessor
from backend.processing.perspective_transform import crop_by_rect, fix_orientation, order_points

logger = logging.getLogger(__name__)

# 縮圖短邊上限
RESIZE_SHORT_EDGE = 2000


class ReceiptSplitter:
    """
    從單張圖片中自動偵測、切割並校正多張發票。

    V10 使用 minAreaRect + Direct Warp 裁切，搭配 Mask IoU 去重。
    """

    def __init__(self, config: Dict):
        """
        初始化 ReceiptSplitter。

        Args:
            config: 包含運算參數的字典。
        """
        canny_threshold1 = config.get("CANNY_THRESHOLD1", 30)
        canny_threshold2 = config.get("CANNY_THRESHOLD2", 100)
        # morph_kernel_size 現在由自適應邏輯計算，這裡的值作為 fallback
        morph_kernel_size = tuple(config.get("MORPH_KERNEL_SIZE", (5, 5)))

        self.min_contour_area_percentage = config.get("MIN_CONTOUR_AREA_PERCENTAGE", 0.02)
        self.iou_threshold = config.get("IOU_THRESHOLD", 0.3)

        # 初始化子模組 (僅用於 find_contours)
        self._preprocessor = ImagePreprocessor(
            canny_threshold1, canny_threshold2, morph_kernel_size
        )

    def split(
        self,
        image: np.ndarray,
        debug: bool = False,
        headless: bool = False,
    ) -> List[np.ndarray]:
        """
        發票分割主程式 (V10)。

        Args:
            image: 輸入的原始圖片 (BGR)。
            debug: 是否顯示中間處理過程的除錯視窗。
            headless: 是否為無頭模式。

        Returns:
            切割完成的發票圖片列表。
        """
        if image is None:
            return []

        final_rects, dilated, scale_factor = self._detect_rects(image)

        logger.debug(f"IoU 去重後剩 {len(final_rects)} 個有效輪廓")

        # ── Step 4 & 5: 除錯顯示 ──
        if debug:
            self._show_debug(image, dilated, final_rects, scale_factor, headless)

        # ── Step 4: Direct Warp 裁切 + Step 5: 方向校正 ──
        final_receipts = []

        for i, item in enumerate(final_rects):
            rect = item["rect"]

            # Direct Warp 裁切 (含長邊校正)
            crop = crop_by_rect(image, rect)

            if crop.size == 0:
                logger.warning(f"[發票 {i+1}] Direct Warp 裁切失敗")
                continue

            # 方向校正 (投影輪廓)
            crop = fix_orientation(crop)

            final_receipts.append(crop)
            logger.info(f"[發票 {i+1}] 裁切完成: {crop.shape[1]}x{crop.shape[0]}")

            if debug and not headless:
                self._show_preview(crop, i, len(final_rects))

        if debug and not headless:
            cv2.destroyAllWindows()

        return final_receipts

    def detect_only(self, image: np.ndarray) -> List[Dict]:
        """
        僅偵測可切割的子區域，不執行裁切。

        Returns:
            每個候選區域包含：
            - points: [TL, TR, BR, BL] 四點座標
            - area: 輪廓面積
        """
        if image is None:
            return []

        final_rects, _, _ = self._detect_rects(image)
        payload = []
        for item in final_rects:
            box = cv2.boxPoints(item["rect"])
            ordered = order_points(box)
            payload.append(
                {
                    "points": [[float(x), float(y)] for x, y in ordered],
                    "area": float(item["area"]),
                }
            )
        return payload

    def _detect_rects(self, image: np.ndarray) -> Tuple[List[Dict], np.ndarray, float]:
        """共用偵測流程：回傳去重後矩形、dilated 圖與縮放比例。"""
        img_h, img_w = image.shape[:2]
        total_area = img_h * img_w

        # ── Step 1: 縮圖輪廓偵測 ──
        resized, scale_factor = self._resize_for_detection(image)
        rh, rw = resized.shape[:2]

        # 自適應膨脹核心
        short_edge = min(rw, rh)
        # V11 調優: divisor 90 為碎片/沾黏最佳平衡點
        k = max(3, short_edge // 90)
        logger.debug(f"自適應核心: k={k} (圖片 {rw}x{rh}, 縮放比={scale_factor:.3f})")

        # 預處理 (灰階 → 模糊 → Canny → 膨脹)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 9, 75, 75)
        edged = cv2.Canny(blurred, 30, 100)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
        dilated = cv2.dilate(edged, kernel, iterations=1)

        # 尋找輪廓
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        logger.debug(f"找到 {len(contours)} 個輪廓")

        # ── Step 2: 座標映射 + 面積過濾 ──
        min_area = total_area * self.min_contour_area_percentage
        candidate_rects = []

        for c in contours[:15]:
            # 還原座標到原圖
            c_orig = (c.astype(np.float64) / scale_factor).astype(np.float32)

            # 凸包 → minAreaRect
            hull = cv2.convexHull(c_orig)
            area = cv2.contourArea(hull)

            if area < min_area:
                continue

            rect = cv2.minAreaRect(hull)
            candidate_rects.append(
                {
                    "rect": rect,
                    "area": area,
                }
            )

        logger.debug(f"面積過濾後剩 {len(candidate_rects)} 個候選")

        # ── Step 3: Mask IoU 去重 ──
        final_rects = self._mask_iou_dedupe(
            candidate_rects, scale_factor, (rh, rw)
        )
        return final_rects, dilated, scale_factor

    def _resize_for_detection(
        self, image: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        若圖片短邊超過 RESIZE_SHORT_EDGE，則等比縮放。

        Returns:
            (縮放後的圖片, 縮放比例 scale_factor)
            scale_factor < 1 表示圖片被縮小了。
            原圖座標 = 縮圖座標 / scale_factor。
        """
        h, w = image.shape[:2]
        short_edge = min(w, h)

        if short_edge <= RESIZE_SHORT_EDGE:
            return image, 1.0

        scale_factor = RESIZE_SHORT_EDGE / short_edge
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        logger.debug(f"縮圖: {w}x{h} → {new_w}x{new_h} (scale={scale_factor:.3f})")
        return resized, scale_factor

    def _mask_iou_dedupe(
        self,
        candidates: List[Dict],
        scale_factor: float,
        mask_shape: Tuple[int, int],
    ) -> List[Dict]:
        """
        使用 Mask IoU 去除重疊的候選矩形。

        在縮圖尺寸的 Mask 上繪製矩形，計算 pixel-wise IoU。
        IoU > threshold 時保留面積大者。

        Args:
            candidates: 候選矩形列表 (含 rect 和 area)。
            scale_factor: 縮圖的縮放比例。
            mask_shape: Mask 的 (H, W)。

        Returns:
            去重後的候選矩形列表。
        """
        if len(candidates) <= 1:
            return candidates

        # 依面積降序排列
        candidates.sort(key=lambda x: x["area"], reverse=True)

        # 預先計算每個候選在縮圖上的 mask
        masks = []
        for item in candidates:
            rect = item["rect"]
            # 將 rect 座標縮放到縮圖尺寸
            center = (rect[0][0] * scale_factor, rect[0][1] * scale_factor)
            size = (rect[1][0] * scale_factor, rect[1][1] * scale_factor)
            angle = rect[2]
            scaled_rect = (center, size, angle)

            box = cv2.boxPoints(scaled_rect)
            box = np.intp(box)

            mask = np.zeros(mask_shape, dtype=np.uint8)
            cv2.fillConvexPoly(mask, box, 255)
            masks.append(mask)

        # 去重: 保留面積最大者
        keep = [True] * len(candidates)

        for i in range(len(candidates)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(candidates)):
                if not keep[j]:
                    continue

                # 計算 IoU
                intersection = cv2.bitwise_and(masks[i], masks[j])
                union = cv2.bitwise_or(masks[i], masks[j])

                inter_count = np.count_nonzero(intersection)
                union_count = np.count_nonzero(union)

                if union_count == 0:
                    continue

                iou = inter_count / union_count

                if iou > self.iou_threshold:
                    # 保留面積大者 (i)，移除面積小者 (j)
                    keep[j] = False
                    logger.debug(
                        f"IoU 去重: 移除候選 {j} (IoU={iou:.2f}, "
                        f"area={candidates[j]['area']:.0f} < {candidates[i]['area']:.0f})"
                    )

        return [c for c, k in zip(candidates, keep) if k]

    def _show_debug(self, image, dilated, final_rects, scale_factor, headless):
        """顯示除錯視窗"""
        cv2.imshow(
            "Debug: Canny Edges (Dilated)",
            cv2.resize(dilated, (0, 0), fx=0.5, fy=0.5),
        )

        debug_image = image.copy()
        for item in final_rects:
            rect = item["rect"]
            box = cv2.boxPoints(rect)
            box = np.intp(box)
            cv2.drawContours(debug_image, [box], -1, (0, 255, 0), 3)

            # 標記中心
            cx, cy = int(rect[0][0]), int(rect[0][1])
            cv2.circle(debug_image, (cx, cy), 8, (0, 0, 255), -1)

        cv2.imshow(
            "Debug: Final Rects",
            cv2.resize(debug_image, (0, 0), fx=0.3, fy=0.3),
        )

        if not headless:
            print("除錯模式：按任意鍵繼續...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    def _show_preview(self, image, index, total):
        """顯示預覽視窗"""
        max_preview_size = 800
        preview_image = image
        if max(image.shape) > max_preview_size:
            scale = max_preview_size / max(image.shape)
            preview_image = cv2.resize(image, (0, 0), fx=scale, fy=scale)

        window_name = f"Receipt {index+1}/{total}"
        cv2.imshow(window_name, preview_image)
        cv2.waitKey(1)
