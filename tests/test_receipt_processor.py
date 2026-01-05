"""
Unit Tests for ReceiptProcessorV2

Tests the integrated receipt processing pipeline with mocked dependencies.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from backend.processing.receipt_processor import ReceiptProcessorV2, ReceiptType

class TestReceiptProcessorV2:
    """ReceiptProcessorV2 Integration Tests with Mocks"""

    @pytest.fixture
    def mock_processor(self):
        """
        Setup ReceiptProcessorV2 with all sub-handlers mocked.
        Returns the processor instance and a dictionary of mocks.
        """
        with patch('backend.processing.receipt_processor.RapidOCRHandler') as MockOCR, \
             patch('backend.processing.receipt_processor.KeywordClassifier') as MockClassifier, \
             patch('backend.processing.receipt_processor.QRHandler') as MockQR, \
             patch('backend.processing.receipt_processor.VisionHandler') as MockVision, \
             patch('backend.processing.receipt_processor.LLMHandler') as MockLLM, \
             patch('backend.processing.receipt_processor.PythonValidator') as MockValidator, \
             patch('backend.processing.receipt_processor.GemmaCorrector') as MockCorrector:
            
            # Create sub-handler instances
            ocr = MockOCR.return_value
            classifier = MockClassifier.return_value
            qr = MockQR.return_value
            vision = MockVision.return_value
            llm = MockLLM.return_value
            validator = MockValidator.return_value
            corrector = MockCorrector.return_value
            
            # Initialize processor
            config = {}
            processor = ReceiptProcessorV2(config)
            
            mocks = {
                'ocr': ocr,
                'classifier': classifier,
                'qr': qr,
                'vision': vision,
                'llm': llm,
                'validator': validator,
                'corrector': corrector
            }
            
            # Common defaults
            ocr.do_ocr.return_value = ([], {'total_time_s': 0.1})
            ocr.to_plain_text.return_value = ""
            validator.validate.return_value = MagicMock(is_valid=True, issues=[], confidence=1.0)
            
            yield processor, mocks

    def test_process_electronic_invoice(self, mock_processor):
        """Test processing flow for Electronic Invoice (QR code based)."""
        processor, mocks = mock_processor
        
        # Setup mocks
        ocr_text = "電子發票證明聯"
        mocks['ocr'].to_plain_text.return_value = ocr_text
        mocks['ocr'].do_ocr.return_value = ([{'text': ocr_text}], {'engine': 'rapidocr'})
        
        # QR detected and decoded
        qr_data = {
            "success": True, 
            "data": {
                "invoice_id": "AB12345678", 
                "total": 100, 
                "seller_id": "87654321",
                "invoice_date": "2024-01-01"
            }
        }
        mocks['qr'].detect_and_decode.return_value = qr_data
        
        # Classification
        classification = MagicMock()
        classification.receipt_type = ReceiptType.ELECTRONIC
        classification.confidence = 0.95
        mocks['classifier'].classify.return_value = classification
        
        # Execution
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)
        
        # Verification
        assert result['success'] is True
        assert result['invoice_type'] == "electronic"
        assert result['llm_result']['receipt_type'] == "電子發票"
        # Check that data came from QR
        assert result['llm_result']['header']['invoice_id'] == "AB12345678"
        assert result['llm_result']['header']['supplier'] == "87654321"

    def test_process_handwritten_receipt(self, mock_processor):
        """Test processing flow for Handwritten Receipt (VLM based)."""
        processor, mocks = mock_processor
        
        # Setup mocks
        ocr_text = "免用統一發票收據"
        mocks['ocr'].to_plain_text.return_value = ocr_text
        
        # No QR
        mocks['qr'].detect_and_decode.return_value = None
        
        # Classification
        classification = MagicMock()
        classification.receipt_type = ReceiptType.HANDWRITTEN
        classification.confidence = 0.9
        mocks['classifier'].classify.return_value = classification
        
        # VLM Response
        vlm_json_str = '{"header": {"supplier": "Test Shop"}, "items": [], "summary": {"total": 500}}'
        mocks['vision'].process_handwritten.return_value = (vlm_json_str, {'tokens_per_second': 10})
        
        # Execution
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)
        
        # Verification
        assert result['success'] is True
        assert result['invoice_type'] == "handwritten"
        assert result['llm_result']['receipt_type'] == "免用統一發票收據"
        assert result['llm_result']['header']['supplier'] == "Test Shop"
        # Check stats included
        assert any(stat.get('stage') == "vlm_extraction" for stat in result['llm_stats'])

    def test_process_other_receipt(self, mock_processor):
        """Test processing flow for Other Receipt (LLM based)."""
        processor, mocks = mock_processor
        
        # Setup mocks
        ocr_text = "計程車乘車證明"
        mocks['ocr'].to_plain_text.return_value = ocr_text
        
        # No QR
        mocks['qr'].detect_and_decode.return_value = None
        
        # Classification
        classification = MagicMock()
        classification.receipt_type = ReceiptType.OTHER
        classification.confidence = 0.8
        mocks['classifier'].classify.return_value = classification
        
        # LLM Response
        llm_json_str = '{"header": {"supplier": "Taxi"}, "summary": {"total": 200}}'
        mocks['llm'].call_with_thinking.return_value = (llm_json_str, {'tokens_per_second': 20})
        
        # Execution
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)
        
        # Verification
        assert result['success'] is True
        assert result['invoice_type'] == "other"
        assert result['llm_result']['receipt_type'] == "其他收據"
        assert result['llm_result']['header']['supplier'] == "Taxi"
        assert any(stat.get('stage') == "llm_extraction" for stat in result['llm_stats'])

    def test_process_invalid_extraction(self, mock_processor):
        """Test handling of failed extraction."""
        processor, mocks = mock_processor
        
        # Classification returns Handwritten
        classification = MagicMock()
        classification.receipt_type = ReceiptType.HANDWRITTEN
        classification.confidence = 0.9  # Set confidence to avoid TypeError
        mocks['classifier'].classify.return_value = classification
        
        # VLM returns empty/None
        mocks['vision'].process_handwritten.return_value = (None, {})
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)
        
        assert result['success'] is False
        assert "資料提取失敗" in result['error']

    def test_gemma_correction_triggered(self, mock_processor):
        """Test that Gemma correction is triggered when validation fails."""
        processor, mocks = mock_processor
        
        # Setup Handwritten flow
        classification = MagicMock()
        classification.receipt_type = ReceiptType.HANDWRITTEN
        classification.confidence = 0.9  # Set confidence
        mocks['classifier'].classify.return_value = classification
        
        mocks['vision'].process_handwritten.return_value = ('{"summary": {"total": 100}}', {})
        
        # Validation Fails
        failed_validation = MagicMock(is_valid=False, issues=["Total mismatch"], confidence=0.5)
        passed_validation = MagicMock(is_valid=True, issues=[], confidence=0.9)
        # First call fails, second call (after correction) passes
        mocks['validator'].validate.side_effect = [failed_validation, passed_validation]
        
        # Gemma Correction Success
        mocks['corrector'].correct.return_value = {
            "success": True,
            "data": {"summary": {"total": 100}},
            "correction": {"source": "gemma", "description": "Fixed total"},
            "correction_time": 1.5
        }
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)
        
        assert result['success'] is True
        assert result['was_corrected'] is True
        assert result['llm_result']['audit']['corrections'][0]['description'] == "Fixed total"
        mocks['corrector'].correct.assert_called_once()
