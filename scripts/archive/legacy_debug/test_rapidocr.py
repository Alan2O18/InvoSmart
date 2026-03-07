#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RapidOCR 單一模組測試腳本

用法：
    python test_rapidocr.py [圖片路徑...]
    
    如果沒有指定圖片，會使用 docs/test_images/ 中的預設收據圖片。
"""

import os
import sys
import time
import cv2
import numpy as np

# 確保可以 import backend 模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.processing.rapidocr_handler import RapidOCRHandler
from backend.processing.receipt_virtual_ocr import (
    classify_text_to_regions,
    format_regions_to_markdown
)
from backend.utils import utils

# 輸出目錄
DEBUG_OUTPUT_DIR = "dev_data/debug_output"

def remove_lines(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 二值化 (黑白分明)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, -2)
    
    # 定義橫線和直線的結構元素
    horizontal = np.copy(thresh)
    vertical = np.copy(thresh)
    
    # 1. 抓橫線 (寬度 > 30px)
    cols = horizontal.shape[1]
    horizontal_size = cols // 30
    horizontalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_size, 1))
    horizontal = cv2.erode(horizontal, horizontalStructure)
    horizontal = cv2.dilate(horizontal, horizontalStructure)
    
    # 2. 抓直線 (高度 > 30px)
    rows = vertical.shape[0]
    vertical_size = rows // 30
    verticalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_size))
    vertical = cv2.erode(vertical, verticalStructure)
    vertical = cv2.dilate(vertical, verticalStructure)
    
    # 3. 建立遮罩 (橫線 + 直線)
    mask = horizontal + vertical
    
    # 4. 把線條塗白 (Inpainting) 或者簡單地相加
    # 這裡用一個簡單暴力的 trick: 把遮罩區域變白
    result = img.copy()
    # 膨脹一下遮罩，確保線條被蓋乾淨
    mask = cv2.dilate(mask, np.ones((3,3), np.uint8), iterations=2)
    
    # 將線條區域設為白色 (假設背景是白)
    result[mask == 255] = (255, 255, 255)
    
    return result


def draw_debug_image(image: np.ndarray, ocr_result: list, output_path: str):
    """
    在圖片上繪製 OCR 結果 (框框 + 文字 + 信心度)
    """
    # 複製圖片
    debug_img = image.copy()
    
    # 載入支援中文的字體 (使用 PIL)
    from PIL import Image, ImageDraw, ImageFont
    
    # 轉換為 PIL Image
    debug_pil = Image.fromarray(cv2.cvtColor(debug_img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(debug_pil)
    
    # 嘗試載入中文字體
    try:
        # Windows 預設中文字體
        font = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 24)
        font_small = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", 18)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", 24)
            font_small = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", 18)
        except:
            font = ImageFont.load_default()
            font_small = font
    
    # 根據信心度選擇顏色
    def get_color(confidence):
        if confidence >= 0.9:
            return (0, 200, 0)  # 綠色 - 高信心度
        elif confidence >= 0.7:
            return (255, 165, 0)  # 橘色 - 中信心度
        else:
            return (255, 0, 0)  # 紅色 - 低信心度
    
    # 繪製每個 OCR 結果
    for item in ocr_result:
        box = item['box']  # [x1, y1, x2, y2]
        text = item['text']
        conf = item['confidence']
        
        x1, y1, x2, y2 = box
        color = get_color(conf)
        
        # 繪製邊框
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        
        # 繪製標籤背景
        label = f"{text} ({conf:.0%})"
        bbox = draw.textbbox((x1, y1 - 25), label, font=font_small)
        draw.rectangle([bbox[0]-2, bbox[1]-2, bbox[2]+2, bbox[3]+2], fill=color)
        
        # 繪製文字
        draw.text((x1, y1 - 25), label, font=font_small, fill=(255, 255, 255))
    
    # 轉回 OpenCV 格式並儲存
    debug_img = cv2.cvtColor(np.array(debug_pil), cv2.COLOR_RGB2BGR)
    cv2.imencode('.jpg', debug_img)[1].tofile(output_path)
    
    return output_path


def test_single_image(handler: RapidOCRHandler, image_path: str):
    """測試單張圖片的 OCR"""
    print(f"\n{'='*60}")
    print(f"圖片: {os.path.basename(image_path)}")
    print(f"{'='*60}")
    
    # 讀取圖片
    image = utils.cv_imread_chinese(image_path)
    if image is None:
        print(f"  ❌ 無法讀取圖片: {image_path}")
        return None

    image = remove_lines(image)
    
    h, w = image.shape[:2]
    print(f"  尺寸: {w}x{h}")
    
    # 執行 OCR
    start_time = time.time()
    ocr_result, ocr_stats = handler.do_ocr(image)
    elapsed = time.time() - start_time
    
    print(f"  OCR 時間: {elapsed:.2f}s (引擎: {ocr_stats.get('ocr_engine_time_s', 'N/A')}s)")
    print(f"  識別區塊: {len(ocr_result)} 個")
    
    if not ocr_result:
        print("  ⚠️  未識別到任何文字")
        return None
    
    # 輸出原始 OCR 結果
    print(f"\n  [原始 OCR 結果]")
    for item in ocr_result:
        box = item['box']
        conf = item['confidence']
        text = item['text']
        print(f"    [{box[0]:4d},{box[1]:4d}]-[{box[2]:4d},{box[3]:4d}] ({conf:.2f}) \"{text}\"")
    
    # 繪製 Debug 圖片
    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    debug_path = os.path.join(DEBUG_OUTPUT_DIR, f"{base_name}_debug.jpg")
    draw_debug_image(image, ocr_result, debug_path)
    print(f"\n  [Debug 圖片] {debug_path}")
    
    # 轉換為虛擬分區格式
    ocr_for_classify = []
    for item in ocr_result:
        box = item["box"]
        four_points = [
            [box[0], box[1]],
            [box[2], box[1]],
            [box[2], box[3]],
            [box[0], box[3]]
        ]
        ocr_for_classify.append([four_points, item["text"], item["confidence"]])
    
    # 虛擬分區
    regions = classify_text_to_regions(ocr_for_classify, h, w)
    
    print(f"\n  [虛擬分區統計]")
    for region_name, items in regions.items():
        print(f"    {region_name}: {len(items)} 項")
    
    # 格式化為 Markdown
    markdown = format_regions_to_markdown(regions)
    
    print(f"\n  [格式化輸出]")
    print("-" * 50)
    print(markdown)
    print("-" * 50)
    
    return {
        'ocr_result': ocr_result,
        'regions': regions,
        'markdown': markdown,
        'stats': ocr_stats,
        'debug_image': debug_path
    }


def main():
    # 預設測試圖片
    default_images = [
        "dev_data/test_images/手寫收據20251117_split_0_1766302781.jpg",
        "dev_data/test_images/手寫收據20251117_split_1_1766160419.jpg",
        "dev_data/test_images/手寫收據20251118.1_split_1_1766160420.jpg",
    ]
    
    # 使用命令列參數或預設
    test_images = sys.argv[1:] if len(sys.argv) > 1 else default_images
    
    print("=" * 60)
    print("RapidOCR 測試腳本")
    print("PP-OCRv5 Server | det_limit_side_len=2560")
    print(f"Debug 輸出: {DEBUG_OUTPUT_DIR}/")
    print("=" * 60)
    
    # 初始化 handler
    print("\n[初始化 RapidOCRHandler...]")
    handler = RapidOCRHandler({})
    
    # 測試每張圖片
    results = {}
    for img_path in test_images:
        if os.path.exists(img_path):
            result = test_single_image(handler, img_path)
            if result:
                results[img_path] = result
        else:
            print(f"\n⚠️  檔案不存在: {img_path}")
    
    # 總結
    print(f"\n{'='*60}")
    print(f"測試完成: {len(results)}/{len(test_images)} 張成功")
    if results:
        print(f"Debug 圖片已儲存至: {DEBUG_OUTPUT_DIR}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

