# Receipt Splitter - 發票分割主模組
"""
ReceiptSplitter (refactored)

此模組提供向後相容的發票分割介面。
實際實作已拆分至：
- image_preprocessor.py: 影像預處理
- contour_validator.py: 輪廓驗證
- perspective_transform.py: 透視變換
"""
import cv2
import numpy as np
from typing import List, Dict

from backend.processing.image_preprocessor import ImagePreprocessor
from backend.processing.contour_validator import ContourValidator
from backend.processing.perspective_transform import PerspectiveTransformer


class ReceiptSplitter:
    """
    一個用於從單張圖片中自動偵測、切割並校正多張發票的類別。
    
    此為 Facade 類別，整合預處理、驗證和變換功能。
    """

    def __init__(self, config: Dict):
        """
        初始化 ReceiptSplitter 並設定影像處理參數。

        Args:
            config (Dict): 一個包含所有運算參數的字典。
        """
        # 提取配置參數
        angle_tolerance = config.get("ANGLE_TOLERANCE_DEG", 3)
        aspect_ratio_range = tuple(config.get("ASPECT_RATIO_RANGE", (0.1, 0.9)))
        canny_threshold1 = config.get("CANNY_THRESHOLD1", 30)
        canny_threshold2 = config.get("CANNY_THRESHOLD2", 100)
        morph_kernel_size = tuple(config.get("MORPH_KERNEL_SIZE", (5, 5)))
        
        self.min_contour_area_percentage = config.get("MIN_CONTOUR_AREA_PERCENTAGE", 0.01)
        self.padding_pixels = config.get("PADDING_PIXELS", 0)
        self.dedupe_distance_threshold = config.get("DEDUPE_DISTANCE_THRESHOLD", 50)
        
        # 初始化子模組
        self._preprocessor = ImagePreprocessor(
            canny_threshold1, canny_threshold2, morph_kernel_size
        )
        self._validator = ContourValidator(angle_tolerance, aspect_ratio_range)
        self._transformer = PerspectiveTransformer(self._validator)
        
        # 向後相容性：保留原始屬性
        self.angle_tolerance_deg = angle_tolerance
        self.aspect_ratio_range = aspect_ratio_range
        self.canny_threshold1 = canny_threshold1
        self.canny_threshold2 = canny_threshold2
        self.morph_kernel_size = morph_kernel_size

    # 向後相容的方法委派
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """委派給 ContourValidator"""
        return self._validator.order_points(pts)

    def _validate_angles(self, pts: np.ndarray) -> bool:
        """委派給 ContourValidator"""
        return self._validator.validate_angles(pts)

    def _validate_aspect_ratio(self, rect_wh) -> bool:
        """委派給 ContourValidator"""
        return self._validator.validate_aspect_ratio(rect_wh)

    def _perspective_transform(
        self,
        image: np.ndarray,
        pts: np.ndarray,
        padding: int,
        contour: np.ndarray = None,
    ) -> np.ndarray:
        """委派給 PerspectiveTransformer"""
        return self._transformer.transform(image, pts, padding, contour)

    def split(
        self,
        image: np.ndarray,
        debug: bool = False,
        headless: bool = False,
    ) -> List[np.ndarray]:
        """
        發票分割主程式。

        流程如下：
        1. 預處理：灰階 -> 雙邊濾波 (去噪) -> Canny (邊緣檢測)。
        2. 形態學：膨脹 (Dilate) 連接斷裂的邊緣。
        3. 輪廓搜尋：尋找所有外輪廓。
        4. 候選過濾：過濾面積過小或長寬比不符的物件。
        5. 去重：合併位置重疊的框。
        6. 切割與輸出：透視變換並提供預覽介面。

        Args:
            image: 輸入的原始圖片。
            debug: 是否顯示中間處理過程的除錯視窗。
            headless: 是否為無頭模式。

        Returns:
            切割完成的發票圖片列表。
        """
        if image is None:
            return []

        img_height, img_width = image.shape[:2]
        TOTAL_IMAGE_AREA = img_height * img_width

        # 1. 預處理
        dilated = self._preprocessor.preprocess(image)

        # 2. 尋找輪廓
        contours = self._preprocessor.find_contours(dilated)

        # 3. 篩選候選輪廓
        candidate_contours = []
        min_area = TOTAL_IMAGE_AREA * self.min_contour_area_percentage

        for c in contours[:15]:  # 僅處理前 15 個大輪廓
            if cv2.contourArea(c) < min_area:
                continue

            # 使用凸包
            hull = cv2.convexHull(c)
            min_rect = cv2.minAreaRect(hull)

            # 策略 A：多邊形擬合
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, 0.02 * peri, True)

            if len(approx) == 4 and self._validator.validate_angles(approx.reshape(4, 2)):
                M = cv2.moments(approx)
                center = (
                    int(M["m10"] / (M["m00"] or 1)),
                    int(M["m01"] / (M["m00"] or 1)),
                )
                candidate_contours.append({
                    "points": approx.reshape(4, 2),
                    "type": "approx_verified",
                    "center": center,
                    "area": cv2.contourArea(hull),
                })
            else:
                # 策略 B：最小外接矩形
                box_points = np.intp(cv2.boxPoints(min_rect))
                M = cv2.moments(box_points)
                center = (
                    int(M["m10"] / (M["m00"] or 1)),
                    int(M["m01"] / (M["m00"] or 1)),
                )
                candidate_contours.append({
                    "points": box_points,
                    "type": "min_rect",
                    "center": center,
                    "area": cv2.contourArea(hull),
                })

        # 4. 去重
        final_contours = []
        processed_centers = []

        candidate_contours.sort(
            key=lambda x: (x["type"] == "approx_verified", x["area"]), reverse=True
        )

        for cand in candidate_contours:
            is_duplicate = False
            for pc in processed_centers:
                dist = np.linalg.norm(np.array(cand["center"]) - np.array(pc))
                if dist < self.dedupe_distance_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                final_contours.append(cand)
                processed_centers.append(cand["center"])

        print(f"-> 篩選後保留 {len(final_contours)} 個有效輪廓。")

        # 5. 除錯顯示
        if debug:
            self._show_debug(image, dilated, final_contours, headless)

        # 6. 切割並輸出
        final_receipt = []
        for i, contour_info in enumerate(final_contours):
            warped_invoice = self._transformer.transform(
                image, contour_info["points"], self.padding_pixels
            )

            if warped_invoice.size == 0:
                continue

            final_receipt.append(warped_invoice)

            if debug and not headless:
                self._show_preview(warped_invoice, i, len(final_contours))

        if debug and not headless:
            cv2.destroyAllWindows()

        return final_receipt

    def _show_debug(self, image, dilated, contours, headless):
        """顯示除錯視窗"""
        cv2.imshow(
            "Debug: Canny Edges (Dilated)",
            cv2.resize(dilated, (0, 0), fx=0.5, fy=0.5),
        )

        debug_image = image.copy()
        for contour_info in contours:
            points = contour_info["points"]
            color = (255, 255, 0) if contour_info["type"] == "approx_verified" else (0, 255, 255)
            cv2.drawContours(debug_image, [points], -1, color, 3)
            cv2.circle(debug_image, contour_info["center"], 5, (0, 0, 255), -1)

        cv2.imshow("Debug: Final Contours", cv2.resize(debug_image, (0, 0), fx=0.5, fy=0.5))

        if not headless:
            print("除錯模式：按任意鍵繼續...")
            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == ord("q"):
                    break
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
