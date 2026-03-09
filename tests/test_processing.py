"""
Unit Tests for Processing Modules

Tests OCR handler, LLM handler, text corrector, and data extractor.
"""
import pytest
from unittest.mock import patch
import json


# ============================================================================
# Mock Helpers for Ollama Streaming Responses
# ============================================================================

class MockMessage:
    """模擬 Ollama message 物件"""
    def __init__(self, content: str = "", thinking: str = ""):
        self.content = content
        self.thinking = thinking


class MockChunk:
    """模擬 Ollama streaming chunk 物件"""
    def __init__(self, content: str = "", thinking: str = "", done: bool = False):
        self.message = MockMessage(content, thinking)
        self.done = done


def create_stream_mock(content: str, thinking: str = "") -> list:
    """建立模擬的 streaming 響應列表"""
    return [
        MockChunk(content=content, thinking=thinking, done=False),
        MockChunk(content="", thinking="", done=True)
    ]


# ============================================================================
# OCRHandler Tests
# ============================================================================

# ============================================================================
# OCRHandler Tests (Removed - module replaced by RapidOCRHandler)
# ============================================================================
# TestOCRHandler and its methods were removed because backend.processing.ocr_handler.py
# was deleted. Please use TestRapidOCRHandler if needed in the future.

# ============================================================================
# LLMHandler._correct_text Tests (was TextCorrector)
# ============================================================================

class TestCorrectTextMethod:
    """Tests for LLMHandler._correct_text method."""

    @patch('backend.processing.llm_handler.ollama')
    def test_correct_text_success(self, mock_ollama):
        """Test successful text correction."""
        from backend.processing.llm_handler import LLMHandler
        
        # Mock ollama for init
        mock_ollama.list.return_value = []
        
        # Mock streaming response for _correct_text
        mock_ollama.chat.return_value = create_stream_mock("海報紙 圓頭筆 電話")
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        result = handler._correct_text("每報紙 圆头笔 电话")
        
        assert result == "海報紙 圓頭筆 電話"
        mock_ollama.chat.assert_called_once()

    @patch('backend.processing.llm_handler.ollama')
    def test_correct_text_failure_returns_original(self, mock_ollama):
        """Test that failure returns original text."""
        from backend.processing.llm_handler import LLMHandler
        
        # Mock ollama for init
        mock_ollama.list.return_value = []
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Mock ollama to raise exception after init
        mock_ollama.chat.side_effect = Exception("LLM Error")
        
        original_text = "測試文字"
        result = handler._correct_text(original_text)
        
        assert result == original_text


# ============================================================================
# LLMHandler._extract_data Tests (was DataExtractor)
# ============================================================================

class TestExtractDataMethod:
    """Tests for LLMHandler._extract_data method."""

    @patch('backend.processing.llm_handler.ollama')
    def test_extract_data_success(self, mock_ollama):
        """Test successful data extraction."""
        from backend.processing.llm_handler import LLMHandler
        
        # Mock ollama for init
        mock_ollama.list.return_value = []
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Mock streaming response with valid JSON
        mock_response = {
            "supplier": "測試供應商",
            "invoice_id": "AB12345678",
            "date": "2025-12-09",
            "items": [
                {"description": "商品A", "quantity": 2, "price": 100.5}
            ],
            "total_amount": 201.0
        }
        mock_ollama.chat.return_value = create_stream_mock(json.dumps(mock_response))
        
        result = handler._extract_data("測試發票文字")
        
        assert result["supplier"] == "測試供應商"
        assert result["invoice_id"] == "AB12345678"
        assert len(result["items"]) == 1
        assert result["items"][0]["description"] == "商品A"

    @patch('backend.processing.llm_handler.ollama')
    def test_extract_data_failure(self, mock_ollama):
        """Test data extraction failure handling."""
        from backend.processing.llm_handler import LLMHandler
        
        # Mock ollama for init
        mock_ollama.list.return_value = []
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Mock ollama to raise exception
        mock_ollama.chat.side_effect = Exception("LLM Error")
        
        result = handler._extract_data("測試發票文字")
        
        assert "error" in result


# ============================================================================
# LLMHandler Tests
# ============================================================================

