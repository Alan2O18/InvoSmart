# processing/data_extractor.py
import ollama
import json
import re

class DataExtractor:
    def __init__(self, model_name: str = 'qwen3:1.7b'):
        self.model_name = model_name

    def extract_data(self, text: str) -> dict:
        """
        Receives text and calls LLM for structured extraction.
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
            json_match = re.search(r"{{.*}}", json_string, re.DOTALL)
            if json_match:
                json_string = json_match.group(0)
            parsed_data = json.loads(json_string)
            print("[INFO] LLM data extraction successful.")
            return parsed_data
        except Exception as e:
            print(f"[ERROR] LLM data extraction failed: {e}")
            return {"error": str(e)}
