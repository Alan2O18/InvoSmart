"""
Receipt Rule-Based Converter
收據規則式轉換器

使用 Python 規則直接從 OCR Markdown 提取資訊, 不依賴 LLM
"""

import os
import json
import re
from typing import Dict, Optional, Any, List
from datetime import datetime


def extract_buyer(lines: List[str]) -> str:
    """從買受人區提取"""
    for line in lines:
        if "國立" in line or "大學" in line:
            # 清理常見干擾
            buyer = line.replace("買受人：", "").replace("台照", "").strip()
            return buyer
    return ""


def extract_date(lines: List[str]) -> str:
    """從日期區提取民國日期"""
    for line in lines:
        # 匹配民國日期格式
        match = re.search(r'(\d{2,3})年(\d{1,2})月(\d{1,2})日', line)
        if match:
            year = match.group(1)
            month = match.group(2).zfill(2)
            day = match.group(3).zfill(2)
            return f"{year}{month}{day}"
    return ""


def extract_items(lines: List[str]) -> List[Dict]:
    """從品項區提取商品"""
    items = []
    numbers = []
    names = []
    
    for line in lines:
        # 跳過標題行
        if "品" in line and ("名" in line or "數量" in line):
            continue
        if line in ["備", "價備"]:
            continue
            
        # 嘗試提取數字
        nums = re.findall(r'\d+', line)
        if nums:
            numbers.extend([int(n) for n in nums])
        else:
            # 可能是品名
            if len(line) > 1 and not any(c in line for c in ["備", "銀", "元"]):
                names.append(line)
    
    # 嘗試配對品名和金額
    for name in names:
        items.append({
            "name": name,
            "qty": None,
            "price": None,
            "total": None
        })
    
    # 如果有識別到的數字, 嘗試填入金額
    if numbers and items:
        # 最大的數字可能是總金額
        items[0]["total"] = max(numbers) if numbers else None
    
    return items


def extract_total(lines: List[str]) -> Optional[int]:
    """從合計區提取總金額"""
    combined = " ".join(lines)
    
    # 嘗試找數字
    nums = re.findall(r'\d+', combined)
    if nums:
        return max([int(n) for n in nums])
    
    # 嘗試解析中文大寫
    chinese_total = ""
    for line in lines:
        if any(c in line for c in ["萬", "仟", "佰", "拾", "壹", "贰", "參", "肆", "伍"]):
            chinese_total = line
            break
    
    if chinese_total:
        # 簡單返回原始中文
        return None
    
    return None


def extract_chinese_total(lines: List[str]) -> str:
    """提取大寫金額"""
    for line in lines:
        if any(c in line for c in ["萬", "仟", "佰", "元整", "壹", "贰"]):
            return line.replace("合計", "").replace("新台", "").strip()
    return ""


def extract_stamp(lines: List[str]) -> str:
    """從店章區提取店名"""
    for line in lines:
        # 跳過常見干擾
        if line in ["備", "銀货雨", "銀貨雨", "價備"]:
            continue
        # 找統編
        if re.search(r'\d{8}', line):
            continue
        # 可能是店名
        if len(line) >= 2:
            return line
    return ""


def parse_ocr_markdown(md_content: str) -> Dict[str, Any]:
    """
    解析 OCR Markdown 並轉換為 JSON
    """
    result = {
        "receipt_type": "免用統一發票收據",
        "header": {
            "supplier": None,
            "buyer": None,
            "date": None
        },
        "items": [],
        "summary": {
            "total": None
        },
        "verification": {
            "handwritten_total_chinese": None,
            "stamp_shop_name": None
        }
    }
    
    # 分割出各區域
    sections = {}
    current_section = None
    current_lines = []
    
    for line in md_content.split('\n'):
        line = line.strip()
        if line.startswith('## '):
            if current_section:
                sections[current_section] = current_lines
            current_section = line[3:].strip()
            current_lines = []
        elif line.startswith('- '):
            current_lines.append(line[2:].strip())
    
    if current_section:
        sections[current_section] = current_lines
    
    # 提取各欄位
    if "買受人" in sections:
        result["header"]["buyer"] = extract_buyer(sections["買受人"])
    
    if "日期" in sections:
        result["header"]["date"] = extract_date(sections["日期"])
    
    if "品項" in sections:
        result["items"] = extract_items(sections["品項"])
    
    if "店章" in sections:
        result["verification"]["stamp_shop_name"] = extract_stamp(sections["店章"])
    
    if "合計" in sections:
        result["summary"]["total"] = extract_total(sections["合計"])
        result["verification"]["handwritten_total_chinese"] = extract_chinese_total(sections["合計"])
    
    return result


def process_ocr_file(md_path: str) -> Optional[Dict[str, Any]]:
    """處理單個 OCR Markdown 檔案"""
    if not os.path.exists(md_path):
        print(f"[ERROR] File not found: {md_path}")
        return None
    
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    print(f"[Converting] {md_path}")
    result = parse_ocr_markdown(md_content)
    print(f"  ✅ Done")
    
    return result


# ==========================================
# 測試用
# ==========================================
if __name__ == "__main__":
    import sys
    
    test_dir = "docs/regions"
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    
    print("=" * 60)
    print("Receipt Rule-Based Converter Test")
    print("=" * 60)
    
    if os.path.exists(test_dir):
        md_files = [f for f in os.listdir(test_dir) if f.endswith('_ocr.md')]
        
        for md_file in md_files:
            md_path = os.path.join(test_dir, md_file)
            result = process_ocr_file(md_path)
            
            if result:
                json_path = md_path.replace('_ocr.md', '_result.json')
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"  [Saved] {json_path}")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
            print()
    else:
        print(f"[ERROR] Directory not found: {test_dir}")