class TestLLMHandlerAdvanced:
    """Additional tests for LLMHandler to improve coverage."""
    
    @patch('backend.processing.llm_handler.ollama')
    def test_call_with_thinking_no_content(self, mock_ollama):
        """Test call_with_thinking when response has no content."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Mock streaming response with empty content
        mock_ollama.chat.return_value = [
            MockChunk(content="", thinking="", done=True)
        ]
        
        result, stats = handler.call_with_thinking("test prompt")
        
        assert result == ""
        assert "total_time_s" in stats
    
    @patch('backend.processing.llm_handler.ollama')
    def test_call_with_thinking_exception(self, mock_ollama):
        """Test call_with_thinking exception handling."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        mock_ollama.chat.side_effect = Exception("Network error")
        
        result, stats = handler.call_with_thinking("test prompt")
        
        assert result == ""
        assert stats == {}
    
    @patch('backend.processing.llm_handler.ollama')
    def test_structure_with_llm_empty_text(self, mock_ollama):
        """Test structure_with_llm with empty input."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Mock to return empty string which will fail JSON parse
        mock_ollama.chat.return_value = create_stream_mock("")
        
        result = handler.structure_with_llm("")
        
        # Should return error dict when JSON parse fails
        assert "error" in result
    
    @patch('backend.processing.llm_handler.ollama')
    def test_structure_with_llm_json_parse_error(self, mock_ollama):
        """Test structure_with_llm with invalid JSON response."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Return invalid JSON
        mock_ollama.chat.return_value = create_stream_mock("not a json {invalid")
        
        result = handler.structure_with_llm("test text")
        
        assert "error" in result
    
    @patch('backend.processing.llm_handler.ollama')
    def test_regenerate_from_corrected_text(self, mock_ollama):
        """Test regenerate_from_corrected_text."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        mock_response = {"supplier": "corrected_supplier", "total_amount": 100}
        mock_ollama.chat.return_value = create_stream_mock(json.dumps(mock_response))
        
        result = handler.regenerate_from_corrected_text("corrected text")
        
        assert result["supplier"] == "corrected_supplier"
    
    @patch('backend.processing.llm_handler.ollama')
    def test_clean_receipt_success(self, mock_ollama):
        """Test clean_receipt with valid OCR JSON."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        ocr_json = {
            "text": "supplier: test shop",
            "lines": [{"text": "item 1", "confidence": 0.9}]
        }
        
        expected_response = {"supplier": "test shop", "items": []}
        # clean_receipt uses non-streaming ollama.chat
        mock_ollama.chat.return_value = {
            "message": {"content": json.dumps(expected_response)}
        }
        
        result = handler.clean_receipt(ocr_json)
        
        assert result is not None
        assert "supplier" in result
    
    @patch('backend.processing.llm_handler.ollama')
    def test_clean_receipt_no_text(self, mock_ollama):
        """Test clean_receipt with empty OCR text."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.return_value = []
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        result = handler.clean_receipt({})
        
        assert result is None
    
    @patch('backend.processing.llm_handler.ollama')
    def test_init_without_ollama(self, mock_ollama):
        """Test LLMHandler init when ollama is not available."""
        from backend.processing.llm_handler import LLMHandler
        
        mock_ollama.list.side_effect = Exception("Ollama not available")
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        # Should raise SystemError when Ollama not running
        with pytest.raises(SystemError, match="Ollama Service Not Running"):
            handler = LLMHandler(config)

# ============================================================================
# LLMHandler Tests (Existing)
# ============================================================================

class TestLLMHandler:
    """Tests for LLM handler (unified module after merging text_corrector and data_extractor)."""

    @patch('backend.processing.llm_handler.ollama')
    def test_structure_with_llm(self, mock_ollama):
        """Test complete LLM processing workflow."""
        from backend.processing.llm_handler import LLMHandler
        
        # Mock ollama for init
        mock_ollama.list.return_value = []
        
        # Use realistic invoice text and response
        corrected_text = """全家便利超商
