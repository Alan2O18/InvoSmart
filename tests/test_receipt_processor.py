"""
Unit Tests for ReceiptProcessor (VLM-First Architecture)

Tests the integrated receipt processing pipeline with mocked dependencies.
Only 3 sub-handlers: VisionHandler, QRHandler, PythonValidator.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from backend.processing.receipt_processor import ReceiptProcessor


class TestReceiptProcessor:
    """ReceiptProcessor Integration Tests with Mocks (VLM-First)"""

    @pytest.fixture
    def mock_processor(self):
        """
        Setup ReceiptProcessor with all sub-handlers mocked.
        VLM-First architecture only has 3 handlers:
        - VisionHandler (Gemini VLM)
        - QRHandler
        - PythonValidator
        """
        with patch('backend.processing.receipt_processor.VisionHandler') as MockVision, \
             patch('backend.processing.receipt_processor.QRHandler') as MockQR, \
             patch('backend.processing.receipt_processor.PythonValidator') as MockValidator, \
             patch('backend.processing.receipt_processor.SuggestionRepository') as MockRepo:

            vision = MockVision.return_value
            qr = MockQR.return_value
            validator = MockValidator.return_value
            repo = MockRepo.return_value

            # Default: validation passes
            validator.validate.return_value = MagicMock(
                is_valid=True, issues=[], confidence=1.0
            )

            processor = ReceiptProcessor({})

            mocks = {
                'vision': vision,
                'qr': qr,
                'validator': validator,
                'repo': repo
            }

            yield processor, mocks

    # =========================================================================
    # Happy Path Tests
    # =========================================================================

    def test_process_success_with_qr(self, mock_processor):
        """Test successful VLM processing with QR code verification."""
        processor, mocks = mock_processor

        vlm_result = {
            "header": {
                "supplier": "全家便利超商",
                "invoice_id": "AB12345678",
                "date": "2025-12-09",
            },
            "items": [
                {"name": "海報紙", "qty": 2, "price": 100.0, "total": 200.0},
            ],
            "summary": {"total": 200.0},
        }
        vlm_stats = {"total_time_s": 0.5, "model": "gemini-flash-lite"}

        mocks['vision'].process_image.return_value = (vlm_result, vlm_stats)
        mocks['qr'].detect_and_decode.return_value = {
            "invoice_id": "AB12345678",
            "total": 200,
        }

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)

        assert result["success"] is True
        assert result["result"]["header"]["invoice_id"] == "AB12345678"
        assert result["metadata"]["qr_detected"] is True
        assert result["result"]["verification"]["qr_verified"] is True
        assert result["validation"]["is_valid"] is True

    def test_process_success_without_qr(self, mock_processor):
        """Test successful VLM processing without QR code."""
        processor, mocks = mock_processor

        vlm_result = {
            "header": {"supplier": "小吃店"},
            "items": [{"name": "便當", "qty": 1, "price": 80.0, "total": 80.0}],
            "summary": {"total": 80.0},
        }
        vlm_stats = {"total_time_s": 0.3}

        mocks['vision'].process_image.return_value = (vlm_result, vlm_stats)
        mocks['qr'].detect_and_decode.return_value = None

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)

        assert result["success"] is True
        assert result["result"]["header"]["supplier"] == "小吃店"
        assert result["metadata"]["qr_detected"] is False
        assert "verification" not in result["result"]  # No QR = no verification block

    def test_update_config(self, mock_processor):
        processor, mocks = mock_processor
        processor.update_config({"new": "config"})
        assert processor.config == {"new": "config"}
        mocks['vision'].update_config.assert_called_once_with({"new": "config"})

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_process_vlm_failure(self, mock_processor):
        """Test handling of VLM processing failure."""
        processor, mocks = mock_processor

        mocks['vision'].process_image.return_value = (
            {},
            {"error": "API quota exceeded"},
        )

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)

        assert result["success"] is False
        assert "API quota exceeded" in result["error"]

    def test_process_validation_issues(self, mock_processor):
        """Test processing with validation issues detected."""
        processor, mocks = mock_processor

        vlm_result = {
            "header": {"supplier": "Test"},
            "items": [{"name": "A", "qty": 2, "price": 100, "total": 150}],
            "summary": {"total": 300},
        }
        mocks['vision'].process_image.return_value = (vlm_result, {"total_time_s": 0.2})
        mocks['qr'].detect_and_decode.return_value = None

        # Validator finds issues
        mocks['validator'].validate.return_value = MagicMock(
            is_valid=False,
            issues=["品項小計不一致: 2×100≠150"],
            confidence=0.3,
        )

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)

        assert result["success"] is True  # Still succeeds (validation is advisory)
        assert result["validation"]["is_valid"] is False
        assert len(result["validation"]["issues"]) > 0
        assert result["validation"]["confidence"] == 0.3

    # =========================================================================
    # _merge_qr_data Tests
    # =========================================================================

    def test_merge_qr_data_overwrites_header(self, mock_processor):
        """Test QR data overwrites VLM header fields."""
        processor, _ = mock_processor

        vlm_result = {
            "header": {"invoice_id": "WRONG123", "supplier": "Shop"},
            "summary": {"total": 100},
        }
        qr_data = {"invoice_id": "AB12345678", "date": "2025-01-01", "total": 200}

        merged = processor._merge_qr_data(vlm_result, qr_data)

        assert merged["header"]["invoice_id"] == "AB12345678"
        assert merged["header"]["date"] == "2025-01-01"
        assert merged["header"]["supplier"] == "Shop"  # Unchanged
        assert merged["summary"]["total"] == 200  # QR total wins
        assert merged["verification"]["qr_verified"] is True

    def test_merge_qr_data_creates_header_if_missing(self, mock_processor):
        """Test QR merge creates header dict if missing."""
        processor, _ = mock_processor

        vlm_result = {"items": [], "summary": {"total": 50}}
        qr_data = {"invoice_id": "CD99999999"}

        merged = processor._merge_qr_data(vlm_result, qr_data)

        assert merged["header"]["invoice_id"] == "CD99999999"

    # =========================================================================
    # _create_error_result Tests
    # =========================================================================

    def test_create_error_result(self, mock_processor):
        """Test error result structure."""
        processor, _ = mock_processor

        result = processor._create_error_result("Something went wrong", [{"stage": "vlm"}])

        assert result["success"] is False
        assert result["error"] == "Something went wrong"
        assert result["result"] == {}
        assert result["metadata"]["stats"] == [{"stage": "vlm"}]

    # =========================================================================
    # Metadata Tests
    # =========================================================================

    def test_process_includes_timing_metadata(self, mock_processor):
        """Test that processing result includes timing metadata."""
        processor, mocks = mock_processor

        mocks['vision'].process_image.return_value = (
            {"header": {}, "items": [], "summary": {}},
            {"total_time_s": 1.5},
        )
        mocks['qr'].detect_and_decode.return_value = None

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = processor.process(img)

        assert "total_time_s" in result["metadata"]
        assert result["metadata"]["total_time_s"] >= 0
        assert "stats" in result["metadata"]
        assert len(result["metadata"]["stats"]) >= 1

    def test_process_injects_budget_categories_context(self, mock_processor):
        """Test that project budget categories are injected into VLM prompt_context."""
        processor, mocks = mock_processor
        
        # Mock project repo
        mock_project = {
            "project_id": "proj-123",
            "metadata": {
                "budgetExpense": [
                    {"name": "印製費", "qty": 1, "price": 100, "total": 100},
                    {"name": "餐飲費", "qty": 2, "price": 50, "total": 100}
                ]
            }
        }
        processor.project_repo = MagicMock()
        processor.project_repo.get_project.return_value = mock_project
        
        vlm_result = {"header": {}, "items": [], "summary": {}}
        mocks['vision'].process_image.return_value = (vlm_result, {"total_time_s": 0.2})
        mocks['qr'].detect_and_decode.return_value = None
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.process(img, project_id="proj-123")
        
        # Verify VisionHandler received prompt context containing categories list
        called_args = mocks['vision'].process_image.call_args[1]
        assert "prompt_context" in called_args
        assert "印製費" in called_args["prompt_context"]
        assert "餐飲費" in called_args["prompt_context"]
        assert "允許的品類列表" in called_args["prompt_context"]

    def test_merge_qr_reconciliation_fields(self, mock_processor):
        """Test that _merge_qr_data backs up VLM fields and records QR data for reconciliation."""
        processor, _ = mock_processor

        vlm_result = {
            "header": {"invoice_id": "WRONG123", "supplier": "Shop", "date": "2025-01-01"},
            "summary": {"total": 100},
        }
        qr_data = {"invoice_id": "AB12345678", "date": "2025-01-02", "total": 200}

        merged = processor._merge_qr_data(vlm_result, qr_data)

        verification = merged["verification"]
        assert verification["qr_verified"] is True
        assert verification["vlm_invoice_id"] == "WRONG123"
        assert verification["vlm_date"] == "2025-01-01"
        assert verification["vlm_total"] == 100
        
        assert verification["qr_invoice_id"] == "AB12345678"
        assert verification["qr_date"] == "2025-01-02"
        assert verification["qr_total"] == 200
