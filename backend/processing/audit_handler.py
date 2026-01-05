# backend/processing/audit_handler.py
"""
Audit Handler - 稽核處理器

使用 Qwen3 1.7B 進行資料驗證與稽核：
1. 電子發票：比對 VLM 輸出與 QR Code 解碼資料
2. 傳統發票：交叉驗證 VLM 輸出與 RapidOCR 結果

這是一個獨立的處理器，不修改現有的 llm_handler.py。
"""
import logging
import json
import re
import time
import ollama

logger = logging.getLogger(__name__)


class AuditHandler:
    """
    稽核處理器
    
    負責驗證 VLM 視覺識別結果的正確性，
    透過比對可信賴的參考資料（QR Code 或傳統 OCR）來減少幻覺。
    """

    def __init__(self, config: dict):
        """
        初始化 Audit Handler
        
        Args:
            config: 配置字典，包含 llm_settings
        """
        llm_settings = config.get("llm_settings", {})
        self.model_name = llm_settings.get("model_name", "qwen3:1.7b")
        self.temperature = llm_settings.get("temperature", 0.0)
        self.debug = llm_settings.get("debug", False)
        self.use_streaming = llm_settings.get("streaming", True)
        
        logger.info(f"AuditHandler 初始化：模型={self.model_name}, 流式={self.use_streaming}")

    def _call_llm(self, prompt: str, task_name: str = "稽核") -> str:
        """
        統一的 LLM 調用方法，支援流式和效能記錄
        """
        start_time = time.time()
        logger.debug(f"[Audit] 開始 {task_name}...")
        
        try:
            if self.use_streaming:
                return self._call_with_streaming(prompt, task_name, start_time)
            else:
                return self._call_without_streaming(prompt, task_name, start_time)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[Audit] {task_name} 失敗 (耗時 {elapsed:.2f}s): {e}")
            raise

    def _call_with_streaming(self, prompt: str, task_name: str, start_time: float) -> str:
        """流式調用"""
        chunks = []
        token_count = 0
        first_token_time = None
        
        stream = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": self.temperature},
            stream=True
        )
        
        for chunk in stream:
            if first_token_time is None:
                first_token_time = time.time()
                ttft = first_token_time - start_time
                if self.debug:
                    logger.debug(f"[Audit] TTFT: {ttft:.2f}s")
            
            content = chunk.get("message", {}).get("content", "")
            if content:
                chunks.append(content)
                token_count += 1
            
            if chunk.get("done", False):
                self._log_stats(chunk, start_time, token_count, task_name)
                break
        
        return "".join(chunks)

    def _call_without_streaming(self, prompt: str, task_name: str, start_time: float) -> str:
        """非流式調用"""
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": self.temperature}
        )
        
        elapsed = time.time() - start_time
        logger.info(f"[Audit] {task_name} 完成: {elapsed:.2f}s")
        
        return response.get("message", {}).get("content", "")

    def _log_stats(self, final_chunk: dict, start_time: float, token_count: int, task_name: str):
        """記錄效能統計"""
        total_time = time.time() - start_time
        eval_count = final_chunk.get("eval_count", token_count)
        eval_duration = final_chunk.get("eval_duration", 0) / 1e9
        
        gen_speed = eval_count / eval_duration if eval_duration > 0 else 0
        logger.info(f"[Audit] {task_name} 完成: {eval_count} tokens, {total_time:.2f}s ({gen_speed:.1f} tok/s)")

    def audit_electronic(self, vlm_markdown: str, qr_data: dict) -> dict:
        """
        稽核電子發票：比對 VLM 輸出與 QR Code 資料
        
        QR Code 資料被視為「真實來源」，VLM 輸出需要與之一致。
        
        Args:
            vlm_markdown: VLM 產生的 Markdown 文字
            qr_data: QR 解碼的發票資料
                {
                    "invoice_id": "AB12345678",
                    "date": "2024-01-15",
                    "seller_id": "12345678",
                    "total": 150,
                    ...
                }
        
        Returns:
            dict: {
                "is_valid": True,
                "confidence": 0.95,
                "discrepancies": [],
                "corrected_markdown": "...",
                "audit_notes": "..."
            }
        """
        logger.debug("開始稽核電子發票...")

        try:
            prompt = f"""你是一個發票稽核機器人。你的任務是比對 VLM 識別結果與 QR Code 真實資料。

## QR Code 資料（真實來源）
- 發票號碼: {qr_data.get('invoice_id', 'N/A')}
- 日期: {qr_data.get('date', 'N/A')}
- 賣方統編: {qr_data.get('seller_id', 'N/A')}
- 總金額: {qr_data.get('total', 'N/A')}

## VLM 識別結果
{vlm_markdown}

## 任務
1. 比對 VLM 識別的發票號碼、日期、總金額是否與 QR Code 一致
2. 如果有差異，找出並列出
3. 如果 VLM 有錯誤，提供修正後的 Markdown

請以 JSON 格式輸出：
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "discrepancies": ["差異1", "差異2"],
    "corrections": {{
        "invoice_id": "修正後的發票號碼（如需要）",
        "date": "修正後的日期（如需要）",
        "total": "修正後的金額（如需要）"
    }},
    "audit_notes": "稽核備註"
}}

只輸出 JSON，不要其他內容。"""

            response_content = self._call_llm(prompt, "電子發票稽核")
            result = self._parse_json_response(response_content)
            
            # 如果有修正，生成修正後的 Markdown
            if result.get("corrections"):
                corrected_markdown = self._apply_corrections(vlm_markdown, result["corrections"])
                result["corrected_markdown"] = corrected_markdown
            else:
                result["corrected_markdown"] = vlm_markdown
            
            logger.debug(f"電子發票稽核完成，有效性: {result.get('is_valid')}")
            return result

        except Exception as e:
            logger.error(f"電子發票稽核失敗: {e}", exc_info=True)
            return {
                "is_valid": False,
                "confidence": 0.0,
                "discrepancies": [f"稽核過程發生錯誤: {str(e)}"],
                "corrected_markdown": vlm_markdown,
                "audit_notes": "稽核失敗，使用原始識別結果"
            }

    def audit_traditional(self, vlm_markdown: str, ocr_text: str) -> dict:
        """
        稽核傳統發票：交叉驗證 VLM 與 RapidOCR 結果
        
        兩者都可能有錯誤，需要智慧比對找出最可能正確的內容。
        
        Args:
            vlm_markdown: VLM 產生的 Markdown 文字
            ocr_text: RapidOCR 產生的純文字
        
        Returns:
            dict: {
                "is_valid": True,
                "confidence": 0.75,
                "discrepancies": ["差異說明"],
                "corrected_markdown": "...",
                "audit_notes": "..."
            }
        """
        logger.debug("開始稽核傳統發票...")

        try:
            prompt = f"""你是一個發票稽核機器人。你需要比對兩種 OCR 結果，找出可能的錯誤。

## VLM 視覺識別結果 (Markdown)
{vlm_markdown}

## 傳統 OCR 結果 (純文字)
{ocr_text}

## 任務
1. 比對兩者的關鍵資訊（發票號碼、日期、金額、品項）
2. 如果有差異，判斷哪個更可能正確
3. 特別注意：
   - 數字容易混淆（0/O, 1/I/l, 6/8）
   - 相似字形（每/海, 圓/園）
   - 金額計算是否正確

請以 JSON 格式輸出：
{{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "discrepancies": ["差異描述"],
    "preferred_source": "vlm" 或 "ocr" 或 "mixed",
    "corrections": {{
        "key": "修正值"
    }},
    "audit_notes": "稽核備註，說明判斷依據"
}}

只輸出 JSON，不要其他內容。"""

            response_content = self._call_llm(prompt, "傳統發票稽核")
            result = self._parse_json_response(response_content)
            
            # 根據判斷結果生成修正後的 Markdown
            if result.get("corrections"):
                corrected_markdown = self._apply_corrections(vlm_markdown, result["corrections"])
                result["corrected_markdown"] = corrected_markdown
            else:
                result["corrected_markdown"] = vlm_markdown
            
            logger.debug(f"傳統發票稽核完成，信心度: {result.get('confidence')}")
            return result

        except Exception as e:
            logger.error(f"傳統發票稽核失敗: {e}", exc_info=True)
            return {
                "is_valid": False,
                "confidence": 0.5,
                "discrepancies": [f"稽核過程發生錯誤: {str(e)}"],
                "corrected_markdown": vlm_markdown,
                "audit_notes": "稽核失敗，使用 VLM 識別結果"
            }

    def _parse_json_response(self, content: str) -> dict:
        """
        解析 LLM JSON 回應
        
        Args:
            content: LLM 回應內容
            
        Returns:
            dict: 解析後的 JSON 物件
        """
        try:
            # 嘗試直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 嘗試提取 JSON 部分
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
            
            # 回傳預設結構
            logger.warning("無法解析 JSON 回應，使用預設值")
            return {
                "is_valid": True,
                "confidence": 0.5,
                "discrepancies": [],
                "audit_notes": "無法解析稽核結果"
            }

    def _apply_corrections(self, markdown: str, corrections: dict) -> str:
        """
        將修正套用到 Markdown
        
        Args:
            markdown: 原始 Markdown 內容
            corrections: 修正字典
            
        Returns:
            str: 修正後的 Markdown
        """
        corrected = markdown
        
        for key, value in corrections.items():
            if not value:
                continue
            
            # 嘗試找到並替換對應的值
            # 這是一個簡化的實作，實際可能需要更複雜的模式匹配
            if key == "invoice_id" and value:
                # 發票號碼格式：XX-12345678 或 XX12345678
                pattern = r'([A-Z]{2}[-]?\d{8})'
                corrected = re.sub(pattern, value, corrected, count=1)
            
            elif key == "total" and value:
                # 總金額：**合計**: 數字
                pattern = r'(\*\*合計\*\*:\s*)\d+'
                corrected = re.sub(pattern, f'\\1{value}', corrected)
        
        return corrected

    def quick_validate(self, vlm_markdown: str, reference_amount: int) -> bool:
        """
        快速驗證：僅檢查總金額是否一致
        
        Args:
            vlm_markdown: VLM 產生的 Markdown
            reference_amount: 參考金額（來自 QR Code）
            
        Returns:
            bool: 金額是否一致
        """
        # 從 Markdown 中提取金額
        amount_pattern = r'\*\*合計\*\*:\s*(\d+)'
        match = re.search(amount_pattern, vlm_markdown)
        
        if match:
            vlm_amount = int(match.group(1))
            return vlm_amount == reference_amount
        
        return False


# 測試用
if __name__ == "__main__":
    print("AuditHandler 模組載入成功")
    
    handler = AuditHandler({
        "llm_settings": {
            "model_name": "qwen3:1.7b",
            "temperature": 0.0
        }
    })
    
    # 測試電子發票稽核
    test_vlm = """# 全聯福利中心

**發票號碼**: AB-12345678
**日期**: 2024/01/15

| 品名 | 數量 | 單價 | 小計 |
|------|------|------|------|
| 鮮奶 | 1 | 65 | 65 |

**合計**: 65
"""
    
    test_qr = {
        "invoice_id": "AB12345678",
        "date": "2024-01-15",
        "total": 65,
        "seller_id": "12345678"
    }
    
    print("\n測試電子發票稽核...")
    result = handler.audit_electronic(test_vlm, test_qr)
    print(json.dumps(result, ensure_ascii=False, indent=2))
