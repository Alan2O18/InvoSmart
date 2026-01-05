"""
Receipt OCR Formatter Module
收據 OCR 格式化模組

對分區圖片進行 OCR (使用 RapidOCR)，並格式化為 Markdown
(適用於 5 區域版面)
"""

import os
import sys
import cv2
import numpy as np
from typing import Dict, Optional, List
from pathlib import Path

# 添加 backend 到 path (如需要其他模組)


# 全域 OCR 引擎 (PP-OCRv5 Server)
_ocr_engine = None


def get_ocr_engine():
    """取得 OCR 引擎 (使用 PP-OCRv5 server 模型)"""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
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
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        return image
    except:
        return None


def ocr_image(image_path: str) -> List[str]:
    """
    對圖片進行 OCR，返回文字列表 (使用 PP-OCRv5 server)
    """
    image = load_image(image_path)
    if image is None:
        return []
    
    engine = get_ocr_engine()
    result, _ = engine(image)
    
    if not result:
        return []
    
    # 按 Y 座標排序，整理成行
    # RapidOCR 返回: [[四個角點], 文字, 信心度]
    sorted_items = sorted(result, key=lambda x: min(p[1] for p in x[0]))
    lines = [item[1] for item in sorted_items]
    
    return lines


def format_buyer(lines: List[str]) -> str:
    """格式化買受人區"""
    md = "## 買受人\n"
    for line in lines:
        md += f"- {line}\n"
    if not lines:
        md += "- (無識別結果)\n"
    return md


def format_date(lines: List[str]) -> str:
    """格式化日期區"""
    md = "## 日期\n"
    for line in lines:
        md += f"- {line}\n"
    if not lines:
        md += "- (無識別結果)\n"
    return md


def format_table(lines: List[str]) -> str:
    """格式化品項表格區"""
    md = "## 品項\n"
    for line in lines:
        md += f"- {line}\n"
    if not lines:
        md += "- (無識別結果)\n"
    return md


def format_stamp(lines: List[str]) -> str:
    """格式化店章區"""
    md = "## 店章\n"
    for line in lines:
        md += f"- {line}\n"
    if not lines:
        md += "- (無識別結果)\n"
    return md


def format_summary(lines: List[str]) -> str:
    """格式化合計區"""
    md = "## 合計\n"
    for line in lines:
        md += f"- {line}\n"
    if not lines:
        md += "- (無識別結果)\n"
    return md


def process_regions(region_paths: Dict[str, str]) -> str:
    """
    處理所有區域並生成 Markdown
    """
    md = "# 收據 OCR 結果\n\n"
    
    formatters = {
        'buyer': format_buyer,
        'date': format_date,
        'table': format_table,
        'stamp': format_stamp,
        'summary': format_summary,
    }
    
    for region_name, formatter in formatters.items():
        if region_name in region_paths:
            print(f"  [OCR] {region_name}...")
            lines = ocr_image(region_paths[region_name])
            print(f"    → {len(lines)} 行文字")
            md += formatter(lines) + "\n"
    
    return md


# ==========================================
# 測試用
# ==========================================
if __name__ == "__main__":
    test_dir = "docs/regions"
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    
    print("=" * 60)
    print("Receipt OCR Formatter Test (RapidOCR + 5-Region)")
    print("=" * 60)
    
    if os.path.exists(test_dir):
        files = os.listdir(test_dir)
        
        # 分組
        groups = {}
        for f in files:
            if f.endswith('.jpg'):
                parts = f.rsplit('_', 1)
                if len(parts) == 2:
                    base = parts[0]
                    region = parts[1].replace('.jpg', '')
                    if base not in groups:
                        groups[base] = {}
                    groups[base][region] = os.path.join(test_dir, f)
        
        # 處理每組
        for base_name, region_paths in groups.items():
            print(f"\n[Processing] {base_name}")
            md_result = process_regions(region_paths)
            print(md_result)
            
            # 儲存結果
            output_path = os.path.join(test_dir, f"{base_name}_ocr.md")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md_result)
            print(f"[Saved] {output_path}")
    else:
        print(f"[ERROR] Directory not found: {test_dir}")
