"""
Receipt Heuristic Classifier
收據啟發式分類器

使用規則和模式匹配進行語意分類，不依賴 LLM
基於區域位置 + 文字特徵進行判斷
"""

import os
import json
import re
from typing import Dict, List, Any


# ==========================================
# 分類規則
# ==========================================

def classify_text(text: str, region: str, confidence: float) -> str:
    """
    根據文字內容和區域判斷欄位類型
    """
    text_lower = text.lower()
    
    # 日期模式
    if re.search(r'\d{2,3}年\d{1,2}月\d{1,2}', text):
        return 'DATE'
    
    # 純數字
    if text.isdigit():
        if region == 'table':
            num = int(text)
            if num > 100:
                return 'ITEM_TOTAL'  # 較大數字可能是總價
            else:
                return 'ITEM_QTY'  # 較小可能是數量
        elif region == 'stamp':
            if len(text) == 8:
                return 'TAX_ID'
            return 'NOISE'
        elif region == 'summary':
            return 'TOTAL_NUM'
        return 'NUMBER'
    
    # 電話模式
    if re.search(r'TEL|電話', text, re.IGNORECASE) or re.search(r'\d{7,}', text):
        if region == 'stamp':
            return 'SHOP_TEL'
    
    # 統編 (8位數字)
    if re.search(r'^\d{8}$', text.replace('-', '')):
        return 'TAX_ID'
    
    # 買受人關鍵字
    if any(kw in text for kw in ['大學', '學校', '機關', '公司', '國立', '市立']):
        return 'BUYER'
    
    # 大寫金額
    if any(c in text for c in ['萬', '仟', '佰', '拾', '壹', '贰', '參', '肆', '伍', '陸', '柒', '捌', '玖']):
        return 'TOTAL_CHINESE'
    
    # 元整
    if '元整' in text:
        return 'TOTAL_CHINESE'
    
    # 表頭雜訊
    if any(kw in text for kw in ['品名', '數量', '單價', '金額', '備註', '總價', '單价']):
        return 'NOISE'
    
    # 常見雜訊
    if text in ['備', '價備', '品', '名', '價']:
        return 'NOISE'
    
    # 根據區域推斷
    if region == 'buyer':
        if '台照' in text:
            return 'NOISE'  # 台照是格式文字
        if '免用' in text or '發票' in text or '收據' in text:
            return 'NOISE'  # 標題
        if '统一' in text or '統一' in text:
            return 'NOISE'  # 統一福號
        if len(text) > 3 and not text.isdigit():
            return 'BUYER'
    
    if region == 'date':
        if '年' in text or '月' in text or '日' in text:
            return 'DATE'
    
    if region == 'table':
        if len(text) >= 2 and not any(c in text for c in ['備', '價', '數', '單']):
            if not text.isdigit():
                return 'ITEM_NAME'
    
    if region == 'stamp':
        if len(text) >= 2 and not text.isdigit():
            if '銀货' not in text and '銀貨' not in text:
                return 'SHOP_NAME'
    
    if region == 'summary':
        if '合計' in text or '新台' in text:
            return 'TOTAL_LABEL'
    
    return 'UNKNOWN'


def classify_regions(regions: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    對所有區域的文字進行分類
    """
    classified = {}
    
    for region_name, texts in regions.items():
        classified[region_name] = []
        for item in texts:
            field_type = classify_text(item['text'], region_name, item['confidence'])
            classified[region_name].append({
                'text': item['text'],
                'confidence': item['confidence'],
                'type': field_type
            })
    
    return classified


def build_json(classified: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """
    根據分類結果建構 JSON
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
    
    # 提取買受人 (取最長的)
    buyers = [c for c in classified.get('buyer', []) if c['type'] == 'BUYER']
    if buyers:
        result['header']['buyer'] = max(buyers, key=lambda x: len(x['text']))['text']
    
    # 提取日期
    dates = [c for c in classified.get('date', []) if c['type'] == 'DATE']
    if dates:
        date_text = dates[0]['text']
        match = re.search(r'(\d{2,3})年(\d{1,2})月(\d{1,2})', date_text)
        if match:
            result['header']['date'] = f"{match.group(1)}{match.group(2).zfill(2)}{match.group(3).zfill(2)}"
    
    # 提取品項
    item_names = [c for c in classified.get('table', []) if c['type'] == 'ITEM_NAME']
    item_totals = [c for c in classified.get('table', []) if c['type'] == 'ITEM_TOTAL']
    
    for i, name_item in enumerate(item_names):
        item = {
            'name': name_item['text'],
            'qty': None,
            'price': None,
            'total': int(item_totals[i]['text']) if i < len(item_totals) else None
        }
        result['items'].append(item)
    
    # 提取合計
    totals_chinese = [c for c in classified.get('summary', []) if c['type'] == 'TOTAL_CHINESE']
    if totals_chinese:
        result['summary']['total_chinese'] = ' '.join([t['text'] for t in totals_chinese])
    
    totals_num = [c for c in classified.get('summary', []) if c['type'] == 'TOTAL_NUM']
    if totals_num:
        result['summary']['total'] = max(int(t['text']) for t in totals_num)
    
    # 提取店章
    shop_names = [c for c in classified.get('stamp', []) if c['type'] == 'SHOP_NAME']
    if shop_names:
        result['stamp']['shop_name'] = shop_names[0]['text']
    
    tels = [c for c in classified.get('stamp', []) if c['type'] == 'SHOP_TEL']
    if tels:
        result['stamp']['tel'] = tels[0]['text']
    
    tax_ids = [c for c in classified.get('stamp', []) if c['type'] == 'TAX_ID']
    if tax_ids:
        result['stamp']['tax_id'] = tax_ids[0]['text']
    
    return result


def process_virtual_ocr(ocr_result: Dict) -> Dict[str, Any]:
    """
    處理虛擬分區 OCR 結果
    """
    regions = ocr_result.get('regions', {})
    
    # Step 1: 分類
    classified = classify_regions(regions)
    
    # Step 2: 建構 JSON
    result_json = build_json(classified)
    
    return {
        'json': result_json,
        'classified': classified
    }


# ==========================================
# 測試
# ==========================================

if __name__ == "__main__":
    import sys
    
    test_files = [
        "docs/virtual_regions/燕巢小宏遠4.2_split_1_1766302789_raw.json",
        "docs/virtual_regions/手寫收據20251117_split_1_1766160419_raw.json",
        "docs/virtual_regions/手寫收據20251117_split_0_1766302781_raw.json",
    ]
    
    if len(sys.argv) > 1:
        test_files = sys.argv[1:]
    
    print("=" * 60)
    print("Heuristic Classifier Test")
    print("=" * 60)
    
    for json_path in test_files:
        if not os.path.exists(json_path):
            print(f"[SKIP] {json_path}")
            continue
        
        print(f"\n[Processing] {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            ocr_result = json.load(f)
        
        result = process_virtual_ocr(ocr_result)
        
        print("\n[Result]")
        print(json.dumps(result['json'], indent=2, ensure_ascii=False))
        
        # 儲存
        output_path = json_path.replace('_raw.json', '_final.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n[Saved] {output_path}")
