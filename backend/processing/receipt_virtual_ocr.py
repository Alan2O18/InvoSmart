"""
Receipt Virtual Region OCR
收據虛擬分區 OCR

對原圖進行一次 OCR，利用返回的座標將文字分配到各虛擬區域：
- 買受人 (左上)
- 日期 (右上)
- 品項表格 (左側)
- 店章 (右側)
- 合計 (底部)
"""

import os
import sys
import json
import cv2
import numpy as np
from typing import Dict, List, Optional, Any
from pathlib import Path

# 使用 RapidOCR PP-OCRv5
from rapidocr_onnxruntime import RapidOCR


# ==========================================
# 配置
# ==========================================

# 虛擬區域邊界 (相對比例)
REGION_BOUNDARIES = {
    'header_ratio': 0.28,    # 0-28% = 頂部區 (買受人/日期)
    'main_ratio': 0.88,      # 28-88% = 主體區 (表格/店章)
    'left_ratio': 0.70,      # 左側佔 70%
    # 88-100% = 底部 (合計)
}


# ==========================================
# OCR 引擎
# ==========================================

_ocr_engine = None

def get_ocr_engine():
    """取得 OCR 引擎 (PP-OCRv5 Server)"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR(
            ocr_version='PP-OCRv5',
            det_model_type='server',
            rec_model_type='server'
        )
    return _ocr_engine


def load_image(image_path: str) -> Optional[np.ndarray]:
    """載入圖片 (支援中文路徑)"""
    if not os.path.exists(image_path):
        return None
    try:
        return cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except:
        return None


# ==========================================
# 虛擬分區
# ==========================================

def classify_text_to_regions(
    ocr_results: List,
    image_height: int,
    image_width: int
) -> Dict[str, List[Dict]]:
    """
    根據座標將 OCR 結果分類到虛擬區域
    
    Args:
        ocr_results: RapidOCR 返回的結果 [[四角點], 文字, 信心度]
        image_height: 圖片高度
        image_width: 圖片寬度
        
    Returns:
        各區域的文字列表
    """
    regions = {
        'buyer': [],
        'date': [],
        'table': [],
        'stamp': [],
        'summary': []
    }
    
    # 計算邊界像素值
    header_y = int(image_height * REGION_BOUNDARIES['header_ratio'])
    main_y = int(image_height * REGION_BOUNDARIES['main_ratio'])
    mid_x = int(image_width * REGION_BOUNDARIES['left_ratio'])
    
    for item in ocr_results:
        box_points, text, confidence = item
        
        # 計算文字區塊的中心點
        xs = [p[0] for p in box_points]
        ys = [p[1] for p in box_points]
        center_x = sum(xs) / 4
        center_y = sum(ys) / 4
        
        # 創建結構化資料
        text_item = {
            'text': text,
            'confidence': float(confidence),
            'center': (center_x, center_y),
            'box': [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
        }
        
        # 根據位置分類
        if center_y < header_y:
            # 頂部區
            if center_x < mid_x:
                regions['buyer'].append(text_item)
            else:
                regions['date'].append(text_item)
        elif center_y < main_y:
            # 主體區
            if center_x < mid_x:
                regions['table'].append(text_item)
            else:
                regions['stamp'].append(text_item)
        else:
            # 底部區
            regions['summary'].append(text_item)
    
    # 按 Y 座標排序每個區域的文字
    for region_name in regions:
        regions[region_name].sort(key=lambda x: x['center'][1])
    
    return regions


def ocr_with_virtual_regions(image_path: str) -> Dict[str, Any]:
    """
    對圖片進行 OCR 並虛擬分區
    
    Args:
        image_path: 圖片路徑
        
    Returns:
        包含分區結果和統計的字典
    """
    image = load_image(image_path)
    if image is None:
        return {'error': f'Failed to load image: {image_path}'}
    
    h, w = image.shape[:2]
    
    # 執行 OCR
    engine = get_ocr_engine()
    ocr_results, elapse = engine(image)
    
    if not ocr_results:
        return {
            'regions': {},
            'stats': {'text_count': 0, 'time_s': elapse}
        }
    
    # 分類到虛擬區域
    regions = classify_text_to_regions(ocr_results, h, w)
    
    # 統計
    stats = {
        'image_size': f'{w}x{h}',
        'text_count': len(ocr_results),
        'time_s': elapse if isinstance(elapse, float) else sum(elapse) if elapse else 0,
        'regions_count': {k: len(v) for k, v in regions.items()}
    }
    
    return {
        'regions': regions,
        'stats': stats
    }


def format_regions_to_markdown(regions: Dict[str, List[Dict]]) -> str:
    """將分區結果格式化為 Markdown"""
    md = "# 收據 OCR 結果 (虛擬分區)\n\n"
    
    section_names = {
        'buyer': '買受人',
        'date': '日期',
        'table': '品項',
        'stamp': '店章',
        'summary': '合計'
    }
    
    for region_key, section_title in section_names.items():
        md += f"## {section_title}\n"
        items = regions.get(region_key, [])
        for item in items:
            md += f"- {item['text']} ({item['confidence']:.2f})\n"
        if not items:
            md += "- (無識別結果)\n"
        md += "\n"
    
    return md


# ==========================================
# 主程式
# ==========================================

if __name__ == "__main__":
    test_images = [
        "docs/手寫收據20251117_split_0_1766302781.jpg",
        "docs/手寫收據20251117_split_1_1766160419.jpg",
        "docs/燕巢小宏遠4.2_split_1_1766302789.jpg",
    ]
    
    if len(sys.argv) > 1:
        test_images = sys.argv[1:]
    
    print("=" * 60)
    print("Virtual Region OCR Test (PP-OCRv5 Server)")
    print("=" * 60)
    
    for img_path in test_images:
        print(f"\n[Processing] {img_path}")
        
        result = ocr_with_virtual_regions(img_path)
        
        if 'error' in result:
            print(f"  ❌ {result['error']}")
            continue
        
        stats = result['stats']
        print(f"  Size: {stats['image_size']}, Texts: {stats['text_count']}")
        print(f"  Regions: {stats['regions_count']}")
        
        # 輸出 Markdown
        md = format_regions_to_markdown(result['regions'])
        print(md)
        
        # 儲存結果
        base_name = Path(img_path).stem
        output_dir = "docs/virtual_regions"
        os.makedirs(output_dir, exist_ok=True)
        
        md_path = os.path.join(output_dir, f"{base_name}_ocr.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md)
        
        json_path = os.path.join(output_dir, f"{base_name}_raw.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"  [Saved] {md_path}")
