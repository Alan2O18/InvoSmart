"""
Unit Tests for Processing Modules

Tests OCR handler, LLM handler, text corrector, and data extractor.
"""
import pytest
from unittest.mock import MagicMock, patch
import json


# ============================================================================
# OCRHandler Tests
# ============================================================================

class TestOCRHandler:
    """Tests for OCR processing."""

    @patch('backend.processing.ocr_handler.PaddleOCR')
    def test_reconstruct_layout_empty(self, mock_paddle):
        """Test layout reconstruction with empty data."""
        from backend.processing.ocr_handler import OCRHandler
        
        config = {"ocr_settings": {"language": "chinese_cht", "use_angle_cls": True}}
        handler = OCRHandler(config)
        
        result = handler.reconstruct_layout([])
        assert result == ""

    @patch('backend.processing.ocr_handler.PaddleOCR')
    def test_reconstruct_layout_single_line(self, mock_paddle):
        """Test layout reconstruction with items on same line."""
        from backend.processing.ocr_handler import OCRHandler
        
        config = {"ocr_settings": {"language": "chinese_cht", "use_angle_cls": True}}
        handler = OCRHandler(config)
        
        # Items with similar y-coordinates (same line)
        ocr_data = [
            {"text": "商品名稱", "box": [10, 100, 80, 120]},
            {"text": "數量", "box": [90, 102, 130, 118]},
            {"text": "價格", "box": [140, 101, 180, 119]},
        ]
        
        result = handler.reconstruct_layout(ocr_data)
        assert "商品名稱 數量 價格" in result

    @patch('backend.processing.ocr_handler.PaddleOCR')
    def test_reconstruct_layout_multiple_lines(self, mock_paddle):
        """Test layout reconstruction with multiple lines."""
        from backend.processing.ocr_handler import OCRHandler
        
        config = {"ocr_settings": {"language": "chinese_cht", "use_angle_cls": True}}
        handler = OCRHandler(config)
        
        # Items on different lines
        ocr_data = [
            {"text": "第一行", "box": [10, 100, 80, 120]},
            {"text": "第二行", "box": [10, 150, 80, 170]},
            {"text": "第三行", "box": [10, 200, 80, 220]},
        ]
        
        result = handler.reconstruct_layout(ocr_data)
        lines = result.split("\n")
        assert len(lines) == 3
        assert "第一行" in lines[0]
        assert "第二行" in lines[1]
        assert "第三行" in lines[2]

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
        
        # Mock ollama response for _correct_text
        mock_ollama.chat.return_value = {
            "message": {"content": "海報紙 圓頭筆 電話"}
        }
        
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
        
        # Mock ollama response with valid JSON
        mock_response = {
            "supplier": "測試供應商",
            "invoice_id": "AB12345678",
            "date": "2025-12-09",
            "items": [
                {"description": "商品A", "quantity": 2, "price": 100.5}
            ],
            "total_amount": 201.0
        }
        mock_ollama.chat.return_value = {
            "message": {"content": json.dumps(mock_response)}
        }
        
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
        
        # Setup side_effect for sequential calls: _correct_text then _extract_data
        mock_ollama.chat.side_effect = [
            {"message": {"content": corrected_text}},  # _correct_text
            {"message": {"content": json.dumps(extracted_data)}}  # _extract_data
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
        
        assert "corrected_full_text" in result
        assert "structured_data" in result
        assert result["corrected_full_text"] == corrected_text
        assert result["structured_data"]["supplier"] == "全家便利超商"
        assert len(result["structured_data"]["items"]) == 2

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
        
        # Set return value for _extract_data call
        mock_ollama.chat.return_value = {
            "message": {"content": json.dumps(extracted_data)}
        }
        
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
    """Tests for receipt splitter."""

    def test_order_points(self):
        """Test point ordering for perspective transform."""
        from backend.processing.receipt_splitter import ReceiptSplitter
        import numpy as np
        
        config = {
            "CANNY_THRESHOLD_1": 50,
            "CANNY_THRESHOLD_2": 150,
            "MIN_AREA": 50000,
            "ANGLE_TOLERANCE": 15,
            "ASPECT_RATIO_RANGE": (0.5, 2.0),
            "PADDING": 10,
            "MORPH_KERNEL_SIZE": (5, 5)
        }
        
        splitter = ReceiptSplitter(config)
        
        # Test points in random order
        pts = np.array([
            [100, 200],  # Bottom-left
            [400, 200],  # Bottom-right
            [100, 50],   # Top-left
            [400, 50]    # Top-right
        ], dtype=np.float32)
        
        ordered = splitter._order_points(pts)
        
        # Check order: TL, TR, BR, BL
        assert ordered[0][1] < ordered[2][1]  # Top y < Bottom y
        assert ordered[0][0] < ordered[1][0]  # Left x < Right x

    def test_validate_angles(self):
        """Test angle validation for rectangles."""
        from backend.processing.receipt_splitter import ReceiptSplitter
        import numpy as np
        
        config = {
            "CANNY_THRESHOLD_1": 50,
            "CANNY_THRESHOLD_2": 150,
            "MIN_AREA": 50000,
            "ANGLE_TOLERANCE": 15,
            "ASPECT_RATIO_RANGE": (0.5, 2.0),
            "PADDING": 10,
            "MORPH_KERNEL_SIZE": (5, 5)
        }
        
        splitter = ReceiptSplitter(config)
        
        # Perfect rectangle
        rect = np.array([
            [0, 0],
            [100, 0],
            [100, 50],
            [0, 50]
        ], dtype=np.float32)
        
        assert splitter._validate_angles(rect) is True

    def test_validate_aspect_ratio(self):
        """Test aspect ratio validation."""
        from backend.processing.receipt_splitter import ReceiptSplitter
        
        config = {
            "CANNY_THRESHOLD_1": 50,
            "CANNY_THRESHOLD_2": 150,
            "MIN_AREA": 50000,
            "ANGLE_TOLERANCE": 15,
            "ASPECT_RATIO_RANGE": (0.5, 2.0),
            "PADDING": 10,
            "MORPH_KERNEL_SIZE": (5, 5)
        }
        
        splitter = ReceiptSplitter(config)
        
        # Valid aspect ratio (1:1)
        assert splitter._validate_aspect_ratio((100, 100)) is True
        
        # Valid aspect ratio (2:1)
        assert splitter._validate_aspect_ratio((200, 100)) is True
        
        # Invalid aspect ratio (too wide)
        assert splitter._validate_aspect_ratio((300, 100)) is False
