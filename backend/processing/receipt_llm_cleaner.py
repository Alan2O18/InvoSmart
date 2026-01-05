"""
Receipt LLM Cleaner
收據 LLM 清洗模組

使用 LLM 修正 OCR 錯誤：
- 修正相似字形誤識別 (图→國, 大学→大學)
- 補全缺失文字 (師大學→師範大學)
- 規範化格式
"""

import os
import json
import re
import ollama
from typing import Dict, List, Optional, Any


# ==========================================
# 配置
# ==========================================

MODEL_NAME = "qwen3:1.7b"

OLLAMA_OPTIONS = {
    "num_predict": 1024,
    "temperature": 0.1,
    # 允許較長思考時間
}

# 常見 OCR 錯誤模式 (用於提示 LLM)
COMMON_OCR_ERRORS = """
常見 OCR 錯誤：
- 图 → 國 (相似字形)
- 大学 → 大學 (簡繁轉換)
- 師大學 → 師範大學 (缺字)
- 壹干 → 壹仟 (相似字形)
- 贰 → 貳 (簡繁)
- 參 → 叁 (異體字)
"""


# ==========================================
# LLM 清洗 Prompt
# ==========================================

CLEANING_PROMPT = """你是收據資料清洗專家。請修正 OCR 錯誤並輸出 JSON。

OCR 結果:
買受人: {buyer}
日期: {date}
品項: {items}
合計: {total_chinese}
店章: {shop_name}

常見錯誤:
- 图→國, 大学→大學, 師大學→師範大學
- 壹干→壹仟, 贰→貳

直接輸出修正後的 JSON (不要解釋):
```json
{{
  "buyer": "修正後的買受人",
  "date": "日期 (YYYYMMDD)",
  "items": [{{"name": "品名", "total": 金額}}],
  "total_chinese": "修正後的大寫金額",
  "shop_name": "店名"
}}
```"""

JSON_TEMPLATE = '''
{
  "header": {
    "buyer": "買受人 (修正後)",
    "date": "日期 (YYYYMMDD 或民國)"
  },
  "items": [
    {"name": "品名", "qty": 數量, "price": 單價, "total": 小計}
  ],
  "summary": {
    "total": 總金額數字,
    "total_chinese": "大寫金額"
  },
  "stamp": {
    "shop_name": "店名",
    "tel": "電話",
    "tax_id": "統編"
  }
}
'''


def clean_with_llm(ocr_json: Dict) -> Optional[Dict]:
    """
    使用 LLM 清洗 OCR 結果
    """
    header = ocr_json.get('header', {})
    items = ocr_json.get('items', [])
    summary = ocr_json.get('summary', {})
    stamp = ocr_json.get('stamp', {})
    
    prompt = CLEANING_PROMPT.format(
        buyer=header.get('buyer', ''),
        date=header.get('date', ''),
        items=', '.join([i.get('name', '') for i in items]),
        total_chinese=summary.get('total_chinese', ''),
        shop_name=stamp.get('shop_name', '')
    )
    
    print("  [LLM] Cleaning...")
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{'role': 'user', 'content': prompt}],
            options=OLLAMA_OPTIONS
        )
        
        content = response.get('message', {}).get('content', '')
        
        # Debug: 顯示 LLM 輸出
        print(f"  [DEBUG] LLM output length: {len(content)}")
        print(f"  [DEBUG] First 500 chars: {content[:500]}")
        
        # 解析 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # 嘗試直接找 JSON
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
            return json.loads(content[start:end+1])
        
        print("  [WARN] Could not parse LLM output")
        return None
        
    except Exception as e:
        print(f"  [ERROR] LLM cleaning failed: {e}")
        return None


def clean_receipt(heuristic_result: Dict) -> Dict:
    """
    清洗收據結果
    
    Args:
        heuristic_result: 啟發式分類器的完整輸出 (含 json 和 classified)
        
    Returns:
        包含原始和清洗結果的字典
    """
    ocr_json = heuristic_result.get('json', {})
    
    # 使用 LLM 清洗
    cleaned = clean_with_llm(ocr_json)
    
    return {
        'original': ocr_json,
        'cleaned': cleaned,
        'has_changes': cleaned is not None and cleaned != ocr_json
    }


# ==========================================
# 測試
# ==========================================

if __name__ == "__main__":
    import sys
    
    test_files = [
        "docs/virtual_regions/燕巢小宏遠4.2_split_1_1766302789_final.json",
    ]
    
    if len(sys.argv) > 1:
        test_files = sys.argv[1:]
    
    print("=" * 60)
    print("Receipt LLM Cleaner Test")
    print(f"Model: {MODEL_NAME}")
    print("=" * 60)
    
    for json_path in test_files:
        if not os.path.exists(json_path):
            print(f"[SKIP] {json_path}")
            continue
        
        print(f"\n[Processing] {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            heuristic_result = json.load(f)
        
        result = clean_receipt(heuristic_result)
        
        if result['cleaned']:
            print("\n[Cleaned Result]")
            print(json.dumps(result['cleaned'], indent=2, ensure_ascii=False))
            
            # 儲存
            output_path = json_path.replace('_final.json', '_cleaned.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n[Saved] {output_path}")
        else:
            print("\n[FAILED] LLM cleaning failed")
