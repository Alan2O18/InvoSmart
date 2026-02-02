"""
Receipt LLM Converter Module
收據 LLM 轉換模組

將 OCR Markdown 輸入透過 LLM 轉換為 JSON 格式
"""

import os
import json
import re
import ollama
from typing import Dict, Optional, Any
from datetime import datetime


# ==========================================
# 配置
# ==========================================

MODEL_NAME = "qwen3:1.7b"  # 純文字 LLM，足夠處理結構化任務

OLLAMA_OPTIONS = {
    "num_predict": 1024,
    "temperature": 0.2,
}

# JSON Schema (簡化版，專注於免用統一發票收據)
JSON_SCHEMA = """
{
    "receipt_type": "免用統一發票收據",
    "header": {
        "supplier": "商店名稱 (String)",
        "buyer": "買受人 (String)",
        "date": "日期 (String, 如 1140930)"
    },
    "items": [
        {
            "name": "品名 (String)",
            "qty": 數量 (Number),
            "price": 單價 (Number),
            "total": 小計 (Number)
        }
    ],
    "summary": {
        "total": 總金額 (Number)
    },
    "verification": {
        "handwritten_total_chinese": "大寫金額 (String)",
        "stamp_shop_name": "店章名稱 (String)"
    }
}
"""

PROMPT_TEMPLATE = """/no_think
你是一個資料轉換專家。請將以下 Markdown 格式的收據 OCR 結果轉換為 JSON。

## OCR 結果
{markdown_content}

## 規則
1. 不確定的欄位填 null
2. 日期格式: 1140930 (民國年月日，不需轉換)
3. 金額為數字，不含單位
4. 直接輸出 JSON，不要解釋

## 輸出格式
{json_schema}

請直接輸出 JSON：
"""


def convert_markdown_to_json(markdown_content: str) -> Optional[Dict[str, Any]]:
    """
    使用 LLM 將 Markdown 轉換為 JSON
    
    Args:
        markdown_content: OCR 產出的 Markdown 文字
        
    Returns:
        解析後的 JSON 字典，失敗回傳 None
    """
    prompt = PROMPT_TEMPLATE.format(
        markdown_content=markdown_content,
        json_schema=JSON_SCHEMA
    )
    
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': prompt
            }],
            options=OLLAMA_OPTIONS
        )
        
        # 取得回應內容
        message = response.get('message') if hasattr(response, 'get') else getattr(response, 'message', None)
        if message:
            content = message.get('content', "") if isinstance(message, dict) else getattr(message, 'content', "")
        else:
            content = ""
        
        # 解析 JSON
        return parse_json_output(content)
        
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return None


def parse_json_output(text: str) -> Optional[Dict[str, Any]]:
    """
    從 LLM 輸出中解析 JSON
    """
    # 嘗試 markdown code block
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    else:
        # 嘗試找 { }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end+1]
    
    try:
        return json.loads(text)
    except:
        return None


def process_ocr_file(md_path: str) -> Optional[Dict[str, Any]]:
    """
    處理單個 OCR Markdown 檔案
    
    Args:
        md_path: Markdown 檔案路徑
        
    Returns:
        JSON 結果
    """
    if not os.path.exists(md_path):
        print(f"[ERROR] File not found: {md_path}")
        return None
    
    with open(md_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    print(f"[Converting] {md_path}")
    result = convert_markdown_to_json(markdown_content)
    
    if result:
        print(f"  ✅ Success")
    else:
        print(f"  ❌ Failed to parse JSON")
    
    return result


# ==========================================
# 測試用
# ==========================================
if __name__ == "__main__":
    import sys
    
    # 預設測試路徑
    test_dir = "dev_data/regions"
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    
    print("=" * 60)
    print("Receipt LLM Converter Test")
    print(f"Model: {MODEL_NAME}")
    print("=" * 60)
    
    if os.path.exists(test_dir):
        md_files = [f for f in os.listdir(test_dir) if f.endswith('_ocr.md')]
        
        for md_file in md_files:
            md_path = os.path.join(test_dir, md_file)
            result = process_ocr_file(md_path)
            
            if result:
                # 儲存 JSON
                json_path = md_path.replace('_ocr.md', '_result.json')
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"  [Saved] {json_path}")
                print(f"  {json.dumps(result, indent=2, ensure_ascii=False)[:300]}...")
            
            print()
    else:
        print(f"[ERROR] Directory not found: {test_dir}")
