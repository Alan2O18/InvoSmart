import sqlite3
import time
import json
import re
import os
import sys
import ollama
import traceback
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# ==========================================
# 配置設定 (Configuration)
# ==========================================

# 模型設定 (Model Settings)
MODEL_NAME = "qwen3-vl:8b"
DB_PATH = "jobs.db"
TEST_SAMPLE_LIMIT = 3 # 依使用者要求測試多份樣本
REPORT_JSON_PATH = "vlm_test_report.json"
REPORT_MD_PATH = "vlm_test_summary.md"

# Ollama 生成參數 (Generation Options)
OLLAMA_OPTIONS = {
    "num_predict": 3072,  # Token 上限
    "temperature": 0.8,   # 降低隨機性
    "top_p": 0.9,         
    "repeat_penalty": 1.2
}

# 參照 docs/json_schema.md 的標準輸出格式
TARGET_JSON_SCHEMA = """
{
    "receipt_type": "免用統一發票收據",
    "header": {
        "supplier": "商店名稱 (String)",
        "buyer": "買受人 (String)",
        "date": "日期 (String, 格式如 20061231)",
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

PROMPT_TEMPLATES = {
    "Schema_Strict_NoThink": f"""/no_think
你是一個專業的會計憑證識別專家。
任務：從圖片中提取收據資訊，請直接輸出 JSON，不需要解釋。
規則：
1. 不確定的資料填 null
2. 日期直接填寫，如中華民國1140101
3. 總額欄中叉叉或橫線代表佔位符，只識別大寫數字
4. 空行不必列入
5. 台照前的文字代表買受人
請直接輸出以下格式的 JSON 
{TARGET_JSON_SCHEMA}
"""
}

# ==========================================
# 資料結構 (Data Structures)
# ==========================================

@dataclass
class TestResult:
    job_id: str
    image_path: str
    prompt_name: str
    success: bool
    json_valid: bool
    accuracy_score: float
    field_match: Dict[str, Any]
    metrics: Dict[str, Any]
    output: Dict[str, Any]
    thinking: str
    error: str = ""

# ==========================================
# 工具函式 (Utility Functions)
# ==========================================

def get_test_samples(db_path, limit=10):
    """從資料庫取得測試樣本 (包含 Ground Truth)"""
    if not os.path.exists(db_path):
        print(f"錯誤: 找不到資料庫 {db_path}")
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 撈取有 manual_json_text (Ground Truth) 且有圖片的任務
        cursor.execute("""
            SELECT job_id, image_path, manual_json_text 
            FROM jobs 
            WHERE image_path IS NOT NULL 
              AND manual_json_text IS NOT NULL 
              AND manual_json_text != ''
            LIMIT ?
        """, (limit,))
        
        samples = []
        for row in cursor.fetchall():
            try:
                # 簡單驗證 manual_json_text 是否為有效 JSON
                gt = json.loads(row['manual_json_text'])
                samples.append({
                    "job_id": row['job_id'],
                    "image_path": row['image_path'],
                    "ground_truth": gt
                })
            except json.JSONDecodeError:
                print(f"Skipping job {row['job_id']}: Invalid manual_json_text")
        
        conn.close()
        return samples
    except Exception as e:
        print(f"讀取資料庫錯誤: {e}")
        return []

def parse_model_output(content):
    """解析模型輸出：分離思考過程與 JSON"""
    # 這裡因為使用了 chat 並且假設 thinking 會在 response.message.thinking 中，
    # 所以 content 主要是 JSON 內容。但為了保險起見 (如果 thinking 混在 content 裡)，我們還是保留 regex
    
    thinking = ""
    json_str = content
    
    # 嘗試提取 JSON (支援 Markdown code block)
    json_match = re.search(r'```json\s*(.*?)\s*```', json_str, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # 嘗試尋找最外層的 {}
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start != -1 and end != -1:
            json_str = json_str[start:end+1]
            
    parsed_json = None
    try:
        parsed_json = json.loads(json_str)
    except:
        pass
        
    return parsed_json

def calculate_accuracy(pred: Dict, truth: Dict) -> tuple[float, Dict]:
    """
    計算準確率 (簡易版)
    比對關鍵欄位: Total, Date, Item Count
    """
    scores = {}
    
    # Safely get nested dictionaries
    pred_summary = pred.get("summary") or {}
    truth_summary = truth.get("summary") or {}
    pred_header = pred.get("header") or {}
    truth_header = truth.get("header") or {}
    pred_items_list = pred.get("items") or []
    truth_items_list = truth.get("items") or []

    # 1. 總金額比對 (Total Amount)
    try:
        pred_total_val = pred_summary.get("total", 0)
        truth_total_val = truth_summary.get("total", 0)
        
        # Handle cases where total is None or empty string
        if pred_total_val is None or pred_total_val == "": pred_total_val = 0
        if truth_total_val is None or truth_total_val == "": truth_total_val = 0
        
        pred_total = float(pred_total_val)
        truth_total = float(truth_total_val)
        scores["total_match"] = 1.0 if abs(pred_total - truth_total) <= 1.0 else 0.0
    except Exception as e:
        # print(f"DEBUG: Total match error: {e}")
        scores["total_match"] = 0.0
        
    # 2. 日期比對 (Date)
    pred_date = str(pred_header.get("date", "") or "").replace("-", "").replace("/", "")
    truth_date = str(truth_header.get("date", "") or "").replace("-", "").replace("/", "")
    scores["date_match"] = 1.0 if (truth_date and truth_date in pred_date) or (pred_date and pred_date in truth_date) else 0.0

    # 3. 項目數量比對 (Item Count)
    scores["item_count_match"] = 1.0 if len(pred_items_list) == len(truth_items_list) else 0.0
    
    # 平均分數
    avg_score = sum(scores.values()) / len(scores) if scores else 0.0
    return avg_score, scores

def print_separator(char="-", length=80):
    print(char * length)

# ==========================================
# 主程式 (Main Execution)
# ==========================================

def main():
    print_separator("=")
    print(f"VLM Benchmark Test (v2.2 - Ollama Chat)")
    print(f"Model: {MODEL_NAME}")
    print(f"Limit: {TEST_SAMPLE_LIMIT} samples")
    print_separator("=")
    
    # 1. 獲取樣本
    samples = get_test_samples(DB_PATH, TEST_SAMPLE_LIMIT)
    if not samples:
        print("No samples found. Exiting.")
        return

    print(f"Found {len(samples)} valid samples with Ground Truth.")
    
    all_results = []
    
    # 2. 執行測試迴圈
    for i, sample in enumerate(samples):
        print(f"\nProcessing [{i+1}/{len(samples)}] Job: {sample['job_id']}")
        image_path = sample['image_path']
        
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}, skipping...")
            continue
            
        for p_name, p_text in PROMPT_TEMPLATES.items():
            print(f"  > Prompt: {p_name}")
            
            try:
                start_time = time.time()
                
                # 使用 ollama.chat
                response = ollama.chat(
                    model=MODEL_NAME,
                    messages=[{
                        'role': 'user',
                        'content': p_text,
                        'images': [image_path]
                    }],
                    options=OLLAMA_OPTIONS
                )
                
                duration = time.time() - start_time
                
                # Metrics (Access as attributes)
                # 注意: 根據使用者回饋，回應是一個物件
                try:
                    # Ensure eval_count and eval_duration_ns are always integers (never None)
                    raw_eval_count = response.get('eval_count', 0) if hasattr(response, 'get') else getattr(response, 'eval_count', 0)
                    raw_eval_duration_ns = response.get('eval_duration', 0) if hasattr(response, 'get') else getattr(response, 'eval_duration', 0)
                    
                    # Convert None to 0
                    eval_count = int(raw_eval_count) if raw_eval_count is not None else 0
                    eval_duration_ns = int(raw_eval_duration_ns) if raw_eval_duration_ns is not None else 0
                    
                    # Message Object
                    message = response.get('message') if hasattr(response, 'get') else getattr(response, 'message', None)
                    
                    content = ""
                    thinking = ""
                    
                    if message:
                        # Message might be a dict or object
                        if isinstance(message, dict):
                            content = message.get('content', "")
                            thinking = message.get('thinking', "") # 嘗試從 dict 拿
                        else:
                            content = getattr(message, 'content', "")
                            thinking = getattr(message, 'thinking', "") # 嘗試從 object 拿
                            
                except Exception as e:
                    print(f"  [ERROR Parsing Response Object]: {e}")
                    # Fallback for debugging
                    print(f"  [DEBUG Response]: {response}")
                    eval_count = 0
                    eval_duration_ns = 0
                    content = ""
                    thinking = ""

                speed = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
                
                # Parsing Content
                parsed_json = parse_model_output(content)
                json_valid = parsed_json is not None
                
                # --- PRINT THINKING / OUTPUT ---
                print_separator(".", 40)
                if thinking:
                    print(f"  [Thinking]:\n{thinking}")
                else:
                    print(f"  [No Thinking Detected in Response Object]")
                
                if json_valid:
                    print(f"  [Extracted JSON]: OK")
                else:
                    print(f"  [Raw Output (Failed Parse)]:\n{content.strip()[:500]}...")
                print_separator(".", 40)
                # -------------------------------

                # Accuracy
                acc_score = 0.0
                match_details = {}
                if json_valid:
                    acc_score, match_details = calculate_accuracy(parsed_json, sample["ground_truth"])
                
                result = TestResult(
                    job_id=sample['job_id'],
                    image_path=image_path,
                    prompt_name=p_name,
                    success=True,
                    json_valid=json_valid,
                    accuracy_score=acc_score,
                    field_match=match_details,
                    metrics={
                        "time_s": round(duration, 2),
                        "speed_tps": round(speed, 2),
                        "tokens": eval_count
                    },
                    output=parsed_json if parsed_json else {"raw": content[:1000]},
                    thinking=thinking,
                    error=""
                )
                
                status = "PASS" if (json_valid and acc_score > 0.8) else ("WARN" if json_valid else "FAIL")
                print(f"  Result: [{status}] Acc: {acc_score:.2f}, Speed: {speed:.1f}t/s")
                all_results.append(result)
                
            except Exception as e:
                print(f"  [ERROR] {e}")
                traceback.print_exc()
                all_results.append(TestResult(
                    job_id=sample['job_id'], 
                    image_path=image_path,
                    prompt_name=p_name,
                    success=False,
                    json_valid=False,
                    accuracy_score=0.0,
                    field_match={},
                    metrics={},
                    output={},
                    thinking="",
                    error=str(e)
                ))

    # 3. 生成報告 (Report Generation)
    generate_report(all_results)

def generate_report(results: List[TestResult]):
    """生成 JSON 和 Markdown 報告"""
    
    # --- JSON Report ---
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "model": MODEL_NAME,
        "total_samples": len(results),
        "results": [asdict(r) for r in results]
    }
    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
        
    # --- Statistics ---
    valid_json_count = sum(1 for r in results if r.json_valid)
    avg_accuracy = sum(r.accuracy_score for r in results) / len(results) if results else 0
    avg_speed = sum(r.metrics.get("speed_tps", 0) for r in results) / len(results) if results else 0
    
    # --- Markdown Summary ---
    md_content = f"""# VLM Benchmark Summary
- **Model**: {MODEL_NAME}
- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Samples Tested**: {len(results)}

## Key Metrics
- **JSON Validity Rate**: {valid_json_count}/{len(results)} ({valid_json_count/len(results)*100:.1f}%)
- **Average Accuracy**: {avg_accuracy:.1%}
- **Average Speed**: {avg_speed:.1f} tokens/s

## Detailed Results
| Job ID | Valid JSON | Accuracy | Specifics (Total/Date/Items) | Speed |
|--------|------------|----------|------------------------------|-------|
"""
    for r in results:
        match_str = ",".join([f"{k}:{v:.0f}" for k,v in r.field_match.items()])
        md_content += f"| {r.job_id} | {'✅' if r.json_valid else '❌'} | {r.accuracy_score:.2f} | {match_str} | {r.metrics.get('speed_tps', 0):.1f} |\n"

    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    print(f"\nReports generated:\n1. {REPORT_JSON_PATH}\n2. {REPORT_MD_PATH}")

if __name__ == "__main__":
    main()
