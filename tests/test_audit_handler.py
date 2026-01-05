"""
Unit Tests for AuditHandler

Tests validation logic for electronic and handwritten receipts using mocks.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
from backend.processing.audit_handler import AuditHandler

class TestAuditHandler:
    """AuditHandler Tests with Mocks"""

    @pytest.fixture
    def mock_ollama(self):
        """Mock the ollama library."""
        with patch('backend.processing.audit_handler.ollama') as MockOllama:
            yield MockOllama

    def setup_method(self):
        self.handler = AuditHandler({})

    def test_audit_electronic_invoice_match(self):
        """Test auditing when VLM matches QR code."""
        # Using Markdown string as expected by audit_electronic
        vlm_markdown = """
        **發票號碼**: AB12345678
        **合計**: 100
        """
        qr_data = {"invoice_id": "AB12345678", "total": 100}
        
        # Using LLM mock to return success
        with patch.object(self.handler, '_call_llm') as mock_llm:
            mock_llm.return_value = '{"is_valid": true, "issues": [], "confidence": 0.95}'
            
            result = self.handler.audit_electronic(vlm_markdown, qr_data)
            
            assert result["is_valid"] is True
            assert result.get("confidence", 0) > 0.9

    def test_audit_electronic_invoice_mismatch(self):
        """Test auditing when VLM ID mismatches QR code."""
        vlm_markdown = """
        **發票號碼**: XY98765432
        **合計**: 100
        """
        qr_data = {"invoice_id": "AB12345678", "total": 100}
        
        with patch.object(self.handler, '_call_llm') as mock_llm:
            mock_llm.return_value = '{"is_valid": false, "discrepancies": ["Invoice ID mismatch"], "confidence": 0.8}'
            
            result = self.handler.audit_electronic(vlm_markdown, qr_data)
            
            assert result["is_valid"] is False
            assert "Invoice ID mismatch" in result["discrepancies"]
    
    def test_audit_handwritten_validation_logic(self, mock_ollama):
        """Test logic validation (math check) for handwritten receipt."""
        # audit_traditional expects vlm_markdown and ocr_text
        vlm_markdown = "**合計**: 200"
        ocr_text = "TOTAL 200"
        
        mock_chunk = {
             "message": {
                 "content": '{"is_valid": true, "issues": [], "confidence": 0.95}'
             },
             "done": True
        }
        # chat returns an iterable (stream)
        mock_ollama.chat.return_value = [mock_chunk]
        
        result = self.handler.audit_traditional(vlm_markdown, ocr_text)
        
        assert result["is_valid"] is True
        assert result["confidence"] == 0.95

    def test_audit_handwritten_math_error(self, mock_ollama):
        """Test detecting math error in handwritten receipt."""
        vlm_markdown = "**合計**: 500"
        ocr_text = "Total 200"
        
        mock_chunk = {
             "message": {
                 "content": '{"is_valid": false, "discrepancies": ["Total mismatch"], "confidence": 0.8}'
             },
             "done": True
        }
        mock_ollama.chat.return_value = [mock_chunk]
        
        result = self.handler.audit_traditional(vlm_markdown, ocr_text)
        
        assert result["is_valid"] is False
        assert "Total mismatch" in result["discrepancies"]

    def test_parse_audit_response_json_repair(self):
        """Test parsing malformed JSON from LLM."""
        malformed = '```json {"is_valid": true} ```'
        parsed = self.handler._parse_json_response(malformed)
        assert parsed["is_valid"] is True
