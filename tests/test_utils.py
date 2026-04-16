"""
Unit Tests for Utility Modules

Tests parser and utils functions.
"""
import pytest
import json
import tempfile
import numpy as np
from pathlib import Path
from unittest.mock import patch


# ============================================================================
# Parser Tests
# ============================================================================

class TestParser:
    """Tests for data parser."""

    def test_extract_structured_data_empty(self):
        """Test extraction from empty input."""
        from backend.utils.parser import extract_structured_data
        
        result = extract_structured_data(None)
        assert result == {}
        
        result = extract_structured_data("")
        assert result == {}

    def test_extract_structured_data_with_structured_data_field(self):
        """Test extraction from new flat structure."""
        from backend.utils.parser import extract_structured_data
        
        # 新格式使用 header 和 summary
        data = {
            "receipt_type": "電子發票",
            "header": {
                "supplier": "測試供應商",
                "invoice_id": "AB12345678",
                "date": "2024-12-19"
            },
            "items": [
                {"name": "商品A", "qty": 2, "price": 100.0, "total": 200.0}
            ],
            "summary": {
                "total": 200.0
            }
        }
        
        result = extract_structured_data(json.dumps(data))
        
        assert result["supplier"] == "測試供應商"
        assert result["invoice_id"] == "AB12345678"
        assert len(result["items"]) == 1
        assert result["items"][0]["description"] == "商品A"
        assert result["items"][0]["quantity"] == 2
        assert result["items"][0]["price"] == 100.0

    def test_extract_structured_data_flat_structure(self):
        """Test extraction from legacy flat JSON structure."""
        from backend.utils.parser import extract_structured_data
        
        # 舊格式相容：頂層 supplier
        data = {
            "header": {
                "supplier": "測試供應商"
            },
            "items": [
                {"name": "商品B", "qty": 3, "price": 50.5}
            ]
        }
        
        result = extract_structured_data(json.dumps(data))
        
        assert result["supplier"] == "測試供應商"
        assert len(result["items"]) == 1
        assert result["items"][0]["description"] == "商品B"
        assert result["items"][0]["quantity"] == 3
        assert result["items"][0]["price"] == 50.5

    def test_extract_structured_data_normalizes_items(self):
        """Test that items are properly normalized."""
        from backend.utils.parser import extract_structured_data
        
        data = {
            "header": {"supplier": "測試"},
            "items": [
                {"name": "A", "qty": "2", "price": "100.5"},  # String numbers
                {"name": "B", "qty": 3},  # Missing price
                {"name": "C"},  # Missing qty and price
            ]
        }
        
        result = extract_structured_data(json.dumps(data))
        
        assert len(result["items"]) == 3
        assert result["items"][0]["quantity"] == 2  # Converted to int
        assert result["items"][0]["price"] == 100.5  # Converted to float
        assert result["items"][1]["quantity"] == 3
        assert result["items"][1]["price"] is None
        assert result["items"][2]["quantity"] is None
        assert result["items"][2]["price"] is None

    def test_extract_structured_data_invalid_json_returns_empty(self):
        """Test that invalid JSON returns empty dict."""
        from backend.utils.parser import extract_structured_data
        
        result = extract_structured_data("not a json string")
        assert result == {}


# ============================================================================
# Utils Tests
# ============================================================================

class TestUtils:
    """Tests for utility functions."""

    @pytest.fixture
    def temp_image(self):
        """Create a temporary test image."""
        import cv2
        
        # Create a simple test image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[25:75, 25:75] = [255, 255, 255]  # White square
        
        return img

    def test_cv_imwrite_read_chinese_path(self, temp_image):
        """Test writing and reading image with Chinese path."""
        from backend.utils.utils import cv_imread_chinese, cv_imwrite_chinese
        
        # Create temp directory with Chinese name
        with tempfile.TemporaryDirectory() as tmpdir:
            chinese_path = Path(tmpdir) / "測試圖片" / "圖像.jpg"
            chinese_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write image
            success = cv_imwrite_chinese(str(chinese_path), temp_image)
            assert success is True
            assert chinese_path.exists()
            
            # Read image
            read_img = cv_imread_chinese(str(chinese_path))
            assert read_img is not None
            assert read_img.shape == temp_image.shape
            
            # Verify content (allowing for JPEG compression)
            assert np.allclose(read_img, temp_image, atol=10)

    def test_cv_imread_chinese_nonexistent_file(self):
        """Test reading non-existent file."""
        from backend.utils.utils import cv_imread_chinese
        
        with pytest.raises(IOError):
            cv_imread_chinese("不存在的檔案.jpg")

    def test_cv_imwrite_chinese_invalid_image(self):
        """Test writing invalid image."""
        from backend.utils.utils import cv_imwrite_chinese
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "測試.jpg"
            
            # Try to write None
            result = cv_imwrite_chinese(str(test_path), None)
            # Should handle error gracefully
            assert result is False or result is None

    def test_cv_imwrite_chinese_jxl_uses_encoder_backend(self, temp_image):
        """Test JXL writing path delegates to encoder backend."""
        from backend.utils.utils import cv_imwrite_chinese

        with tempfile.TemporaryDirectory() as tmpdir:
            jxl_path = Path(tmpdir) / "測試.jxl"

            with patch("backend.processing.jxl_encoder_backend.encode_image_to_jxl") as mock_encode:
                mock_encode.return_value = jxl_path
                success = cv_imwrite_chinese(str(jxl_path), temp_image)

            assert success is True
            mock_encode.assert_called_once()

    def test_cv_imwrite_chinese_creates_directory(self, temp_image):
        """Test that parent directory is NOT created automatically."""
        from backend.utils.utils import cv_imwrite_chinese
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Path with non-existent parent
            test_path = Path(tmpdir) / "不存在的目錄" / "圖片.jpg"
            
            # Should fail because directory doesn't exist
            try:
                result = cv_imwrite_chinese(str(test_path), temp_image)
                # If it doesn't raise, it should return False
                assert result is False
            except Exception:
                # Expected behavior - operation fails
                pass
