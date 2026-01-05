"""
Unit Tests for KeywordClassifier

Tests the logic for classifying receipts based on OCR text and visual features.
"""
import pytest
from backend.processing.keyword_classifier import KeywordClassifier, ReceiptType

class TestKeywordClassifier:
    """關鍵字分類器測試"""

    def setup_method(self):
        """Setup classifier instance before each test."""
        self.classifier = KeywordClassifier()

    # ============================================================================
    # Electronic Invoice Tests (電子發票)
    # ============================================================================

    def test_classify_electronic_invoice_with_keywords(self):
        """Test classifying electronic invoice based on strong keywords."""
        # Need score >= 2. "電子發票" (+1), "載具" (+1) -> Score 2
        text = "電子發票證明聯 載具號碼: /ABC.123"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.ELECTRONIC
        assert "電子發票" in result.matched_keywords
        assert result.confidence >= 0.5

    def test_classify_electronic_invoice_with_qr_code(self):
        """Test classifying electronic invoice when QR code is detected."""
        text = "一些模糊的文字..."
        # Simulate QR code detected (- score +3)
        result = self.classifier.classify(text, has_qr_code=True)
        
        assert result.receipt_type == ReceiptType.ELECTRONIC
        assert "QR Code" in result.matched_keywords
        assert result.confidence >= 0.8

    def test_classify_electronic_invoice_with_pattern(self):
        """Test classifying electronic invoice based on invoice number pattern."""
        # Pattern (+1), plus "電子發票" (+1) -> Score 2
        # Just pattern (Score 1) is not enough for strict classification
        text = "電子發票號碼: AB-12345678"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.ELECTRONIC
        assert any("pattern" in k for k in result.matched_keywords)

    def test_classify_electronic_invoice_carrier(self):
        """Test classifying based on carrier keywords."""
        text = "手機條碼 / 載具號碼"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.ELECTRONIC
        assert "手機條碼" in result.matched_keywords or "載具" in result.matched_keywords

    # ============================================================================
    # Handwritten Receipt Tests (手寫收據)
    # ============================================================================

    def test_classify_handwritten_receipt(self):
        """Test classifying handwritten receipt based on specific keywords."""
        text = "免用統一發票收據 統一編號:12345678"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.HANDWRITTEN
        assert "免用統一發票" in result.matched_keywords
        assert result.confidence > 0.5

    def test_classify_handwritten_with_chinese_numbers(self):
        """Test classifying handwritten receipt based on uppercase Chinese numbers."""
        text = "收據 金額: 壹仟貳佰元整"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.HANDWRITTEN
        assert "收據" in result.matched_keywords
        assert "壹" in result.matched_keywords
        assert "貳" in result.matched_keywords

    # ============================================================================
    # Other Receipt Tests (其他/傳統發票/計程車)
    # ============================================================================

    def test_classify_taxi_receipt(self):
        """Test classifying taxi receipt."""
        text = "計程車乘車證明 車資: 200元 里程: 5km"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.OTHER
        assert "計程車" in result.matched_keywords
        assert "車資" in result.matched_keywords

    def test_classify_traditional_invoice(self):
        """Test classifying traditional invoice (unified invoice)."""
        text = "統一發票 113年1月 12345678"
        # If it matches "統一發票" but lacks electronic/handwritten features, it settles as OTHER
        result = self.classifier.classify(text)
        
        # Note: Depending on implementation details, "統一發票" might be common to multiple types.
        # But if it doesn't match electronic (no QR, no '電子') or handwritten ('免用'), 
        # it should fall back to OTHER.
        assert result.receipt_type in [ReceiptType.OTHER, ReceiptType.UNKNOWN]
        if result.receipt_type == ReceiptType.OTHER:
             assert "統一發票" in result.matched_keywords

    # ============================================================================
    # Edge Cases Tests
    # ============================================================================

    def test_classify_empty_text(self):
        """Test classifying empty or None text."""
        result = self.classifier.classify("")
        assert result.receipt_type == ReceiptType.UNKNOWN
        assert result.confidence == 0.0
        
        result = self.classifier.classify(None)
        assert result.receipt_type == ReceiptType.UNKNOWN

    def test_classify_ambiguous_text(self):
        """
        Test text that doesn't match any known keywords.
        Should default to OTHER with low confidence.
        """
        text = "這是一張普通的紙條"
        result = self.classifier.classify(text)
        
        assert result.receipt_type == ReceiptType.OTHER
        assert result.confidence == 0.5
        assert len(result.matched_keywords) == 0

    def test_mixed_features_priority(self):
        """
        Test priority when multiple features are present.
        Electronic (QR) > Handwritten > Other
        """
        # Contains "免用統一發票" (Handwritten) but has QR code (Electronic flag)
        text = "免用統一發票收據"
        result = self.classifier.classify(text, has_qr_code=True)
        
        # QR code should force Electronic
        assert result.receipt_type == ReceiptType.ELECTRONIC
        assert "QR Code" in result.matched_keywords

    def test_mixed_features_priority_text_only(self):
        """
        Test priority via text only.
        Electronic keywords > Handwritten
        """
        # "電子發票" vs "收據"
        text = "電子發票證明聯 載具 收據"
        result = self.classifier.classify(text)
        
        # Should distinguish. Look at implementation scoring:
        # electronic matching is checked first in classify() method.
        # If electronic matches returns good score, it returns immediately.
        assert result.receipt_type == ReceiptType.ELECTRONIC