發票號碼: AB12345678
日期: 2025-12-09
商品明細:
海報紙 x2 100元
圓頭筆 x3 50元
合計: 200元"""
        
        # 新格式使用 header/items/summary
        extracted_data = {
            "receipt_type": "電子發票",
            "header": {
                "supplier": "全家便利超商",
                "invoice_id": "AB12345678",
                "date": "2025-12-09"
            },
            "items": [
                {"name": "海報紙", "qty": 2, "price": 100.0, "total": 200.0},
                {"name": "圓頭筆", "qty": 3, "price": 50.0, "total": 150.0}
            ],
            "summary": {
                "total": 200.0
            }
        }
        
        # Setup side_effect for sequential calls: _correct_text then _extract_data
        mock_ollama.chat.side_effect = [
            create_stream_mock(corrected_text),  # _correct_text
            create_stream_mock(json.dumps(extracted_data))  # _extract_data
        ]
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        # Input text with some OCR errors
        ocr_input = """全家便利趙滴
發票竈码: AB12345678
日期: 2025-12-09
商品明细:
海幸氏 x2 100元
圆头笔 x3 50元
合计: 200元"""
        
        result = handler.structure_with_llm(ocr_input)
        
        # 新格式驗證：直接返回扁平結構
        assert "header" in result
        assert "items" in result
        assert result["header"]["supplier"] == "全家便利超商"
        assert len(result["items"]) == 2

    @patch('backend.processing.llm_handler.ollama')
    def test_regenerate_from_corrected_text(self, mock_ollama):
        """Test regenerating from manually corrected text."""
        from backend.processing.llm_handler import LLMHandler
        
        # Mock init
        mock_ollama.list.return_value = []
        
        # Realistic manually corrected text
        manual_text = """全家便利超商
發票號碼: AB12345678
日期: 2025-12-09
海報紙 x2 100元
圓頭筆 x3 50元
合計: 200元"""
        
        extracted_data = {
            "supplier": "全家便利超商",
            "invoice_id": "AB12345678",
            "date": "2025-12-09",
            "items": [
                {"description": "海報紙", "quantity": 2, "price": 100.0},
                {"description": "圓頭筆", "quantity": 3, "price": 50.0}
            ],
            "total_amount": 200.0
        }
        
        # Set streaming return value for _extract_data call
        mock_ollama.chat.return_value = create_stream_mock(json.dumps(extracted_data))
        
        config = {"llm_settings": {"model_name": "qwen3:1.7b"}}
        handler = LLMHandler(config)
        
        result = handler.regenerate_from_corrected_text(manual_text)
        
        assert result["supplier"] == "全家便利超商"
        assert result["invoice_id"] == "AB12345678"
        assert len(result["items"]) == 2
        assert result["total_amount"] == 200.0


# ============================================================================
# ReceiptSplitter Tests
# ============================================================================

class TestReceiptSplitter:
    """Tests for receipt splitter (V10)."""

    def test_order_points(self):
        """Test point ordering for perspective transform."""
        from backend.processing.perspective_transform import order_points
        import numpy as np
        
        # Test points in random order
        pts = np.array([
            [100, 200],  # Bottom-left
            [400, 200],  # Bottom-right
            [100, 50],   # Top-left
            [400, 50]    # Top-right
        ], dtype=np.float32)
        
        ordered = order_points(pts)
        
        # Check order: TL, TR, BR, BL
        assert ordered[0][1] < ordered[2][1]  # Top y < Bottom y
        assert ordered[0][0] < ordered[1][0]  # Left x < Right x

    def test_validate_aspect_ratio(self):
        """Test aspect ratio validation."""
        from backend.processing.contour_validator import ContourValidator
        
        validator = ContourValidator(aspect_ratio_range=(0.5, 2.0))
        
        # Valid aspect ratio (1:1) -> min/max = 1.0
        assert validator.validate_aspect_ratio((100, 100)) is True
        
        # Valid aspect ratio (2:1) -> min/max = 0.5
        assert validator.validate_aspect_ratio((200, 100)) is True
        
        # Invalid aspect ratio (3:1) -> min/max = 0.333 < 0.5
        assert validator.validate_aspect_ratio((300, 100)) is False

    def test_splitter_empty_image(self):
        """Test that split() handles None input."""
        from backend.processing.receipt_splitter import ReceiptSplitter
        
        config = {}
        splitter = ReceiptSplitter(config)
        
        assert splitter.split(None) == []

