# backend/processing/vision_handler.py
"""
Vision Handler - Gemini 2.5 Flash Lite 視覺語言模型處理器 (google-genai SDK)

使用 Google AI Studio 的 Gemini 2.5 Flash Lite 進行收據圖片識別，
直接從收據圖片生成結構化 JSON，並支援 Thinking (思考模式)。

支援功能：
- 高精度手寫辨識 (Gemini 2.5 Flash Lite)
- Thinking / Reasoning (思考模式)
- 繁體中文優化
- API 錯誤重試
"""
import logging
import base64
import time
import json
import os
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Lazy import to avoid startup errors if not installed
_genai = None
_types = None

def _get_genai_stuff():
    """Lazy load google.genai modules"""
    global _genai, _types
    if _genai is None:
        try:
            from google import genai
            from google.genai import types
            _genai = genai
            _types = types
        except ImportError:
            raise ImportError("請安裝 google-genai: pip install google-genai")
    return _genai, _types


class VisionHandler:
    """
    視覺語言模型處理器 (Gemini 2.5 版本)
    
    使用 Gemini 2.5 Flash Lite 進行視覺識別，輸出 JSON 格式。
    採用 "High Trust, Verify Later" 策略。
    """

    # 預設 Prompt Template
    DEFAULT_PROMPT = """你是一個專業的台灣收據辨識助手。請辨識這張圖片中的手寫或印刷收據內容，並輸出為嚴格的 JSON 格式 (不要包含 Markdown code fence)。

請參考以下 JSON 範例輸出：
{
  "receipt_type": "免用統一發票收據",  
  "header": {
      "supplier": "店家名", 
      "buyer": "買受人", 
      "invoice_id": "", 
      "date": "中華民國1140930"
  }, 
  "items": [
      {"name": "品項名稱", "qty": 1, "price": 100, "total": 100}
  ], 
  "summary": {
      "total": 100
  }, 
  "verification": {
      "handwritten_total_chinese": "壹仟元整", 
      "stamp_shop_name": "店家章名稱"
  }
}

規則：
1. "receipt_type": 依據圖片內容判斷，例如 "免用統一發票收據"、"電子發票證明聯" 等。
2. "date": 請轉換為 "中華民國YYYMMDD" 或 "YYYY-MM-DD" 格式。
3. "items": 請列出所有品項，確保 "total" = "qty" * "price"。
4. "summary.total": 必須等於 items 的總和。
5. "verification": 請辨識手寫的大寫金額 (handwritten_total_chinese) 與蓋章的店名 (stamp_shop_name) 用於後續驗證。
6. 若欄位無法辨識或不存在，請留空字串 "" 或 null。

直接輸出 JSON，不要任何其他說明。"""

    def __init__(self, config: dict):
        """
        初始化 Vision Handler (Gemini)
        
        Args:
            config: 配置字典，包含 vision_settings
        """
        vision_settings = config.get("vision_settings", {})
        
        # API 設定
        self.api_key = vision_settings.get("api_key") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("[VisionHandler] 未設定 GOOGLE_API_KEY，Gemini 功能將無法使用")
        
        # 模型設定
        self.model_name = vision_settings.get("model_name", "gemini-2.5-flash-lite")
        self.temperature = vision_settings.get("temperature", 0.0)
        self.max_retries = vision_settings.get("max_retries", 3)
        self.timeout = vision_settings.get("timeout", 120)
        self.debug = vision_settings.get("debug", False)
        
        # Thinking 設定
        self.think_mode = vision_settings.get("think_mode", False)
        self.thinking_budget = vision_settings.get("thinking_budget", -1) 
        
        # 初始化 Gemini client
        self._client = None
        if self.api_key:
            self._init_client()
        
        logger.info(f"[VisionHandler] 初始化完成：model={self.model_name}, think={self.think_mode}")

    def _init_client(self):
        """初始化 Gemini client (google-genai 版)"""
        try:
            genai, types = _get_genai_stuff()
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"[VisionHandler] Gemini genai.Client 初始化成功")
        except Exception as e:
            logger.error(f"[VisionHandler] Gemini client 初始化失敗: {e}")
            self._client = None

    def _prepare_image_part(self, image_array: np.ndarray):
        """
        將 OpenCV 圖片準備為 Gemini Part
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
        """
        _, types = _get_genai_stuff()
        
        # 編碼為 JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        success, buffer = cv2.imencode('.jpg', image_array, encode_param)
        if not success:
            raise ValueError("圖片編碼失敗")
        
        if self.debug:
            img_size_kb = len(buffer) / 1024
            logger.debug(f"[VisionHandler] 圖片準備完成: {img_size_kb:.1f} KB")
            
        return types.Part.from_bytes(
            data=buffer.tobytes(),
            mime_type="image/jpeg"
        )

    def process_handwritten(self, image_array: np.ndarray, prompt_context: str = "") -> tuple:
        """
        處理手寫收據 - 使用 Gemini 2.5 Flash Lite
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
            prompt_context: 額外的上下文提示
            
        Returns:
            tuple: (result_json_str, stats_dict)
        """
        start_time = time.time()
        logger.info(f"[VisionHandler] 開始手寫收據識別 (Gemini 2.5: {self.model_name})")
        
        if not self._client:
            error_msg = "Gemini client 未初始化"
            return "", {"error": error_msg, "total_time_s": 0}

        try:
            # 準備輸入元件
            image_part = self._prepare_image_part(image_array)
            
            prompt = self.DEFAULT_PROMPT
            if prompt_context:
                prompt += f"\n\n【參考資訊】\n{prompt_context}"
            
            # 呼叫 API (with retry)
            result_text, thoughts = self._call_with_retry(prompt, image_part)
            
            # 清理結果
            result_text = self._clean_json_response(result_text)
            
            total_time = time.time() - start_time
            logger.info(f"[VisionHandler] ✓ 辨識完成，耗時 {total_time:.2f}s")
            
            stats = {
                "stage": "primary",
                "processor": "Gemini-2.5",
                "model": self.model_name,
                "total_time_s": round(total_time, 3),
                "has_thoughts": bool(thoughts),
                "started_at": int(start_time),
                "completed_at": int(time.time())
            }
            
            return result_text, stats

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[VisionHandler] ✗ 辨識失敗: {e}", exc_info=True)
            return "", {"error": str(e), "total_time_s": round(total_time, 3)}

    def _call_with_retry(self, prompt: str, image_part) -> tuple:
        """呼叫 Gemini API，支援重試與思考模式"""
        _, types = _get_genai_stuff()
        last_error = None
        
        # 設定生成配置
        config = {
            "temperature": self.temperature,
            "max_output_tokens": 4096,
        }
        
        # 如果啟用思考模式
        if self.think_mode:
            config["thinking_config"] = {
                "include_thoughts": True,
                "thinking_budget": self.thinking_budget if self.thinking_budget != -1 else None
            }
            # 注意：某些 SDK 版本可能只接受特定欄位
            # 如果 thinking_budget 是 -1 (動態)，有些 API 可能不傳該欄位，或者傳 null
            if self.thinking_budget == -1:
                config["thinking_config"].pop("thinking_budget")
        
        gen_config = types.GenerateContentConfig(**config)
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"[VisionHandler] API 呼叫嘗試 {attempt}/{self.max_retries}")
                
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=[prompt, image_part],
                    config=gen_config
                )
                
                if self.debug:
                    import pprint
                    logger.debug(f"[DEBUG] Raw Response Type: {type(response)}")
                    # logger.debug(f"[DEBUG] Raw Response: {response}") # Too verbose
                
                # 提取 Content 與 Thoughts
                full_text = ""
                thoughts = ""
                
                if response.candidates:
                    for i, candidate in enumerate(response.candidates):
                         for j, part in enumerate(candidate.content.parts):
                            is_thought = False
                            if hasattr(part, 'thought') and part.thought:
                                is_thought = True
                                if hasattr(part, 'text') and part.text:
                                    thoughts += part.text
                            
                            if not is_thought and hasattr(part, 'text') and part.text:
                                full_text += part.text
                
                if thoughts and self.debug:
                    logger.debug(f"[VisionHandler] Thoughts summarized: {len(thoughts)} chars")
                    # logger.debug(f"[VisionHandler] Thoughts: {thoughts[:500]}...")
                
                if full_text:
                    return full_text, thoughts
                else:
                    raise ValueError("Gemini 回應中找不到文字內容")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"[VisionHandler] API 呼叫失敗 (嘗試 {attempt}): {e}")
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
        
        raise last_error

    def _clean_json_response(self, content: str) -> str:
        """清理 JSON 格式"""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:].strip()
        elif content.startswith("```"):
            content = content[3:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        return content

    def image_to_markdown(self, image_array: np.ndarray) -> tuple:
        """通用介面"""
        return self.process_handwritten(image_array)

    def describe_image(self, image_array: np.ndarray, custom_prompt: str = None) -> tuple:
        """描述圖片"""
        start_time = time.time()
        prompt = custom_prompt or "請描述這張圖片的內容。"
        
        if not self._client:
            return "", {"error": "Gemini client 未初始化"}
        
        try:
            image_part = self._prepare_image_part(image_array)
            text, thoughts = self._call_with_retry(prompt, image_part)
            
            stats = {
                "processor": "Gemini-2.5",
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
    handler = VisionHandler({"vision_settings": {"debug": True, "think_mode": True}})
    result, stats = handler.image_to_markdown(image)
    print(f"Result: {result}\nStats: {stats}")
