
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json
import logging

# Setup path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock dependencies before importing backend modules that might need them
sys.modules['cv2'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['paddleocr'] = MagicMock()
sys.modules['onnxruntime'] = MagicMock()
sys.modules['ollama'] = MagicMock()
sys.modules['PIL'] = MagicMock()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Verification")

class TestPipelineFixes(unittest.TestCase):
    
    def setUp(self):
        # Import after mocking
        global ReceiptProcessorV2, ReceiptType
        from backend.processing.receipt_processor import ReceiptProcessorV2
        from backend.processing.keyword_classifier import ReceiptType
        
        self.config = {
            "ocr_settings": {},
            "llm_settings": {"model_name": "qwen3:1.7b"},
            "vision_settings": {"model_name": "qwen3-vl:2b"},
            "gemma_settings": {"model_name": "gemma3:4b"}
        }
        self.processor = ReceiptProcessorV2(self.config)
        self.ReceiptType = ReceiptType

    def test_success_result_format(self):
        """Phase 3: Verify success result matches json_schema.md"""
        logger.info("Testing Success Result Format (Phase 3)...")
        
        # Mock extracted data
        data = {
            "header": {"supplier": "Test Shop"},
            "items": [],
            "summary": {"total": 100}
        }
        
        # Call _create_success_result
        result = self.processor._create_success_result(
            receipt_type=self.ReceiptType.ELECTRONIC,
            data=data,
            confidence=0.9,
            issues=[],
            ocr_raw=["line1"],
            ocr_stats={"time": 1.0},
            llm_stats=[{"processor": "test"}]
        )
        
        # Verify Structure
        self.assertIn("ocr_result", result)
        self.assertIn("llm_result", result)
        self.assertIn("ocr_stats", result)
        self.assertIn("llm_stats", result)
        
        # Verify OCR Result Format (Only text and type)
        self.assertIn("text", result["ocr_result"])
        self.assertIn("type", result["ocr_result"])
        self.assertEqual(result["ocr_result"]["type"], "電子發票")
        # Ensure block_count etc are NOT present (bloat removal)
        self.assertNotIn("blocks", result["ocr_result"])
        
        # Verify LLM Result Format (Flat structure with receipt_type)
        self.assertEqual(result["llm_result"]["receipt_type"], "電子發票")
        self.assertIn("header", result["llm_result"])
        self.assertIn("audit", result["llm_result"])
        
        # Verify Invoice Type (Chinese)
        self.assertEqual(result["invoice_type"], "電子發票")
        
        logger.info("✓ Success Result Format Verified")

    def test_error_result_format(self):
        """Phase 3: Verify error result matches json_schema.md"""
        logger.info("Testing Error Result Format (Phase 3)...")
        
        result = self.processor._create_error_result(
            receipt_type=self.ReceiptType.HANDWRITTEN,
            error="Test Error",
            ocr_raw=["raw"],
            ocr_stats={}
        )
        
        # Verify OCR Result Format
        self.assertEqual(result["ocr_result"]["type"], "免用統一發票收據")
        self.assertNotIn("blocks", result["ocr_result"])
        self.assertEqual(result["invoice_type"], "免用統一發票收據")
        
        logger.info("✓ Error Result Format Verified")

    @patch('backend.processing.receipt_processor.ReceiptProcessorV2._process_other')
    def test_process_stats_propagation(self, mock_process_other):
        """Phase 5: Verify stats propagation in process method"""
        logger.info("Testing Stats Propagation (Phase 5)...")
        
        # Setup mocks
        self.processor.ocr_handler.do_ocr = MagicMock(return_value=(["text"], {"ocr_time": 0.5}))
        self.processor.ocr_handler.to_plain_text = MagicMock(return_value="text")
        self.processor.qr_handler.detect_and_decode = MagicMock(return_value=None)
        
        # force OTHER type classification
        mock_cls = MagicMock()
        mock_cls.receipt_type = self.ReceiptType.OTHER
        mock_cls.confidence = 0.8
        self.processor.classifier.classify = MagicMock(return_value=mock_cls)
        
        # Mock _process_other return value (data, stats)
        mock_process_other.return_value = ({}, {"processor": "test_llm", "time": 0.2})
        
        self.processor.validator.validate = MagicMock(return_value=MagicMock(is_valid=True, issues=[]))
        
        # Run process
        result = self.processor.process("fake_image_array")
        
        # Verify stats presence
        llm_stats = result["llm_stats"]
        self.assertTrue(any(s.get("processor") == "test_llm" for s in llm_stats))
        self.assertTrue(any(s.get("ocr_time") == 0.5 for s in [result["ocr_stats"]]))
        
        logger.info("✓ Stats Propagation Verified")

if __name__ == '__main__':
    unittest.main()
