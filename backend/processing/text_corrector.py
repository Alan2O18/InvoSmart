# processing/text_corrector.py
import ollama

class TextCorrector:
    def __init__(self, model_name: str = 'qwen3:1.7b'):
        self.model_name = model_name

    def correct_text(self, pre_formatted_text: str) -> str:
        """
        Corrects OCR and semantic errors in the input text using an LLM.
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
