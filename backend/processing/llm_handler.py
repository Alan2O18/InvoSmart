# processing/llm_handler.py
import ollama
from .text_corrector import TextCorrector
from .data_extractor import DataExtractor


class LLMHandler:
    def __init__(self, config: dict):
        model_name = config["llm_settings"].get("model_name", "qwen3:1.7b")
        print(f"[LLM] Initializing with model: {model_name}...")

        try:
            ollama.list()
            print("[INFO] Ollama service is running.")
        except Exception:
            print(
                "[WARN] Ollama service is not running. Please start Ollama manually and rerun the script."
            )
            raise SystemError("Ollama Service Not Running")

        self.text_corrector = TextCorrector(model_name)
        self.data_extractor = DataExtractor(model_name)
        self.config = config

    def structure_with_llm(self, pre_formatted_text: str) -> dict:
        """
        Coordinates the text correction and data extraction process.
        """
        # 1. Correct the text
        corrected_text = self.text_corrector.correct_text(pre_formatted_text)

        # 2. Extract structured data from the corrected text
        structured_data = self.data_extractor.extract_data(corrected_text)

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
        Receives human-corrected text and performs only data extraction.
        """
        return self.data_extractor.extract_data(corrected_text)
