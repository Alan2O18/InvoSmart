"""
Receipt Two-Step LLM Processor
收據兩階段 LLM 處理器

Step 1: 語意分類 - 判斷每個 OCR 文字代表什麼欄位
Step 2: 結構化輸出 - 將分類結果整理成 JSON
"""

import os
import json
import re
import ollama
from typing import Dict, List, Optional, Any
from datetime import datetime


# ==========================================
# 配置
# ==========================================

MODEL_NAME = "qwen3:1.7b"

OLLAMA_OPTIONS = {
    "num_predict": 512,
    "temperature": 0.1,
}

# 欄位類型定義
FIELD_TYPES = """
- BUYER: 買受人/機關名稱 (如: 國立高雄師範大學)
- DATE: 日期 (如: 114年11月25日)
- ITEM_NAME: 品項名稱 (如: 便當、紅茶、套餐)
- ITEM_QTY: 數量 (如: 3, 11)
- ITEM_PRICE: 單價 (如: 40, 120)
- ITEM_TOTAL: 小計金額 (如: 1320, 1560)
- TOTAL_CHINESE: 大寫金額 (如: 萬壹仟參百)
- TOTAL_NUM: 總金額數字 (如: 1320)
- SHOP_NAME: 店家名稱
- SHOP_TEL: 電話
- TAX_ID: 統編 (8位數字)
- NOISE: 表頭/雜訊 (如: 品名、數量、單價、備註)
"""


# ==========================================
# Step 1: 語意分類
# ==========================================

STEP1_PROMPT = """/no_think
你是收據 OCR 專家。判斷每個文字代表什麼欄位。

## 欄位類型
{field_types}

## OCR 文字 (區域: {region})
{texts}

## 任務
為每個文字標註類型，格式：
文字 → 類型

直接輸出結果：
"""


def classify_region_texts(region: str, texts: List[Dict]) -> Dict[str, str]:
    """
    對區域內的文字進行語意分類
    
    Args:
        region: 區域名稱
        texts: 該區域的 OCR 結果列表
        
    Returns:
        {文字: 欄位類型} 字典
    """
    if not texts:
        return {}
    
    # 格式化文字列表
    text_list = "\n".join([f"- {t['text']} ({t['confidence']:.2f})" for t in texts])
    
    prompt = STEP1_PROMPT.format(
        field_types=FIELD_TYPES,
        region=region,
        texts=text_list
    )
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{'role': 'user', 'content': prompt}],
            options=OLLAMA_OPTIONS
        )
        
        content = response.get('message', {}).get('content', '')
        return parse_classification(content, texts)
        
    except Exception as e:
        print(f"[ERROR] Step 1 failed: {e}")
        return {}


def parse_classification(response: str, texts: List[Dict]) -> Dict[str, str]:
    """解析分類結果"""
    result = {}
    
    for line in response.split('\n'):
        if '→' in line or '->' in line:
            parts = re.split(r'→|->|:', line)
            if len(parts) >= 2:
                text = parts[0].strip().strip('-').strip()
                field_type = parts[-1].strip().upper()
                
                # 驗證是否為有效類型
                valid_types = ['BUYER', 'DATE', 'ITEM_NAME', 'ITEM_QTY', 
                              'ITEM_PRICE', 'ITEM_TOTAL', 'TOTAL_CHINESE',
                              'TOTAL_NUM', 'SHOP_NAME', 'SHOP_TEL', 'TAX_ID', 'NOISE']
                
                if any(vt in field_type for vt in valid_types):
                    result[text] = field_type
    
    return result


# ==========================================
# Step 2: 結構化 JSON
# ==========================================

def build_json_from_classifications(
    regions: Dict[str, List[Dict]],
    classifications: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    """
    根據分類結果建構 JSON
    
    Args:
        regions: 各區域的 OCR 結果
        classifications: 各區域的分類結果
        
    Returns:
        結構化 JSON
    """
    result = {
        "receipt_type": "免用統一發票收據",
        "header": {
            "buyer": None,
            "date": None
        },
        "items": [],
        "summary": {
            "total": None,
            "total_chinese": None
        },
        "stamp": {
            "shop_name": None,
            "tel": None,
            "tax_id": None
        }
    }
    
    # 收集所有分類
    all_classified = {}
    for region, cls in classifications.items():
        all_classified.update(cls)
    
    # 提取各欄位
    for text, field_type in all_classified.items():
        if 'BUYER' in field_type:
            # 取最長的作為買受人
            if not result['header']['buyer'] or len(text) > len(result['header']['buyer']):
                result['header']['buyer'] = text.replace('買受人：', '').strip()
        
        elif 'DATE' in field_type:
            result['header']['date'] = extract_date(text)
        
        elif 'ITEM_NAME' in field_type:
            result['items'].append({'name': text, 'qty': None, 'price': None, 'total': None})
        
        elif 'TOTAL_CHINESE' in field_type:
            result['summary']['total_chinese'] = text
        
        elif 'TOTAL_NUM' in field_type:
            nums = re.findall(r'\d+', text)
            if nums:
                result['summary']['total'] = max(int(n) for n in nums)
        
        elif 'SHOP_NAME' in field_type:
            result['stamp']['shop_name'] = text
        
        elif 'SHOP_TEL' in field_type:
            result['stamp']['tel'] = text
        
        elif 'TAX_ID' in field_type:
            match = re.search(r'\d{8}', text)
            if match:
                result['stamp']['tax_id'] = match.group()
    
    return result


def extract_date(text: str) -> str:
    """提取民國日期"""
    match = re.search(r'(\d{2,3})年(\d{1,2})月(\d{1,2})', text)
    if match:
        return f"{match.group(1)}{match.group(2).zfill(2)}{match.group(3).zfill(2)}"
    return text


# ==========================================
# 主處理流程
# ==========================================

def process_two_step(virtual_ocr_result: Dict) -> Dict[str, Any]:
    """
    兩階段處理流程
    
    Args:
        virtual_ocr_result: 虛擬分區 OCR 結果
        
    Returns:
        結構化 JSON
    """
    regions = virtual_ocr_result.get('regions', {})
    
    # Step 1: 分類每個區域
    print("  [Step 1] 語意分類...")
    classifications = {}
    for region_name, texts in regions.items():
        if texts:
            cls = classify_region_texts(region_name, texts)
            classifications[region_name] = cls
            print(f"    {region_name}: {len(cls)} items classified")
    
    # Step 2: 建構 JSON
    print("  [Step 2] 結構化輸出...")
    result = build_json_from_classifications(regions, classifications)
    
    return {
        'json': result,
        'classifications': classifications
    }


# ==========================================
# 測試
# ==========================================

if __name__ == "__main__":
    import sys
    
    # 載入虛擬分區結果
    test_files = [
        "docs/virtual_regions/燕巢小宏遠4.2_split_1_1766302789_raw.json",
        "docs/virtual_regions/手寫收據20251117_split_1_1766160419_raw.json",
    ]
    
    if len(sys.argv) > 1:
        test_files = sys.argv[1:]
    
    print("=" * 60)
    print("Two-Step LLM Processor Test")
    print("=" * 60)
    
    for json_path in test_files:
        if not os.path.exists(json_path):
            print(f"[SKIP] {json_path} not found")
            continue
        
        print(f"\n[Processing] {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            ocr_result = json.load(f)
        
        result = process_two_step(ocr_result)
        
        print("\n[Result]")
        print(json.dumps(result['json'], indent=2, ensure_ascii=False))
        
        # 儲存
        output_path = json_path.replace('_raw.json', '_final.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n[Saved] {output_path}")
