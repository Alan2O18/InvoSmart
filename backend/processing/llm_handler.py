# processing/llm_handler.py
"""
LLM Handler - Unified module for text correction and data extraction.

This module combines the functionality of the former text_corrector.py and
data_extractor.py into a single cohesive module for LLM-based processing.
"""
import logging
import ollama
import json
import re

logger = logging.getLogger(__name__)


class LLMHandler:
    """
    Handles all LLM-based text processing including:
    - OCR text correction
    - Structured data extraction from invoices
    """

    def __init__(self, config: dict):
        """
        Initialize the LLM handler.
        
        Args:
            config: Configuration dictionary with 'llm_settings' key containing model settings.
        """
        self.model_name = config["llm_settings"].get("model_name", "qwen3:1.7b")
        logger.debug(f"初始化 LLM 模型: {self.model_name}")

        try:
            ollama.list()
            logger.debug("Ollama 服務運行中")
        except Exception:
            logger.error("Ollama 服務未啟動，請先啟動 Ollama 再重試")
            raise SystemError("Ollama Service Not Running")

        self.config = config

    def _correct_text(self, pre_formatted_text: str) -> str:
        """
        Corrects OCR and semantic errors in the input text using an LLM.
        
        This method handles:
        - Visual OCR errors (e.g., 每報紙 → 海報紙)
        - Simplified to Traditional Chinese conversion
        - Common OCR mistakes
        
        Args:
            pre_formatted_text: Raw text from OCR that may contain errors.
            
        Returns:
            Corrected text in Traditional Chinese.
        """
        logger.debug("呼叫 LLM 進行 OCR/語意錯誤校正...")
        prompt = f"""
        [INST]
        You are a meticulous data correction robot. Your input is pre-formatted text from a Taiwanese e-invoice, which may contain OCR recognition errors.

        **Primary Directive: ALL text in your output MUST be in Traditional Chinese (繁體中文). This is a non-negotiable rule.**

        **Your Task:**
        1.  **Semantic & OCR Error Correction**: Analyze the entire text for correctness. Your main goal is to fix OCR errors that arise from visual similarity or are contextually nonsensical.
            - **Example 1 (Visual Error)**: Correct `每報紙` to `海報紙`.
            - **Example 2 (Simplified Chinese)**: Convert `圆头笔` to `圓頭筆`.
            - **Example 3 (Common OCR Mistakes)**: Correct `电话` to `電話`.
        2.  **Output**: Return ONLY the full, corrected invoice text as a single block of plain text. Do NOT include any other explanations, formatting, or surrounding text like "Here is the corrected text:".

        <pre-formatted_invoice_text>
        {pre_formatted_text}
        </pre-formatted_invoice_text>

        Begin.
        [/INST]
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
            )
            corrected_text = response["message"]["content"]
            logger.debug("文字校正成功")
            return corrected_text
        except Exception as e:
            logger.error(f"文字校正失敗: {e}", exc_info=True)
            # On failure, return the original text to allow data extraction to proceed
            return pre_formatted_text

    def _extract_data(self, text: str) -> dict:
        """
        Extracts structured data from invoice text using an LLM.
        
        Args:
            text: Corrected invoice text to extract data from.
            
        Returns:
            Dictionary containing extracted invoice data:
            - supplier: Supplier name
            - invoice_id: Invoice identifier
            - date: Invoice date (YYYY-MM-DD)
            - items: List of items with description, quantity, price
            - total_amount: Total invoice amount
        """
        logger.debug("呼叫 LLM 進行結構化資料擷取...")
        prompt = f"""
        [INST]
        You are a data extraction robot.
        Your input is a clean, corrected text from a Taiwanese e-invoice.
        Your ONLY task is to extract the specified fields and return them in a single, valid JSON object.
        Ensure all text in the output is in Traditional Chinese.

        <invoice_text>
        {text}
        </invoice_text>

        <json_output_format>
        {{
            "supplier": "supplier_name",
            "invoice_id": "invoice_id",
            "date": "YYYY-MM-DD",
            "items": [
                {{"description": "product_name", "quantity": quantity, "price": price}}
            ],
            "total_amount": amount
        }}
        </json_output_format>
        [/INST]
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0.0},
            )
            json_string = response["message"]["content"]
            json_match = re.search(r"\{.*\}", json_string, re.DOTALL)
            if json_match:
                json_string = json_match.group(0)
            parsed_data = json.loads(json_string)
            logger.debug("LLM 資料擷取成功")
            return parsed_data
        except Exception as e:
            logger.error(f"LLM 資料擷取失敗: {e}", exc_info=True)
            return {"error": str(e)}

    def structure_with_llm(self, pre_formatted_text: str) -> dict:
        """
        Coordinates the text correction and data extraction process.
        
        This is the main entry point for processing OCR text through the LLM pipeline.
        
        Args:
            pre_formatted_text: Raw OCR text to process.
            
        Returns:
            Dictionary containing:
            - corrected_full_text: The corrected text
            - structured_data: Extracted structured invoice data
        """
        # 1. Correct the text
        corrected_text = self._correct_text(pre_formatted_text)

        # 2. Extract structured data from the corrected text
        structured_data = self._extract_data(corrected_text)

        # 3. Combine the results into the desired final format
        final_output = {
            "corrected_full_text": corrected_text,
            "structured_data": structured_data,
        }

        if "error" in structured_data:
            logger.warning("資料擷取產生錯誤，但仍返回合併結構")

        return final_output

    def regenerate_from_corrected_text(self, corrected_text: str) -> dict:
        """
        Performs data extraction on human-corrected text.
        
        Use this method when a user has manually corrected the OCR text
        and you only need to re-extract the structured data.
        
        Args:
            corrected_text: Human-corrected text to extract data from.
            
        Returns:
            Dictionary containing extracted invoice data.
        """
        return self._extract_data(corrected_text)
