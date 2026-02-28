"""
Unit Tests for RapidOCRHandler

Tests OCR processing logic, result formatting, and statistics using mocks.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from backend.processing.rapidocr_handler import RapidOCRHandler

class TestRapidOCRHandler:
    """RapidOCRHandler Tests with Mocks"""

    @pytest.fixture
    def mock_rapid_ocr(self):
        """Mock the underlying RapidOCR class."""
        with patch('backend.processing.rapidocr_handler.RapidOCR') as MockRapidOCR:
            instance = MockRapidOCR.return_value
            # Default OCR return value from rapidocr_onnxruntime: (result, elapse_list)
            # result is a list of [box, text, confidence]
            # elapse_list is usually ignored in the handler logic
            instance.return_value = (
                [
                    [[[0,0], [10,0], [10,10], [0,10]], "text1", 0.99],
                    [[[0,20], [10,20], [10,30], [0,30]], "text2", 0.88]
                ], 
                None
            )
            yield instance

    def setup_method(self):
        self.handler = RapidOCRHandler({})

    def test_do_ocr_returns_structured_result(self, mock_rapid_ocr):
        """Test do_ocr returns correct structured list."""
        # Setup real image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        results, stats = self.handler.do_ocr(img)
        
        assert len(results) == 2
        assert results[0]["text"] == "text1"
        assert results[0]["confidence"] == 0.99
        assert results[0]["box"] == [0, 0, 10, 10]
        
        assert stats["engine"] == "rapidocr"
        assert stats["text_blocks_count"] == 2
        assert "total_time_s" in stats

    def test_do_ocr_empty_result(self, mock_rapid_ocr):
        """Test handling of empty OCR result."""
        mock_rapid_ocr.return_value = (None, None)
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        results, stats = self.handler.do_ocr(img)
        
        assert results == []
        assert stats.get("text_blocks_count") == 0

    def test_to_plain_text_line_ordering(self):
        """Test converting results to plain text with basic sorting logic if applicable."""
        # The handler might just join them in order.
        # Let's verify input order is preserved or sorted.
        # Assuming input is already sorted or just joined.
        results = [
            {"text": "Line1", "box": [0, 0, 100, 20]},
            {"text": "Line2", "box": [0, 50, 100, 70]}
        ]
        text = self.handler.to_plain_text(results)
        assert "Line1" in text
        assert "Line2" in text
        assert text == "Line1\nLine2"

    def test_get_high_confidence_text(self):
        """Test filtering by confidence."""
        results = [
            {"text": "Good", "confidence": 0.9},
            {"text": "Bad", "confidence": 0.4}
        ]
        # Assuming default threshold is 0.5 or similar, let's look at implementation default.
        # Or pass threshold if method allows. 
        # Checking implementation: get_high_confidence_text(results, threshold=0.5)
        
        filtered = self.handler.get_high_confidence_text(results, threshold=0.6)
        # Returns list of dicts, not text
        assert len(filtered) == 1
        assert filtered[0]["text"] == "Good"

    def test_extract_numbers(self):
        """Test extracting numbers from text."""
        # The method expects structured results (list of dicts)
        ocr_result = [
             {"text": "Order 123"}, 
             {"text": "Price $500"}, 
             {"text": "Tax 5.5%"}
        ]
        nums = self.handler.extract_numbers(ocr_result)
        
        # Returns list of strings
        assert "123" in nums
        assert "500" in nums
        assert "5.5" in nums

    def test_empty_image_handling(self, mock_rapid_ocr):
        """Test safe handling of empty or None image."""
        # If the handler passes None to the engine, ensure engine returns nothing
        mock_rapid_ocr.return_value = (None, None)
        
        results, stats = self.handler.do_ocr(None)
        assert results == []
        
        empty_img = np.array([])
        results, stats = self.handler.do_ocr(empty_img)
        assert results == []

    @patch('backend.processing.rapidocr_handler.RAPIDOCR_AVAILABLE', False)
    def test_rapidocr_not_available(self):
        """Test when rapidocr_onnxruntime is not installed"""
        handler = RapidOCRHandler({})
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        results, stats = handler.do_ocr(img)
        assert results == []
        assert stats["engine"] == "rapidocr"
        assert stats["text_blocks_count"] == 0

    @patch('backend.processing.rapidocr_handler.RapidOCR')
    def test_rapidocr_init_exception(self, MockRapidOCR):
        """Test gracefully handling RapidOCR constructor exceptions."""
        MockRapidOCR.side_effect = Exception("Init error")
        handler = RapidOCRHandler({})
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        results, stats = handler.do_ocr(img)
        assert results == []
        assert handler.engine is None

    def test_do_ocr_exception(self, mock_rapid_ocr):
        """Test do_ocr exception branch during inference."""
        # Make the mocked instance raise an exception when called
        mock_rapid_ocr.side_effect = Exception("Inference error")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        results, stats = self.handler.do_ocr(img)
        assert results == []
        assert "error" in stats
        assert stats["error"] == "Inference error"

    def test_do_ocr_list_elapse(self, mock_rapid_ocr):
        """Test calculating ocr_time if elapse is a list."""
        mock_rapid_ocr.return_value = (
            [
                [[[0,0], [10,0], [10,10], [0,10]], "text1", 0.99]
            ], 
            [0.1, 0.2, 0.3]
        )
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        results, stats = self.handler.do_ocr(img)
        assert len(results) == 1
        assert stats["ocr_engine_time_s"] == 0.6

    def test_to_plain_text_empty(self):
        """Test to_plain_text on empty result."""
        assert self.handler.to_plain_text([]) == ""

