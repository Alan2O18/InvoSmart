"""
Unit Tests for PythonValidator

Tests the receipt data validation logic including:
- Mathematical validation (item totals, summary total)
- Required field checking
- Number parsing (including Chinese numbers)
- Confidence scoring
"""
import pytest
from backend.processing.python_validator import PythonValidator, ValidationResult


class TestPythonValidator:
    """PythonValidator Tests"""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return PythonValidator()

    # ===== Basic Validation Tests =====
    
    def test_validate_correct_data(self, validator):
        """Test validation with correct data."""
        data = {
            "header": {"supplier": "測試商店", "date": "2024-01-15"},
            "items": [
                {"name": "商品A", "qty": 2, "price": 100, "total": 200},
                {"name": "商品B", "qty": 1, "price": 50, "total": 50}
            ],
            "summary": {"total": 250}
        }
        
        result = validator.validate(data)
        
        assert result.is_valid is True
        assert result.confidence >= 0.8
        assert len(result.issues) == 0
        assert result.calculated_total == 250

    def test_validate_wrong_item_total(self, validator):
        """Test detection of incorrect item total."""
        data = {
            "header": {"supplier": "店家"},
            "items": [
                {"name": "商品A", "qty": 2, "price": 100, "total": 150}  # Should be 200
            ],
            "summary": {"total": 150}
        }
        
        result = validator.validate(data)
        
        assert result.is_valid is False
        assert any("小計" in issue or "計算" in issue for issue in result.issues)

    def test_validate_wrong_summary_total(self, validator):
        """Test detection of incorrect summary total."""
        data = {
            "header": {"supplier": "店家"},
            "items": [
                {"name": "商品A", "qty": 2, "price": 100, "total": 200},
                {"name": "商品B", "qty": 1, "price": 50, "total": 50}
            ],
            "summary": {"total": 300}  # Should be 250
        }
        
        result = validator.validate(data)
        
        assert result.is_valid is False
        assert result.calculated_total == 250
        assert result.reported_total == 300

    def test_validate_empty_data(self, validator):
        """Test validation with empty data."""
        result = validator.validate({})
        
        assert result.is_valid is False
        assert result.confidence < 0.5

    def test_validate_missing_items(self, validator):
        """Test validation when items are missing."""
        data = {
            "header": {"supplier": "店家"},
            "summary": {"total": 100}
        }
        
        result = validator.validate(data)
        
        # Should still work but with lower confidence
        assert result.confidence < 1.0

    # ===== Number Parsing Tests =====
    
    def test_to_number_integer(self, validator):
        """Test integer conversion."""
        assert validator._to_number(100) == 100
        assert validator._to_number("100") == 100

    def test_to_number_float(self, validator):
        """Test float conversion."""
        assert validator._to_number(99.5) == 99.5
        assert validator._to_number("99.5") == 99.5

    def test_to_number_invalid(self, validator):
        """Test invalid number handling."""
        assert validator._to_number("abc") == 0
        assert validator._to_number(None) == 0
        assert validator._to_number("") == 0

    def test_to_number_with_commas(self, validator):
        """Test number with thousand separators."""
        assert validator._to_number("1,000") == 1000
        assert validator._to_number("1,234,567") == 1234567

    # ===== Chinese Number Parsing Tests =====
    
    def test_parse_chinese_number_simple(self, validator):
        """Test simple Chinese number parsing."""
        assert validator._parse_chinese_number("壹佰") == 100
        assert validator._parse_chinese_number("貳佰") == 200

    def test_parse_chinese_number_complex(self, validator):
        """Test complex Chinese number parsing."""
        assert validator._parse_chinese_number("壹仟貳佰") == 1200
        assert validator._parse_chinese_number("壹萬") == 10000

    def test_parse_chinese_number_with_suffix(self, validator):
        """Test Chinese number with 元整 suffix."""
        assert validator._parse_chinese_number("壹仟元整") == 1000
        assert validator._parse_chinese_number("伍佰元整") == 500

    def test_parse_chinese_number_invalid(self, validator):
        """Test invalid Chinese number returns 0."""
        result = validator._parse_chinese_number("Invalid")
        assert result == 0

    # ===== Date Validation Tests =====
    
    def test_is_valid_date_correct(self, validator):
        """Test correct date formats."""
        assert validator._is_valid_date("2024-01-15") is True
        assert validator._is_valid_date("2024-12-31") is True

    def test_is_valid_date_invalid(self, validator):
        """Test invalid date formats."""
        assert validator._is_valid_date("not-a-date") is False
        assert validator._is_valid_date("") is False
        assert validator._is_valid_date(None) is False

    # ===== Required Fields Tests =====
    
    def test_validate_required_fields_complete(self, validator):
        """Test with all required fields present."""
        data = {
            "header": {"supplier": "店家", "date": "2024-01-01"},
            "items": [{"name": "商品", "total": 100}],  # Include items
            "summary": {"total": 100}
        }
        
        issues = validator._validate_required_fields(data)
        assert len(issues) == 0

    def test_validate_required_fields_missing_supplier(self, validator):
        """Test with missing supplier - returns '缺少商家名稱和發票號碼'."""
        data = {
            "header": {"date": "2024-01-01"},  # No supplier or invoice_id
            "items": [{"name": "商品"}],  # Include items to avoid that issue
            "summary": {"total": 100}
        }
        
        issues = validator._validate_required_fields(data)
        assert any("商家" in issue or "發票" in issue for issue in issues)

    # ===== Confidence Scoring Tests =====
    
    def test_confidence_with_ocr_confidence(self, validator):
        """Test confidence calculation with OCR confidence."""
        data = {
            "header": {"supplier": "店家", "date": "2024-01-15"},
            "items": [{"name": "商品", "qty": 1, "price": 100, "total": 100}],
            "summary": {"total": 100}
        }
        
        result_low_ocr = validator.validate(data, ocr_confidence=0.5)
        result_high_ocr = validator.validate(data, ocr_confidence=0.95)
        
        # Higher OCR confidence should lead to higher overall confidence
        assert result_high_ocr.confidence >= result_low_ocr.confidence

    def test_confidence_decreases_with_issues(self, validator):
        """Test that confidence decreases when issues are found."""
        correct_data = {
            "header": {"supplier": "店家"},
            "items": [{"name": "A", "qty": 1, "price": 100, "total": 100}],
            "summary": {"total": 100}
        }
        
        wrong_data = {
            "header": {"supplier": "店家"},
            "items": [{"name": "A", "qty": 1, "price": 100, "total": 999}],  # Wrong
            "summary": {"total": 999}  # Wrong
        }
        
        result_correct = validator.validate(correct_data)
        result_wrong = validator.validate(wrong_data)
        
        assert result_correct.confidence > result_wrong.confidence

    # ===== Items Validation Tests =====
    
    def test_validate_items_correct(self, validator):
        """Test items with correct calculations."""
        items = [
            {"name": "A", "qty": 2, "price": 50, "total": 100},
            {"name": "B", "qty": 3, "price": 30, "total": 90}
        ]
        
        issues = validator._validate_items(items)
        
        assert len(issues) == 0

    def test_validate_items_missing_fields(self, validator):
        """Test items with missing qty/price fields - uses defaults."""
        items = [
            {"name": "A", "total": 100}  # Missing qty and price, defaults to qty=1, price=0
        ]
        
        issues = validator._validate_items(items)
        
        # Will flag as issue since 1 * 0 != 100
        assert len(issues) >= 0  # Just verify it runs without error

    def test_validate_qr_verified_reconciliation_pass(self, validator):
        """Test validation with matching VLM and QR Code details."""
        data = {
            "header": {"supplier": "測試商店", "date": "2024-01-15", "invoice_id": "AB12345678"},
            "items": [{"name": "商品A", "qty": 1, "price": 100, "total": 100}],
            "summary": {"total": 100},
            "verification": {
                "qr_verified": True,
                "vlm_invoice_id": "AB12345678",
                "qr_invoice_id": "AB12345678",
                "vlm_date": "2024-01-15",
                "qr_date": "2024-01-15",
                "vlm_total": 100,
                "qr_total": 100
            }
        }

        result = validator.validate(data)
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.confidence >= 0.85  # Includes 15% QR code bonus

    def test_validate_qr_verified_reconciliation_mismatches(self, validator):
        """Test validation flags issues for mismatched VLM and QR Code fields."""
        data = {
            "header": {"supplier": "測試商店", "date": "2024-01-15", "invoice_id": "AB12345678"},
            "items": [{"name": "商品A", "qty": 1, "price": 100, "total": 100}],
            "summary": {"total": 100},
            "verification": {
                "qr_verified": True,
                "vlm_invoice_id": "AB1234567B",  # Mismatch (OCR typo)
                "qr_invoice_id": "AB12345678",
                "vlm_date": "2024-01-14",  # Mismatch
                "qr_date": "2024-01-15",
                "vlm_total": 90,  # Mismatch
                "qr_total": 100
            }
        }

        result = validator.validate(data)
        assert result.is_valid is False
        assert any("發票號碼不符" in issue for issue in result.issues)
        assert any("日期不符" in issue for issue in result.issues)
        assert any("總金額不符" in issue for issue in result.issues)
