# backend/processing/vision_handler.py
"""
Vision Handler - Qwen3 VL 視覺語言模型處理器

使用 Qwen3 VL 2B 進行「類 OCR」操作，
直接從收據圖片生成 Markdown 格式的結構化文字。

這是「OCR 結果」：忠實呈現發票視覺內容，
包含商家名稱、發票號碼、品項表格等。

支援功能：
- 流式輸出（streaming）模式
- 詳細效能記錄（token/s, eval time 等）
- 除錯模式
"""
import logging
import base64
import time
import numpy as np
import cv2
import ollama

logger = logging.getLogger(__name__)


class VisionHandler:
    """
    視覺語言模型處理器
    
    使用 Qwen3 VL 進行視覺識別，輸出 Markdown 格式。
    這取代了傳統 OCR + 排版重建的流程，
    讓 VLM 直接「閱讀」發票並輸出結構化內容。
    """

    def __init__(self, config: dict):
        """
        初始化 Vision Handler
        
        Args:
            config: 配置字典，包含 vision_settings
        """
        vision_settings = config.get("vision_settings", {})
        self.model_name = vision_settings.get("model_name", "qwen3-vl:2b")
        self.temperature = vision_settings.get("temperature", 0.0)
        self.debug = vision_settings.get("debug", False)
        self.use_streaming = vision_settings.get("streaming", True)
        self.timeout = vision_settings.get("timeout", 120)
        self.think_mode = vision_settings.get("think_mode", True)
        
        # 從 test.py 的最佳參數
        self.num_predict = vision_settings.get("num_predict", 4096)
        self.num_ctx = vision_settings.get("num_ctx", 8192)
        self.repeat_penalty = vision_settings.get("repeat_penalty", 1.2)
        self.top_p = vision_settings.get("top_p", 0.3)
        
        logger.info(f"VisionHandler 初始化：model={self.model_name}, think={self.think_mode}")

    def _encode_image(self, image_array: np.ndarray) -> str:
        """
        將 OpenCV 圖片編碼為 base64 字串
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            
        Returns:
            str: base64 編碼的圖片字串
        """
        # 編碼為 JPEG 格式（比 PNG 更快）
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        success, buffer = cv2.imencode('.jpg', image_array, encode_param)
        if not success:
            raise ValueError("圖片編碼失敗")
        
        # 轉為 base64
        base64_image = base64.b64encode(buffer).decode('utf-8')
        
        if self.debug:
            img_size_kb = len(buffer) / 1024
            logger.debug(f"[VLM Debug] 圖片編碼完成: {img_size_kb:.1f} KB")
        
        return base64_image

    def process_handwritten(self, image_array: np.ndarray) -> tuple:
        """
        處理手寫收據 - 使用專用 prompt
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            
        Returns:
            tuple: (result_text, stats_dict)
                - result_text: VLM 輸出的文字（可能包含 JSON）
                - stats_dict: 處理統計資訊
        """
        start_time = time.time()
        logger.info(f"[VLM] 開始手寫收據識別 (模型: {self.model_name})")

        try:
            base64_image = self._encode_image(image_array)
            
            # 手寫收據專用 prompt - 簡化版，避免思考陷阱
            prompt = """你是專業的收據資料提取 API。請將圖片中的內容轉為 JSON。

**重點：**
1. **提取手寫字**：品名、數量、單價、總價
2. **數值**：盡量轉為數字，不確定就用字串
3. **日期**：直接使用原始格式即可（例如 20241128 或 1141128）
4. **看不清的欄位**：填 null

**輸出 JSON：**
{
    "receipt_type": "免用統一發票收據",
    "header": {
        "buyer": "買受人",
        "date": "原始日期（可以是 yyyymmdd 或 yyymmdd 格式）",
        "supplier": "供應商名（如有）"
    },
    "items": [
        { "name": "品名", "qty": 1, "price": 100, "total": 100 }
    ],
    "summary": {
        "total": 100
    },
    "verification": {
        "handwritten_total_chinese": "中文大寫金額",
        "stamp_shop_name": "店章店名"
    }
}

直接輸出 JSON，不要其他說明。"""

            if self.use_streaming:
                result, stats = self._call_with_streaming(prompt, base64_image)
            else:
                result, stats = self._call_without_streaming(prompt, base64_image)
            
            total_time = time.time() - start_time
            logger.info(f"[VLM] ✓ 手寫收據識別完成，耗時 {total_time:.2f}s")
            
            return result, stats

        except Exception as e:
            logger.error(f"[VLM] ✗ 手寫收據識別失敗: {e}", exc_info=True)
            return "", {"error": str(e), "total_time_s": time.time() - start_time}

    def image_to_markdown(self, image_array: np.ndarray) -> tuple:
        """
        將收據圖片轉換為 JSON 格式
        
        這是通用方法，內部會調用 process_handwritten
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            
        Returns:
            tuple: (result_text, stats_dict)
        """
        return self.process_handwritten(image_array)

    def _call_with_streaming(self, prompt: str, base64_image: str) -> tuple:
        """
        使用流式模式調用 Ollama
        
        流式模式可以：
        - 看到生成進度
        - 避免長時間無回應的問題
        - 取得詳細的效能統計
        
        注意：某些模型（如 qwen3）會把思考過程放在 thinking 欄位，
        如果 content 為空但 thinking 有內容，需要收集 thinking。
        
        Returns:
            tuple: (result_text, stats_dict)
        """
        logger.debug("[VLM] 使用流式模式調用...")
        
        chunks = []
        thinking_chunks = []
        token_count = 0
        thinking_token_count = 0
        first_token_time = None
        start_time = time.time()
        stats_dict = {}  # 儲存統計資料
        
        # 用於批次輸出 log 的緩衝區
        content_buffer = ""
        thinking_buffer = ""
        last_log_len = 0
        LOG_BATCH_SIZE = 50  # 每累積約 50 字元輸出一次 log
        
        try:
            # 構建 options，使用 test.py 的最佳參數
            chat_options = {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
                "num_ctx": self.num_ctx,
                "repeat_penalty": self.repeat_penalty,
                "top_p": self.top_p
            }
            
            stream = ollama.chat(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [base64_image]
                    }
                ],
                options=chat_options,
                stream=True,
                think=self.think_mode  # Qwen3 思考模式開關
            )
            
            for chunk in stream:
                if first_token_time is None:
                    first_token_time = time.time()
                    ttft = first_token_time - start_time
                    logger.info(f"[VLM] 首個回應時間 (TTFT): {ttft:.2f}s")
                
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
                    if self.debug and len(thinking_buffer) >= LOG_BATCH_SIZE:
                        display = thinking_buffer.replace('\n', ' ')
                        logger.debug(f"[VLM 思考] {display}")
                        thinking_buffer = ""
                
                # 收集實際內容
                if content:
                    chunks.append(content)
                    content_buffer += content
                    token_count += 1
                    
                    # 批次輸出 content log
                    if self.debug and len(content_buffer) >= LOG_BATCH_SIZE:
                        display = content_buffer.replace('\n', ' ')
                        logger.debug(f"[VLM 輸出] {display}")
                        content_buffer = ""
                
                # 每 100 個 token 或每 5 秒報告一次進度
                total_tokens = token_count + thinking_token_count
                if total_tokens > 0 and total_tokens % 100 == 0:
                    elapsed = time.time() - first_token_time
                    speed = total_tokens / elapsed if elapsed > 0 else 0
                    total_chars = len("".join(chunks)) + len("".join(thinking_chunks))
                    logger.info(f"[VLM] 進度: {total_tokens} tokens ({speed:.1f}/s), {total_chars} 字元")
                
                # 檢查是否完成
                if chunk.get("done", False):
                    # 輸出剩餘的緩衝區內容
                    if self.debug:
                        if thinking_buffer:
                            logger.debug(f"[VLM 思考] {thinking_buffer.replace(chr(10), ' ')}")
                        if content_buffer:
                            logger.debug(f"[VLM 輸出] {content_buffer.replace(chr(10), ' ')}")
                    
                    stats_dict = self._log_final_stats(chunk, start_time, token_count + thinking_token_count)
                    break
            
            # 組合最終結果
            final_content = "".join(chunks)
            final_thinking = "".join(thinking_chunks)
            
            # 如果 content 為空但 thinking 有內容，嘗試使用 thinking
            if not final_content and final_thinking:
                logger.warning(f"[VLM] content 為空，但 thinking 有 {len(final_thinking)} 字元")
                logger.warning("[VLM] 注意：此模型可能需要關閉思考模式。嘗試使用 thinking 內容作為輸出...")
                # 可選：使用 thinking 作為輸出（可能包含非結構化內容）
                # final_content = final_thinking
            
            if not final_content:
                logger.warning("[VLM] 警告：沒有收到任何 content！")
                if final_thinking:
                    logger.info(f"[VLM] 思考內容預覽: {final_thinking[:200]}...")
            else:
                logger.info(f"[VLM] 完成: content={len(final_content)} 字元, thinking={len(final_thinking)} 字元")
            
            return final_content, stats_dict
            
        except Exception as e:
            logger.error(f"[VLM] 流式調用錯誤: {e}", exc_info=True)
            accumulated = "".join(chunks) if 'chunks' in locals() else ""
            if accumulated:
                logger.error(f"[VLM] 部分內容: {accumulated[:300]}...")
            raise

    def _call_without_streaming(self, prompt: str, base64_image: str) -> tuple:
        """
        使用非流式模式調用 Ollama
        
        Returns:
            tuple: (result_text, stats_dict)
        """
        logger.debug("[VLM] 使用非流式模式調用...")
        start_time = time.time()
        
        response = ollama.chat(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [base64_image]
                }
            ],
            options={
                "temperature": self.temperature
            },
            format="json",  # 強制 JSON 輸出
            think=self.think_mode  # Qwen3 思考模式開關
        )
        
        elapsed = time.time() - start_time
        logger.info(f"[VLM] 非流式調用完成: {elapsed:.2f}s")
        
        # 記錄效能統計（如果有）
        if self.debug and response:
            self._log_response_stats(response)
        
        # 構建 stats
        stats_dict = {
            "stage": "primary",
            "processor": "VLM",
            "model": self.model_name,
            "total_time_s": round(elapsed, 3),
            "started_at": int(start_time),
            "completed_at": int(time.time())
        }
        
        return response.get("message", {}).get("content", ""), stats_dict

    def _log_final_stats(self, final_chunk: dict, start_time: float, token_count: int) -> dict:
        """記錄並返回最終效能統計"""
        total_time = time.time() - start_time
        
        # 從 Ollama 回應中提取效能資訊
        eval_count = final_chunk.get("eval_count", token_count)
        eval_duration = final_chunk.get("eval_duration", 0) / 1e9  # 納秒轉秒
        prompt_eval_count = final_chunk.get("prompt_eval_count", 0)
        prompt_eval_duration = final_chunk.get("prompt_eval_duration", 0) / 1e9
        
        # 計算速度
        gen_speed = eval_count / eval_duration if eval_duration > 0 else 0
        prompt_speed = prompt_eval_count / prompt_eval_duration if prompt_eval_duration > 0 else 0
        
        logger.info(f"[VLM] 效能統計:")
        logger.info(f"  - 總耗時: {total_time:.2f}s")
        logger.info(f"  - Prompt 處理: {prompt_eval_count} tokens, {prompt_eval_duration:.2f}s ({prompt_speed:.1f} tok/s)")
        logger.info(f"  - 生成: {eval_count} tokens, {eval_duration:.2f}s ({gen_speed:.1f} tok/s)")
        
        # 返回 stats dict
        return {
            "stage": "primary",
            "processor": "VLM",
            "model": self.model_name,
            "total_time_s": round(total_time, 3),
            "ttft_s": None,  # 需要從調用處傳入
            "prompt_tokens": prompt_eval_count,
            "prompt_time_s": round(prompt_eval_duration, 3),
            "gen_tokens": eval_count,
            "gen_time_s": round(eval_duration, 3),
            "gen_speed_tps": round(gen_speed, 1),
            "started_at": int(start_time),
            "completed_at": int(time.time())
        }

    def _log_response_stats(self, response: dict):
        """記錄回應統計（非流式模式）"""
        eval_count = response.get("eval_count", 0)
        eval_duration = response.get("eval_duration", 0) / 1e9
        prompt_eval_count = response.get("prompt_eval_count", 0)
        prompt_eval_duration = response.get("prompt_eval_duration", 0) / 1e9
        
        if eval_duration > 0:
            gen_speed = eval_count / eval_duration
            logger.debug(f"[VLM Debug] 生成速度: {gen_speed:.1f} tok/s")
        if prompt_eval_duration > 0:
            prompt_speed = prompt_eval_count / prompt_eval_duration
            logger.debug(f"[VLM Debug] Prompt 處理速度: {prompt_speed:.1f} tok/s")

    def _clean_json_response(self, content: str) -> str:
        """
        清理 JSON 回應內容
        
        移除可能的 code fence 包裝（```json ... ```）
        
        Args:
            content: 原始回應內容
            
        Returns:
            str: 清理後的 JSON 內容
        """
        content = content.strip()
        
        # 移除開頭的 ```json 或 ```
        if content.startswith("```json"):
            content = content[len("```json"):].strip()
        elif content.startswith("```"):
            content = content[3:].strip()
        
        # 移除結尾的 ```
        if content.endswith("```"):
            content = content[:-3].strip()
        
        return content

    def describe_image(self, image_array: np.ndarray, custom_prompt: str = None) -> str:
        """
        使用自定義 prompt 描述圖片
        
        提供更靈活的視覺識別功能。
        
        Args:
            image_array: OpenCV 格式的圖片陣列
            custom_prompt: 自定義 prompt（可選）
            
        Returns:
            str: VLM 的回應
        """
        prompt = custom_prompt or "請描述這張圖片的內容。"
        
        try:
            base64_image = self._encode_image(image_array)
            
            if self.use_streaming:
                return self._call_with_streaming(prompt, base64_image)
            else:
                return self._call_without_streaming(prompt, base64_image)

        except Exception as e:
            logger.error(f"圖片描述失敗: {e}", exc_info=True)
            return f"錯誤: {str(e)}"


# 測試用
if __name__ == "__main__":
    import sys

    # 設置 logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python vision_handler.py <image_path> [--no-stream] [--debug]")
        sys.exit(1)

    image_path = sys.argv[1]
    use_streaming = "--no-stream" not in sys.argv
    debug_mode = "--debug" in sys.argv
    
    image = cv2.imread(image_path)

    if image is None:
        print(f"無法讀取圖片: {image_path}")
        sys.exit(1)

    handler = VisionHandler({
        "vision_settings": {
            "model_name": "qwen3-vl:2b",
            "temperature": 0.0,
            "streaming": use_streaming,
            "debug": debug_mode
        }
    })
    
    print(f"正在進行視覺識別 (流式: {use_streaming}, 除錯: {debug_mode})...")
    result = handler.image_to_markdown(image)
    
    print("\n" + "=" * 50)
    print("Markdown 輸出:")
    print("=" * 50)
    print(result)
    print("=" * 50)
    print(f"輸出長度: {len(result)} 字元")
