# backend/processing/gemma_corrector.py
"""
GEMMA 修正器 - 使用 gemma3:4b VLM 修正有問題的識別結果

當 Python 驗算器發現問題時，使用此模組重新識別並修正。
"""
import logging
import json
import re
import time
import base64
import cv2
import numpy as np
import ollama

logger = logging.getLogger(__name__)


class GemmaCorrector:
    """
    GEMMA3 VLM 修正處理器
    
    使用 gemma3:4b 重新識別有問題的收據，
    結合原始識別結果和發現的問題來進行修正。
    """
    
    def __init__(self, config: dict):
        """初始化修正器"""
        gemma_settings = config.get("gemma_settings", {})
        self.model_name = gemma_settings.get("model_name", "gemma3:4b")
        self.temperature = gemma_settings.get("temperature", 0.1)
        self.num_predict = gemma_settings.get("num_predict", 4096)
        self.num_ctx = gemma_settings.get("num_ctx", 8192)
        self.use_streaming = gemma_settings.get("streaming", True)
        self.debug = gemma_settings.get("debug", False)
        
        logger.info(f"GemmaCorrector 初始化：model={self.model_name}")
    
    def correct(
        self, 
        image_array: np.ndarray, 
        original_result: dict, 
        issues: list[str]
    ) -> dict:
        """
        修正有問題的識別結果
        
        Args:
            image_array: 原始圖片
            original_result: 原始識別結果
            issues: 驗算發現的問題列表
            
        Returns:
            dict: 修正後的結果
        """
        start_time = time.time()
        logger.info(f"[GEMMA] 開始修正，共 {len(issues)} 個問題")
        
        try:
            # 編碼圖片
            base64_image = self._encode_image(image_array)
            
            # 構建修正 prompt
            prompt = self._build_correction_prompt(original_result, issues)
            
            # 調用 GEMMA
            if self.use_streaming:
                response_text = self._call_with_streaming(prompt, base64_image)
            else:
                response_text = self._call_without_streaming(prompt, base64_image)
            
            # 解析回應
            corrected_data = self._parse_response(response_text)
            
            # 記錄效能
            total_time = time.time() - start_time
            logger.info(f"[GEMMA] ✓ 修正完成，耗時 {total_time:.2f}s")
            
            return {
                "success": True,
                "data": corrected_data,
                "correction_time": total_time,
                "correction": {
                    "source": "gemma",
                    "timestamp": int(time.time()),
                    "description": f"GEMMA3 自動修正，共處理 {len(issues)} 個問題"
                }
            }
            
        except Exception as e:
            logger.error(f"[GEMMA] ✗ 修正失敗: {e}", exc_info=True)
            return {
                "success": False,
                "data": original_result,  # 失敗時返回原始結果
                "error": str(e),
                "correction": None
            }
    
    def _encode_image(self, image_array: np.ndarray) -> str:
        """編碼圖片為 base64"""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        success, buffer = cv2.imencode('.jpg', image_array, encode_param)
        if not success:
            raise ValueError("圖片編碼失敗")
        return base64.b64encode(buffer).decode('utf-8')
    
    def _build_correction_prompt(self, original: dict, issues: list[str]) -> str:
        """建構修正用 prompt"""
        original_json = json.dumps(original, ensure_ascii=False, indent=2)
        issues_text = "\n".join(f"- {issue}" for issue in issues)
        
        prompt = f"""你是一個發票驗證專家。以下收據資料有異常需要修正。

【原始識別結果】
```json
{original_json}
```

【發現的問題】
{issues_text}

【修正任務】
1. 請仔細查看圖片，重新確認有問題的欄位
2. 特別注意數字的識別（可能混淆：0/O, 1/I/l, 6/8, 2/Z）
3. 確保 qty × price = total 的計算正確
4. 確保所有品項 total 加總等於 summary.total

【輸出格式】
請輸出修正後的完整 JSON，格式與原始格式相同。只輸出 JSON，不要其他說明。
"""
        return prompt
    
    def _call_with_streaming(self, prompt: str, base64_image: str) -> str:
        """流式調用 - 詳細日誌版本"""
        logger.debug("[GEMMA] 使用流式調用...")
        
        chunks = []
        thinking_chunks = []
        token_count = 0
        thinking_token_count = 0
        first_token_time = None
        start_time = time.time()
        
        # 批次輸出緩衝區
        content_buffer = ""
        thinking_buffer = ""
        LOG_BATCH_SIZE = 50
        
        stream = ollama.chat(
            model=self.model_name,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [base64_image]
            }],
            options={
                "temperature": self.temperature,
                "num_predict": self.num_predict,
                "num_ctx": self.num_ctx
            },
            stream=True,
            think=False  # 顯式禁用思考模式，避免 400 錯誤
        )
        
        for chunk in stream:
            if first_token_time is None:
                first_token_time = time.time()
                ttft = first_token_time - start_time
                logger.info(f"[GEMMA] 首個回應時間 (TTFT): {ttft:.2f}s")
            
            # 取得 message 內容
            message = chunk.get("message", {})
            content = message.get("content", "")
            thinking = message.get("thinking", "")
            
            # 收集思考內容
            if thinking:
                thinking_chunks.append(thinking)
                thinking_buffer += thinking
                thinking_token_count += 1
                
                # 批次輸出 thinking log
                if len(thinking_buffer) >= LOG_BATCH_SIZE:
                    display = thinking_buffer.replace('\n', ' ')
                    logger.debug(f"[GEMMA 思考] {display}")
                    thinking_buffer = ""
            
            # 收集實際內容
            if content:
                chunks.append(content)
                content_buffer += content
                token_count += 1
                
                # 批次輸出 content log
                if len(content_buffer) >= LOG_BATCH_SIZE:
                    display = content_buffer.replace('\n', ' ')
                    logger.debug(f"[GEMMA 輸出] {display}")
                    content_buffer = ""
            
            # 每 100 個 token 報告一次進度
            total_tokens = token_count + thinking_token_count
            if total_tokens > 0 and total_tokens % 100 == 0:
                elapsed = time.time() - first_token_time
                speed = total_tokens / elapsed if elapsed > 0 else 0
                total_chars = len("".join(chunks)) + len("".join(thinking_chunks))
                logger.info(f"[GEMMA] 進度: {total_tokens} tokens ({speed:.1f}/s), {total_chars} 字元")
            
            if chunk.get("done", False):
                # 輸出剩餘緩衝區內容
                if thinking_buffer:
                    logger.debug(f"[GEMMA 思考] {thinking_buffer.replace(chr(10), ' ')}")
                if content_buffer:
                    logger.debug(f"[GEMMA 輸出] {content_buffer.replace(chr(10), ' ')}")
                break
        
        elapsed = time.time() - start_time
        final_content = "".join(chunks)
        final_thinking = "".join(thinking_chunks)
        
        # 記錄最終統計
        logger.info(f"[GEMMA] 完成: content={len(final_content)} 字元, thinking={len(final_thinking)} 字元")
        logger.debug(f"[GEMMA] 流式調用完成: {elapsed:.2f}s")
        
        # 如果 content 為空但 thinking 有內容
        if not final_content and final_thinking:
            logger.warning("[GEMMA] content 為空，但 thinking 有內容")
            logger.info(f"[GEMMA] 思考內容預覽: {final_thinking[:200]}...")
        
        return final_content
    
    def _call_without_streaming(self, prompt: str, base64_image: str) -> str:
        """非流式調用"""
        response = ollama.chat(
            model=self.model_name,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [base64_image]
            }],
            options={
                "temperature": self.temperature,
                "num_predict": self.num_predict,
                "num_ctx": self.num_ctx
            }
        )
        return response.get("message", {}).get("content", "")
    
    def _parse_response(self, response_text: str) -> dict:
        """解析回應中的 JSON"""
        # 記錄原始回應
        logger.debug(f"[GEMMA] 原始回應長度: {len(response_text)} 字元")
        logger.debug(f"[GEMMA] 回應前100字: {response_text[:100]}")
        
        # 清理可能的 code fence
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            result = json.loads(text)
            logger.info(f"[GEMMA] ✓ 成功解析 JSON（{len(str(result))} 字元）")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"[GEMMA] JSON 解析失敗: {e}")
            # 嘗試提取 JSON
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(0))
                    logger.info(f"[GEMMA] ✓ 從文字中提取 JSON 成功")
                    return result
                except:
                    logger.warning(f"[GEMMA] 提取的 JSON 也無法解析")
            
            logger.error("[GEMMA] ✗ 無法解析回應中的 JSON")
            logger.debug(f"[GEMMA] 失敗的文字: {text[:500]}")
            return {}


# 測試用
if __name__ == "__main__":
    print("GemmaCorrector 模組載入成功")
