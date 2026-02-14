# backend/processing/vision_handler.py
"""
Vision Handler - OpenAI Compatible 視覺語言模型處理器

使用 OpenAI SDK 呼叫 Gemini / OpenRouter / DeepSeek 等相容 API，
直接從收據圖片生成結構化 JSON。

支援功能：
- 高精度手寫辨識
- Thinking / Reasoning (reasoning_effort)
- 繁體中文優化
- API 錯誤重試
- 可切換 Provider (只需修改 base_url + api_key)
"""
import logging
import base64
import time
import json
import os
import traceback
import numpy as np
import cv2
from openai import OpenAI

logger = logging.getLogger(__name__)


class VisionHandler:
    """
    視覺語言模型處理器 (OpenAI Compatible)
    
    使用 OpenAI SDK 進行視覺識別，輸出 JSON 格式。
    採用 "High Trust, Verify Later" 策略。
    
    支援 Provider:
    - Google Gemini: base_url = https://generativelanguage.googleapis.com/v1beta/openai/
    - OpenRouter:    base_url = https://openrouter.ai/api/v1
    - DeepSeek:      base_url = https://api.deepseek.com
    - OpenAI:        base_url = https://api.openai.com/v1  (預設)
    """

    # 預設 Prompt Template - 通用收據辨識 (電子/手寫/傳統)
    DEFAULT_PROMPT = """你是一個專業的台灣收據辨識助手。請辨識這張圖片中的收據內容（可能是電子發票、手寫收據、或傳統長條發票），並輸出為嚴格的 JSON 格式 (不要包含 Markdown code fence)。

請參考以下 JSON 範例輸出：
{
  "receipt_type": "電子發票證明聯",
  "header": {
      "supplier": "店家名", 
      "buyer": "買受人", 
      "invoice_id": "AB12345678", 
      "date": "2024-01-15"
  }, 
  "items": [
      {"name": "品項名稱", "qty": 1, "price": 100, "total": 100}
  ], 
  "summary": {
      "subtotal": 100,
      "tax": 5,
      "total": 105
  }, 
  "verification": {
      "handwritten_total_chinese": "壹佰零伍元整", 
      "stamp_shop_name": "店家章名稱",
      "qr_code_detected": true
  }
}

規則：
1. "receipt_type": 判斷收據類型，例如 "電子發票證明聯"、"免用統一發票收據"、"二聯式發票" 等。
2. "date": 請使用 ISO 格式 "YYYY-MM-DD"，若為民國年請轉換。
3. "invoice_id": 電子發票請填寫發票號碼 (如 AB12345678)。
4. "items": 請列出所有品項，確保 "total" = "qty" * "price"。
5. "summary.total": 必須等於 items 的總和 (或加上稅額)。
6. "verification": 辨識手寫的大寫金額、蓋章店名、是否有 QR Code。
7. 若欄位無法辨識或不存在，請留空字串 "" 或 null。

直接輸出 JSON，不要任何其他說明。"""

    def __init__(self, config: dict):
        """
        初始化 Vision Handler (OpenAI Compatible)
        
        Args:
            config: 配置字典，包含 vision_settings
        """
        vision_settings = config.get("vision_settings", {})
        
        # API 設定
        self.api_key = vision_settings.get("api_key") or os.environ.get("GOOGLE_API_KEY")
        self.base_url = vision_settings.get(
            "base_url", 
            "https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        
        if not self.api_key:
            logger.warning("[VisionHandler] 未設定 API Key，VLM 功能將無法使用")
        
        # 模型設定
        self.model_name = vision_settings.get("model_name", "gemini-2.5-flash-lite")
        self.temperature = vision_settings.get("temperature", 0.0)
        self.max_retries = vision_settings.get("max_retries", 3)
        self.timeout = vision_settings.get("timeout", 120)
        self.debug = vision_settings.get("debug", False)
        
        # Thinking 設定 (OpenAI compatible)
        self.reasoning_effort = vision_settings.get("reasoning_effort", None)
        
        # 初始化 OpenAI client
        self._client = None
        if self.api_key:
            self._init_client()
        
        logger.info(
            f"[VisionHandler] 初始化完成：model={self.model_name}, "
            f"base_url={self.base_url}, reasoning={self.reasoning_effort}"
        )

    def _init_client(self):
        """初始化 OpenAI client"""
        try:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            logger.info(f"[VisionHandler] OpenAI client 初始化成功 (base_url={self.base_url})")
        except Exception as e:
            logger.error(f"[VisionHandler] Client 初始化失敗: {e}")
            self._client = None

    def _prepare_image_b64(self, image_array: np.ndarray) -> str:
        """
        將 OpenCV 圖片編碼為 base64 data URI
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            
        Returns:
            str: data:image/jpeg;base64,... 格式的字串
        """
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        success, buffer = cv2.imencode('.jpg', image_array, encode_param)
        if not success:
            raise ValueError("圖片編碼失敗")
        
        b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
        
        if self.debug:
            img_size_kb = len(buffer) / 1024
            logger.debug(f"[VisionHandler] 圖片準備完成: {img_size_kb:.1f} KB")
            
        return f"data:image/jpeg;base64,{b64}"

    def process_handwritten(self, image_array: np.ndarray, prompt_context: str = "") -> tuple:
        """
        處理手寫收據 (舊版介面，內部呼叫 _call_with_retry)
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            prompt_context: 額外的上下文提示
            
        Returns:
            tuple: (result_json_str, stats_dict)
        """
        start_time = time.time()
        logger.info(f"[VisionHandler] 開始手寫收據識別 ({self.model_name})")
        
        if not self._client:
            error_msg = "Client 未初始化"
            return "", {"error": error_msg, "total_time_s": 0}

        try:
            image_url = self._prepare_image_b64(image_array)
            
            prompt = self.DEFAULT_PROMPT
            if prompt_context:
                prompt += f"\n\n【參考資訊】\n{prompt_context}"
            
            result_text = self._call_with_retry(prompt, image_url)
            result_text = self._clean_json_response(result_text)
            
            total_time = time.time() - start_time
            logger.info(f"[VisionHandler] ✓ 辨識完成，耗時 {total_time:.2f}s")
            
            stats = {
                "stage": "primary",
                "processor": "VLM-OpenAI",
                "model": self.model_name,
                "total_time_s": round(total_time, 3),
                "started_at": int(start_time),
                "completed_at": int(time.time())
            }
            
            return result_text, stats

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[VisionHandler] ✗ 辨識失敗: {e}", exc_info=True)
            return "", {"error": str(e), "total_time_s": round(total_time, 3)}

    def _call_with_retry(self, prompt: str, image_data_url: str) -> str:
        """
        呼叫 Chat Completions API，支援重試
        
        Args:
            prompt: 文字提示
            image_data_url: data:image/jpeg;base64,... 格式
            
        Returns:
            str: 模型回應的文字內容
        """
        last_error = None
        
        # 建構 API 參數
        api_kwargs = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": 4096,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }],
        }
        
        # 加入 reasoning_effort (若有設定)
        if self.reasoning_effort:
            api_kwargs["reasoning_effort"] = self.reasoning_effort
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"[VisionHandler] API 呼叫嘗試 {attempt}/{self.max_retries}")
                
                response = self._client.chat.completions.create(**api_kwargs)
                
                if self.debug:
                    logger.debug(f"[DEBUG] Response model: {response.model}, "
                                 f"usage: {response.usage}")
                
                # 提取回應文字
                result_text = response.choices[0].message.content
                
                if result_text:
                    return result_text
                else:
                    raise ValueError("回應中找不到文字內容")
                    
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                logger.warning(
                    f"[VisionHandler] API 呼叫失敗 (嘗試 {attempt}/{self.max_retries}): "
                    f"[{error_type}] {e}"
                )
                if self.debug:
                    logger.debug(f"[VisionHandler] 詳細錯誤堆疊:\n{traceback.format_exc()}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"[VisionHandler] 等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
        
        raise last_error

    def _clean_json_response(self, content: str) -> str:
        """清理 JSON 格式 (移除 markdown code fence)"""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:].strip()
        elif content.startswith("```"):
            content = content[3:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        return content

    def image_to_markdown(self, image_array: np.ndarray) -> tuple:
        """通用介面 (舊版相容)"""
        return self.process_image(image_array)

    def process_image(self, image_array: np.ndarray, prompt_context: str = "") -> tuple:
        """
        處理收據圖片 - 主要入口點 (VLM-First 架構)
        
        統一處理所有收據類型：電子發票、手寫收據、傳統發票。
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            prompt_context: 額外的上下文提示 (選填)
            
        Returns:
            tuple: (result_dict, stats_dict)
        """
        start_time = time.time()
        logger.info(f"[VisionHandler] 開始收據識別 ({self.model_name})")
        
        if not self._client:
            error_msg = "Client 未初始化"
            return {}, {"error": error_msg, "total_time_s": 0}

        try:
            image_url = self._prepare_image_b64(image_array)
            
            prompt = self.DEFAULT_PROMPT
            if prompt_context:
                prompt += f"\n\n【參考資訊】\n{prompt_context}"
            
            result_text = self._call_with_retry(prompt, image_url)
            result_text = self._clean_json_response(result_text)
            
            # 解析 JSON
            try:
                result_dict = json.loads(result_text)
            except json.JSONDecodeError as e:
                logger.warning(f"[VisionHandler] JSON 解析失敗: {e}")
                result_dict = {"raw_text": result_text}
            
            total_time = time.time() - start_time
            logger.info(f"[VisionHandler] ✓ 辨識完成，耗時 {total_time:.2f}s")
            
            stats = {
                "stage": "vlm",
                "processor": "VLM-OpenAI",
                "model": self.model_name,
                "total_time_s": round(total_time, 3),
                "started_at": int(start_time),
                "completed_at": int(time.time())
            }
            
            return result_dict, stats

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[VisionHandler] ✗ 辨識失敗: {e}", exc_info=True)
            return {}, {"error": str(e), "total_time_s": round(total_time, 3)}

    def describe_image(self, image_array: np.ndarray, custom_prompt: str = None) -> tuple:
        """描述圖片"""
        start_time = time.time()
        prompt = custom_prompt or "請描述這張圖片的內容。"
        
        if not self._client:
            return "", {"error": "Client 未初始化"}
        
        try:
            image_url = self._prepare_image_b64(image_array)
            text = self._call_with_retry(prompt, image_url)
            
            stats = {
                "processor": "VLM-OpenAI",
                "model": self.model_name,
                "total_time_s": round(time.time() - start_time, 3)
            }
            return text, stats
        except Exception as e:
            logger.error(f"[VisionHandler] 描述失敗: {e}")
            return "", {"error": str(e)}


# 測試用
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print("Usage: python vision_handler.py <image_path>")
        sys.exit(1)

    image = cv2.imread(sys.argv[1])
    handler = VisionHandler({"vision_settings": {"debug": True, "reasoning_effort": "medium"}})
    result, stats = handler.image_to_markdown(image)
    print(f"Result: {result}\nStats: {stats}")
