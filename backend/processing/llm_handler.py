# processing/llm_handler.py
"""
LLM Handler - Unified module for text correction and data extraction.

This module combines the functionality of the former text_corrector.py and
data_extractor.py into a single cohesive module for LLM-based processing.
"""
import ollama
import json
import re


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
        print(f"[LLM] Initializing with model: {self.model_name}...")

        try:
            ollama.list()
            print("[INFO] Ollama service is running.")
        except Exception:
            print(
                "[WARN] Ollama service is not running. Please start Ollama manually and rerun the script."
            )
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
        print("\n[INFO] Calling LLM to correct OCR/semantic errors in text...")
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
            print("[INFO] Text correction successful.")
            return corrected_text
        except Exception as e:
            print(f"[ERROR] Text correction failed: {e}")
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
        print("\n[INFO] Calling LLM to extract structured data from text...")
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
            print("[INFO] LLM data extraction successful.")
            return parsed_data
        except Exception as e:
            print(f"[ERROR] LLM data extraction failed: {e}")
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
            print(
                f"[WARN] Data extraction produced an error, but returning combined structure."
            )

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
