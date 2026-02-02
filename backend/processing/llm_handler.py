# backend/processing/llm_handler.py
"""
LLM Handler - 統一的 LLM 文字處理模組

功能：
- OCR 文字校正
- 結構化資料擷取
- 收據資料清洗

所有 Prompts 從 prompts_config.py 載入，支援外部配置。
"""
import logging
import ollama
import json
import re
from typing import Optional

from .prompts_config import (
    CORRECTION_PROMPT,
    EXTRACTION_PROMPT,
    CLEANING_PROMPT
)

logger = logging.getLogger(__name__)


class LLMHandler:
    """
    LLM 文字處理器

    支援：
    - OCR 文字校正
    - 結構化資料擷取
    - 收據資料清洗
    """

    def __init__(self, config: dict):
        """
        初始化 LLM Handler

        Args:
            config: 配置字典，包含 'llm_settings' 設定
        """
        llm_settings = config.get("llm_settings", {})
        self.model_name = llm_settings.get("model_name", "qwen3:1.7b")
        self.think_mode = llm_settings.get("think_mode", True)
        self.num_predict = llm_settings.get("num_predict", 2048)

        logger.debug(f"初始化 LLM 模型: {self.model_name}, think={self.think_mode}")

        try:
            ollama.list()
            logger.debug("Ollama 服務運行中")
        except Exception:
            logger.error("Ollama 服務未啟動，請先啟動 Ollama 再重試")
            raise SystemError("Ollama Service Not Running")

        self.config = config

    def call_with_thinking(self, prompt: str) -> tuple[str, dict]:
        """
        使用思考模式調用 LLM

        Args:
            prompt: 提示詞

        Returns:
            tuple: (LLM 輸出, 統計資料)
        """
        import time

        logger.debug("[LLM] 使用思考模式調用...")

        start_time = time.time()
        first_token_time = None

        try:
            chunks = []
            thinking_chunks = []
            token_count = 0

            stream = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0, "num_predict": self.num_predict},
                stream=True,
                think=self.think_mode,
            )

            for chunk in stream:
                if first_token_time is None:
                    first_token_time = time.time()

                message = chunk.get("message", {})
                content = message.get("content", "")
                thinking = message.get("thinking", "")

                if content:
                    chunks.append(content)
                    token_count += 1
                if thinking:
                    thinking_chunks.append(thinking)

                if chunk.get("done", False):
                    break

            result = "".join(chunks)
            total_time = time.time() - start_time
            ttft = (first_token_time - start_time) if first_token_time else 0

            stats = {
                "processor": "LLM",
                "model": self.model_name,
                "total_time_s": round(total_time, 2),
                "ttft_s": round(ttft, 2),
                "generation_tokens": token_count,
                "generation_speed_tps": (
                    round(token_count / total_time, 2) if total_time > 0 else 0
                ),
            }

            logger.debug(
                f"[LLM] 完成: content={len(result)} 字元, thinking={len(''.join(thinking_chunks))} 字元"
            )
            return result, stats

        except Exception as e:
            logger.error(f"[LLM] 調用失敗: {e}", exc_info=True)
            return "", {}

    def _correct_text(self, pre_formatted_text: str) -> str:
        """
        使用 LLM 校正 OCR 文字錯誤

        處理：
        - 視覺相似字錯誤 (每報紙 → 海報紙)
        - 簡繁轉換 (圆头笔 → 圓頭筆)
        - 常見 OCR 錯誤

        Args:
            pre_formatted_text: OCR 辨識原文

        Returns:
            校正後的繁體中文文字
        """
        logger.info("="*50)
        logger.info("[LLM校正] 開始文字校正...")
        logger.info(f"[LLM校正] 輸入文字 ({len(pre_formatted_text)} 字元):\n{pre_formatted_text[:500]}{'...' if len(pre_formatted_text) > 500 else ''}")

        # 使用外部 prompt
        prompt = CORRECTION_PROMPT.format(ocr_text=pre_formatted_text)

        try:
            # 使用 streaming + think 模式
            chunks = []
            thinking_chunks = []
            
            stream = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
                stream=True,
                think=self.think_mode,
            )
            
            for chunk in stream:
                message = chunk.get("message", {})
                content = message.get("content", "")
                thinking = message.get("thinking", "")
                
                if content:
                    chunks.append(content)
                if thinking:
                    thinking_chunks.append(thinking)
                    
                if chunk.get("done", False):
                    break
            
            corrected_text = "".join(chunks)
            thinking_text = "".join(thinking_chunks)
            
            # 輸出思考過程到 log
            if thinking_text:
                logger.info(f"[LLM校正] 思考過程:\n{thinking_text[:1000]}{'...' if len(thinking_text) > 1000 else ''}")
            
            logger.info(f"[LLM校正] 輸出文字 ({len(corrected_text)} 字元):\n{corrected_text[:500]}{'...' if len(corrected_text) > 500 else ''}")
            return corrected_text
            
        except Exception as e:
            logger.error(f"文字校正失敗: {e}", exc_info=True)
            return pre_formatted_text

    def _extract_data(self, text: str) -> dict:
        """
        使用 LLM 從文字中擷取結構化資料

        Args:
            text: 校正後的發票/收據文字

        Returns:
            結構化字典：supplier, invoice_id, date, items, total_amount
        """
        logger.info("="*50)
        logger.info("[LLM擷取] 開始結構化資料擷取...")
        logger.info(f"[LLM擷取] 輸入校正文字 ({len(text)} 字元):\n{text[:500]}{'...' if len(text) > 500 else ''}")

        # 使用外部 prompt
        prompt = EXTRACTION_PROMPT.format(corrected_text=text)

        try:
            # 使用 streaming + think 模式
            chunks = []
            thinking_chunks = []
            
            stream = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.0},
                stream=True,
                think=self.think_mode,
            )
            
            for chunk in stream:
                message = chunk.get("message", {})
                content = message.get("content", "")
                thinking = message.get("thinking", "")
                
                if content:
                    chunks.append(content)
                if thinking:
                    thinking_chunks.append(thinking)
                    
                if chunk.get("done", False):
                    break
            
            json_string = "".join(chunks)
            thinking_text = "".join(thinking_chunks)
            
            # 輸出思考過程到 log
            if thinking_text:
                logger.info(f"[LLM擷取] 思考過程:\n{thinking_text[:1500]}{'...' if len(thinking_text) > 1500 else ''}")
            
            json_match = re.search(r"\{.*\}", json_string, re.DOTALL)
            if json_match:
                json_string = json_match.group(0)
            parsed_data = json.loads(json_string)
            
            logger.info(f"[LLM擷取] 輸出 JSON: {json.dumps(parsed_data, ensure_ascii=False, indent=2)[:800]}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"LLM 資料擷取失敗: {e}", exc_info=True)
            return {"error": str(e)}

    def structure_with_llm(self, pre_formatted_text: str) -> dict:
        """
        協調文字校正和資料擷取流程

        這是處理 OCR 文字的主要入口點。

        Args:
            pre_formatted_text: OCR 原始文字

        Returns:
            結構化資料字典
        """
        # 1. 校正文字
        corrected_text = self._correct_text(pre_formatted_text)

        # 2. 從校正後文字擷取結構化資料
        extracted = self._extract_data(corrected_text)

        if "error" in extracted:
            logger.warning("資料擷取產生錯誤，但仍返回結構")

        return extracted

    def regenerate_from_corrected_text(self, corrected_text: str) -> dict:
        """
        從人工校正後的文字重新擷取資料

        當使用者手動修正 OCR 文字後，只需重新擷取結構化資料。

        Args:
            corrected_text: 人工校正後的文字

        Returns:
            結構化資料字典
        """
        return self._extract_data(corrected_text)

    def clean_receipt(self, ocr_json: dict) -> Optional[dict]:
        """
        使用 LLM 清洗收據 OCR 結果

        整合自原 receipt_llm_cleaner.py

        Args:
            ocr_json: 啟發式分類器輸出的收據 JSON

        Returns:
            清洗後的 JSON，失敗則返回 None
        """
        header = ocr_json.get("header", {})
        items = ocr_json.get("items", [])
        summary = ocr_json.get("summary", {})
        stamp = ocr_json.get("stamp", {})

        prompt = CLEANING_PROMPT.format(
            buyer=header.get("buyer", ""),
            date=header.get("date", ""),
            items=", ".join([i.get("name", "") for i in items]),
            total_chinese=summary.get("total_chinese", ""),
            shop_name=stamp.get("shop_name", ""),
        )

        logger.debug("[LLM] 執行收據清洗...")

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": 1024, "temperature": 0.1},
            )

            content = response.get("message", {}).get("content", "")

            # 解析 JSON
            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # 嘗試直接找 JSON
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                return json.loads(content[start : end + 1])

            logger.warning("[LLM] 無法解析清洗結果")
            return None

        except Exception as e:
            logger.error(f"[LLM] 收據清洗失敗: {e}", exc_info=True)
            return None
