#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
發票切割測試腳本 - 診斷歪斜問題
"""

import os
import sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.processing.receipt_splitter import ReceiptSplitter
from backend.utils import utils

# 輸出目錄
DEBUG_OUTPUT_DIR = "dev_data/debug_output"


def test_splitter(image_path: str, debug_visual: bool = True):
    """測試發票切割"""
    print(f"\n{'='*60}")
    print(f"圖片: {os.path.basename(image_path)}")
    print(f"{'='*60}")
    
    # 讀取圖片
    image = utils.cv_imread_chinese(image_path)
    if image is None:
        print(f"  ❌ 無法讀取圖片: {image_path}")
        return None
    
    h, w = image.shape[:2]
    print(f"  尺寸: {w}x{h}")
    
    # 建立 splitter
    config = {
        "ANGLE_TOLERANCE_DEG": 15,  # 放寬角度容忍度
        "ASPECT_RATIO_RANGE": (0.1, 0.9),
        "CANNY_THRESHOLD1": 30,
        "CANNY_THRESHOLD2": 100,
        "MORPH_KERNEL_SIZE": (5, 5),
        "MIN_CONTOUR_AREA_PERCENTAGE": 0.01,
        "PADDING_PIXELS": 0,
        "DEDUPE_DISTANCE_THRESHOLD": 50,
    }
    
    splitter = ReceiptSplitter(config)
    
    # 手動跑分割流程，看中間過程
    print("\n  [預處理...]")
    dilated = splitter._preprocessor.preprocess(image)
    contours = splitter._preprocessor.find_contours(dilated)
    print(f"  找到輪廓: {len(contours)} 個")
    
    # 分析前幾個大輪廓
    TOTAL_IMAGE_AREA = h * w
    min_area = TOTAL_IMAGE_AREA * splitter.min_contour_area_percentage
    
    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
    debug_img = image.copy()
    
    print("\n  [輪廓分析]")
    for i, c in enumerate(contours[:5]):
        area = cv2.contourArea(c)
        if area < min_area:
            print(f"    #{i}: 面積 {area:.0f} (太小, 跳過)")
            continue
        
        # 凸包
        hull = cv2.convexHull(c)
        min_rect = cv2.minAreaRect(hull)
        box_points = np.intp(cv2.boxPoints(min_rect))
        
        # 多邊形擬合
        peri = cv2.arcLength(hull, True)
        approx = cv2.approxPolyDP(hull, 0.02 * peri, True)
        
        print(f"\n    #{i}: 面積 {area:.0f}")
        print(f"         approxPolyDP 頂點數: {len(approx)}")
        print(f"         minAreaRect 角度: {min_rect[2]:.1f}°")
        
        if len(approx) == 4:
            approx_pts = approx.reshape(4, 2)
            # 計算每個角的角度
            angles = []
            for j in range(4):
                p1 = approx_pts[j]
                p2 = approx_pts[(j + 1) % 4]
                p3 = approx_pts[(j + 2) % 4]
                
                v1 = p1 - p2
                v2 = p3 - p2
                cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
                angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
                angles.append(angle_deg)
            
            print(f"         approx 角度: {[f'{a:.1f}°' for a in angles]}")
            print(f"         偏離90度: {[f'{abs(90-a):.1f}°' for a in angles]}")
            
            # 畫 approxPolyDP 的點 (青色)
            cv2.drawContours(debug_img, [approx], -1, (255, 255, 0), 3)
            for pt in approx_pts:
                cv2.circle(debug_img, tuple(pt.astype(int)), 10, (255, 255, 0), -1)
        
        # 畫 minAreaRect 的點 (綠色)
        cv2.drawContours(debug_img, [box_points], -1, (0, 255, 0), 2)
        for pt in box_points:
            cv2.circle(debug_img, tuple(pt), 8, (0, 255, 0), -1)
    
    # 儲存 debug 圖
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    debug_path = os.path.join(DEBUG_OUTPUT_DIR, f"{base_name}_splitter_debug.jpg")
    cv2.imencode('.jpg', debug_img)[1].tofile(debug_path)
    print(f"\n  [Debug 圖片] {debug_path}")
    print("   青色 = approxPolyDP (可能歪斜)")
    print("   綠色 = minAreaRect (正矩形)")
    
    # 執行實際分割
    print("\n  [執行分割...]")
    results = splitter.split(image, debug=False, headless=True)
    print(f"  切割出 {len(results)} 張發票")
    
    # 儲存切割結果
    for j, result in enumerate(results):
        result_path = os.path.join(DEBUG_OUTPUT_DIR, f"{base_name}_split_{j}.jpg")
        cv2.imencode('.jpg', result)[1].tofile(result_path)
        print(f"    → {result_path}")
    
    return results


def main():
    default_images = [
        "dev_data/test_images/小宏遠採購.png",
    ]
    
    test_images = sys.argv[1:] if len(sys.argv) > 1 else default_images
    
    print("=" * 60)
    print("發票切割測試腳本 - 診斷歪斜問題")
    print("=" * 60)
    
    for img_path in test_images:
        if os.path.exists(img_path):
            test_splitter(img_path)
        else:
            print(f"\n⚠️  檔案不存在: {img_path}")


if __name__ == "__main__":
    main()
