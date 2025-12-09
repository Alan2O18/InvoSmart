import cv2
import numpy as np
from typing import List, Tuple, Dict


class ReceiptSplitter:
    """
    一個用於從單張圖片中自動偵測、切割並校正多張發票的類別。
    """

    def __init__(self, config: Dict):
        """
        初始化 ReceiptSplitter 並設定影像處理參數。

        Args:
            config (Dict): 一個包含所有運算參數的字典。
                - ANGLE_TOLERANCE_DEG (int): 判定矩形時，內角與 90 度的最大容忍誤差（度）。預設 3
                - ASPECT_RATIO_RANGE (Tuple[float, float]): 發票有效長寬比範圍 (短邊/長邊)。預設 (0.1, 0.9)。
                - MIN_CONTOUR_AREA_PERCENTAGE (float): 輪廓面積佔整張圖的最小百分比，用於過濾雜訊。預設 0.01。
                - PADDING_PIXELS (int): 透視變換切割後，圖像四周保留的邊距像素。預設 0。
                - DEDUPE_DISTANCE_THRESHOLD (int): 判定兩個輪廓是否為同一張發票的中心點距離閾值。預設 50。
                - CANNY_THRESHOLD1 (int): Canny 邊緣檢測的第一閾值 (低)。預設 30。
                - CANNY_THRESHOLD2 (int): Canny 邊緣檢測的第二閾值 (高)。預設 100。
                - MORPH_KERNEL_SIZE (Tuple[int, int]): 用於連接斷裂邊緣的形態學核心大小。建議設小 (如 5x5) 以避免邊框偏差。
        """
        self.angle_tolerance_deg = config.get("ANGLE_TOLERANCE_DEG", 3)
        self.aspect_ratio_range = tuple(config.get("ASPECT_RATIO_RANGE", (0.1, 0.9)))
        self.min_contour_area_percentage = config.get(
            "MIN_CONTOUR_AREA_PERCENTAGE", 0.01
        )
        self.padding_pixels = config.get("PADDING_PIXELS", 0)
        self.dedupe_distance_threshold = config.get("DEDUPE_DISTANCE_THRESHOLD", 50)
        self.canny_threshold1 = config.get("CANNY_THRESHOLD1", 30)
        self.canny_threshold2 = config.get("CANNY_THRESHOLD2", 100)
        self.morph_kernel_size = tuple(config.get("MORPH_KERNEL_SIZE", (5, 5)))

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        對一個四邊形的四個頂點進行空間排序。

        順序為：左上 (TL) -> 右上 (TR) -> 右下 (BR) -> 左下 (BL)。
        此排序對於透視變換 (Perspective Transform) 至關重要。

        Args:
            pts (np.ndarray): 形狀為 (4, 2) 的頂點陣列。

        Returns:
            np.ndarray: 排序後的頂點陣列，形狀為 (4, 2)，dtype 為 float32。
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
        # 註：原始程式碼此處邏輯為 bottom_points[1] 是右下，[0] 是左下
        bottom_points = bottom_points[np.argsort(bottom_points[:, 0]), :]
        rect[2] = bottom_points[1]  # 右下
        rect[3] = bottom_points[0]  # 左下

        return rect

    def _validate_angles(self, pts: np.ndarray) -> bool:
        """
        驗證四邊形的四個內角是否接近 90 度。

        這是為了區分「真正的發票（通常是矩形）」與「背景雜訊產生的隨機四邊形」。

        Args:
            pts (np.ndarray): 四邊形的四個頂點。

        Returns:
            bool: 若所有角度都在容忍範圍內 (90 ± tolerance) 則返回 True。
        """
        if pts.shape[0] != 4:
            return False

        p = self._order_points(pts)
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
            # Clip 防止浮點數誤差導致數值超出 [-1, 1]
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

    def _validate_aspect_ratio(self, rect_wh: Tuple[float, float]) -> bool:
        """
        驗證矩形的長寬比是否符合一般發票的形狀。

        Args:
            rect_wh (Tuple[float, float]): 矩形的 (寬, 高)。

        Returns:
            bool: 若比例在 ASPECT_RATIO_RANGE 範圍內則返回 True。
        """
        w, h = rect_wh
        if w <= 0 or h <= 0:
            return False

        # 計算長寬比 (短邊 / 長邊)，使其與旋轉方向無關
        aspect_ratio = min(w, h) / max(w, h)

        return self.aspect_ratio_range[0] <= aspect_ratio <= self.aspect_ratio_range[1]

    def _perspective_transform(
        self,
        image: np.ndarray,
        pts: np.ndarray,
        padding: int,
        contour: np.ndarray = None,  # <--- 新增參數：原始輪廓
    ) -> np.ndarray:
        """
        執行透視變換，並支援去背 (Masking) 功能。
        """
        rect = self._order_points(pts)

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

        # 1. 計算變換矩陣
        M = cv2.getPerspectiveTransform(rect, dst)

        # 2. 切割原始圖片
        warped_img = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        # --- 新增邏輯：如果有提供輪廓，進行去背處理 ---
        if contour is not None:
            # 建立一個跟原圖一樣大的全黑遮罩
            mask = np.zeros(image.shape[:2], dtype=np.uint8)
            # 在遮罩上畫出發票的原始形狀 (白色填充)
            cv2.drawContours(mask, [contour], -1, 255, -1)

            # 對遮罩進行同樣的透視變換
            warped_mask = cv2.warpPerspective(mask, M, (maxWidth, maxHeight))

            # 建立純白背景
            white_bg = np.ones_like(warped_img) * 255

            # 使用遮罩合成：遮罩白色區域用發票圖，黑色區域用白背景
            # 這樣缺角的地方就會變成白色，而不是藍色桌布
            mask_inv = cv2.bitwise_not(warped_mask)

            # 前景(發票)
            img_fg = cv2.bitwise_and(warped_img, warped_img, mask=warped_mask)
            # 背景(補白)
            bg_fill = cv2.bitwise_and(white_bg, white_bg, mask=mask_inv)

            # 合併
            final_output = cv2.add(img_fg, bg_fill)
            return final_output
        else:
            return warped_img

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
        4. 候選過濾：
           - 計算凸包 (Convex Hull) 以修復不規則邊緣。
           - 過濾面積過小或長寬比不符的物件。
           - 嘗試多邊形擬合 (ApproxPolyDP) 尋找四邊形 (高信心)。
           - 若擬合失敗，退回使用最小外接矩形 (低信心)。
        5. 去重：合併位置重疊的框，優先保留高信心結果。
        6. 切割與輸出：透視變換並提供預覽介面。

        Args:
            image (np.ndarray): 輸入的原始圖片。
            debug (bool): 是否顯示中間處理過程的除錯視窗。
            headless (bool): 是否為無頭模式 (不顯示互動視窗，直接返回結果)。

        Returns:
            List[np.ndarray]: 切割完成的發票圖片列表。
        """
        if image is None:
            return []

        img_height, img_width = image.shape[:2]
        TOTAL_IMAGE_AREA = img_height * img_width

        # --- 1. 預處理 (使用 Canny) ---
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 使用 Bilateral Filter 保留邊緣細節同時去除雜訊
        blurred = cv2.bilateralFilter(gray, 9, 75, 75)

        # Canny 邊緣檢測：比二值化更能抵抗光影變化
        edged = cv2.Canny(blurred, self.canny_threshold1, self.canny_threshold2)

        # --- 2. 形態學運算 ---
        # 使用 Dilate 連接 Canny 可能斷裂的線條
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, self.morph_kernel_size)
        dilated = cv2.dilate(edged, kernel, iterations=2)

        # --- 3. 尋找輪廓 ---
        contours, _ = cv2.findContours(
            dilated.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        candidate_contours = []
        min_area = TOTAL_IMAGE_AREA * self.min_contour_area_percentage

        # 依照面積大小排序，優先處理主要物件
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for c in contours[:15]:  # 僅處理前 15 個大輪廓以提升效能
            if cv2.contourArea(c) < min_area:
                continue

            # --- 使用凸包 (Convex Hull) ---
            # 凸包將凹凸不平的邊緣「撐開」成平滑多邊形，
            hull = cv2.convexHull(c)

            # 初步使用最小外接矩形檢查長寬比
            min_rect = cv2.minAreaRect(hull)
            # if not self._validate_aspect_ratio(min_rect[1]):
            #     continue

            # 策略 A (高信心)：多邊形擬合
            # 嘗試將凸包擬合成四邊形
            peri = cv2.arcLength(hull, True)
            approx = cv2.approxPolyDP(hull, 0.02 * peri, True)

            # 若擬合結果為四邊形且角度正常，視為最佳結果
            if len(approx) == 4 and self._validate_angles(approx.reshape(4, 2)):
                M = cv2.moments(approx)
                center = (
                    int(M["m10"] / (M["m00"] or 1)),
                    int(M["m01"] / (M["m00"] or 1)),
                )
                candidate_contours.append(
                    {
                        "points": approx.reshape(4, 2),
                        "type": "approx_verified",  # 標記為驗證通過
                        "center": center,
                        "area": cv2.contourArea(hull),
                    }
                )
            else:
                # 策略 B (低信心)：最小外接矩形
                # 若形狀不規則，退回使用外接矩形 (Box Points)
                box_points = np.intp(cv2.boxPoints(min_rect))
                M = cv2.moments(box_points)
                center = (
                    int(M["m10"] / (M["m00"] or 1)),
                    int(M["m01"] / (M["m00"] or 1)),
                )
                candidate_contours.append(
                    {
                        "points": box_points,
                        "type": "min_rect",  # 標記為一般矩形
                        "center": center,
                        "area": cv2.contourArea(hull),
                    }
                )

        # --- 4. 去除重複輪廓 (Deduplication) ---
        final_contours = []
        processed_centers = []

        # 排序：優先保留 "approx_verified" 且面積較大的候選者
        candidate_contours.sort(
            key=lambda x: (x["type"] == "approx_verified", x["area"]), reverse=True
        )

        for cand in candidate_contours:
            is_duplicate = False
            # 檢查是否與已選中的輪廓中心點過於接近
            for pc in processed_centers:
                dist = np.linalg.norm(np.array(cand["center"]) - np.array(pc))
                if dist < self.dedupe_distance_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                final_contours.append(cand)
                processed_centers.append(cand["center"])

        print(f"-> 篩選後保留 {len(final_contours)} 個有效輪廓。")

        # --- 5. 除錯顯示 ---
        if debug:
            # 顯示 Canny 邊緣圖 (有助於判斷閾值是否恰當)
            cv2.imshow(
                "Debug: Canny Edges (Dilated)",
                cv2.resize(dilated, (0, 0), fx=0.5, fy=0.5),
            )

            debug_image = image.copy()
            for contour_info in final_contours:
                points = contour_info["points"]
                # 藍色 (Cyan) 為高信心，黃色為低信心 (矩形補償)
                color = (
                    (255, 255, 0)
                    if contour_info["type"] == "approx_verified"
                    else (0, 255, 255)
                )

                cv2.drawContours(debug_image, [points], -1, color, 3)
                cv2.circle(debug_image, contour_info["center"], 5, (0, 0, 255), -1)

            cv2.imshow(
                "Debug: Final Contours", cv2.resize(debug_image, (0, 0), fx=0.5, fy=0.5)
            )

            print("除錯模式：按任意鍵繼續...")
            while True:
                key = cv2.waitKey(0) & 0xFF
                if key == ord("q"):
                    break
            cv2.destroyAllWindows()

        # --- 6. 切割並輸出 ---
        final_receipt = []
        for i, contour_info in enumerate(final_contours):
            warped_invoice = self._perspective_transform(
                image, contour_info["points"], self.padding_pixels
            )

            if warped_invoice.size == 0:
                continue

            # Always return result in headless/server mode
            final_receipt.append(warped_invoice)
            
            # Debug preview only if debug is True AND not headless
            if debug and not headless:
                # 縮小預覽圖以免視窗過大
                max_preview_size = 800
                preview_image = warped_invoice
                if max(warped_invoice.shape) > max_preview_size:
                    scale = max_preview_size / max(warped_invoice.shape)
                    preview_image = cv2.resize(warped_invoice, (0, 0), fx=scale, fy=scale)

                window_name = f"Receipt {i+1}/{len(final_contours)}"
                cv2.imshow(window_name, preview_image)
                cv2.waitKey(1) # Just show briefly or handle differently if needed

        if debug and not headless:
            cv2.destroyAllWindows()

        return final_receipt
