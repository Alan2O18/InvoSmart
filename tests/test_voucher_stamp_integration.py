"""Tests for stamp integration in voucher generation"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import fitz

from backend.engine.voucher_generator import VoucherGenerator
from backend.engine.voucher_text_config import STAMP_ZONES, STITCHED_SEAL_CONFIG


@pytest.fixture
def temp_template_pdf(temp_workspace):
    """Create a temporary template PDF for testing."""
    template_path = temp_workspace / "template.pdf"
    
    # Create a simple A4 PDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Test Voucher Template")
    doc.save(str(template_path))
    doc.close()
    
    yield str(template_path)


@pytest.fixture
def mock_stamp_bytes():
    """Create mock stamp image bytes (minimal PNG)."""
    # Minimal PNG with transparency
    # PNG header + minimal data
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'


@pytest.mark.asyncio
async def test_stamp_zones_configuration():
    """Test that STAMP_ZONES is properly configured."""
    assert "handler" in STAMP_ZONES
    assert "activity_general_affairs" in STAMP_ZONES
    assert "general_affairs_head" in STAMP_ZONES
    assert "president" in STAMP_ZONES
    assert "advisor" in STAMP_ZONES
    assert "club_seal" in STAMP_ZONES
    
    # Check that each zone has the required rect format [x0, y0, width, height]
    for role, config in STAMP_ZONES.items():
        assert "rect" in config
        assert len(config["rect"]) == 4
        assert all(isinstance(x, (int, float)) for x in config["rect"])


@pytest.mark.asyncio
async def test_stitched_seal_configuration():
    """Test that STITCHED_SEAL_CONFIG is properly configured."""
    assert "fin_original" in STITCHED_SEAL_CONFIG
    assert "fin_audited" in STITCHED_SEAL_CONFIG
    
    for role, config in STITCHED_SEAL_CONFIG.items():
        assert "label" in config
        assert "position" in config
        assert config["position"] in ("edge", "bottom")


def test_voucher_generator_init(temp_template_pdf):
    """Test VoucherGenerator initialization."""
    generator = VoucherGenerator(template_path=temp_template_pdf)
    assert generator.template_path == temp_template_pdf


def test_get_stamp_image_bytes_nonexistent_file(temp_workspace):
    """Test _get_stamp_image_bytes with nonexistent file."""
    result = VoucherGenerator._get_stamp_image_bytes(str(temp_workspace / "nonexistent.png"))
    assert result is None


def test_get_stamp_image_bytes_valid_file(temp_workspace, mock_stamp_bytes):
    """Test _get_stamp_image_bytes with valid file."""
    stamp_file = temp_workspace / "test_stamp.png"
    stamp_file.write_bytes(mock_stamp_bytes)
    
    result = VoucherGenerator._get_stamp_image_bytes(str(stamp_file))
    assert result == mock_stamp_bytes


def test_insert_stamp_with_page(mock_stamp_bytes):
    """Test _insert_stamp adds image to page."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    rect = fitz.Rect(100, 100, 150, 150)
    
    # This should not raise an error
    VoucherGenerator._insert_stamp(page, mock_stamp_bytes, rect, rotation=5)
    
    doc.close()


def test_insert_stamp_with_none_bytes():
    """Test _insert_stamp with None bytes."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    rect = fitz.Rect(100, 100, 150, 150)
    
    # Should return early without error
    VoucherGenerator._insert_stamp(page, None, rect)
    
    doc.close()


def test_apply_stamps_to_page_empty_stamps(temp_template_pdf):
    """Test _apply_stamps_to_page with empty stamps dict."""
    generator = VoucherGenerator(template_path=temp_template_pdf)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    # Should not raise error
    generator._apply_stamps_to_page(page, {})
    
    doc.close()


def test_apply_stamps_to_page_with_valid_stamps(temp_template_pdf, temp_workspace, mock_stamp_bytes):
    """Test _apply_stamps_to_page with valid stamps."""
    # Create test stamp files
    stamp_files = {}
    for role in ["handler", "president", "club_seal"]:
        stamp_file = temp_workspace / f"{role}_stamp.png"
        stamp_file.write_bytes(mock_stamp_bytes)
        stamp_files[role] = str(stamp_file)
    
    generator = VoucherGenerator(template_path=temp_template_pdf)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    
    # Apply stamps
    generator._apply_stamps_to_page(page, stamp_files)
    
    doc.close()


def test_generate_from_layout_without_stamps(temp_template_pdf, temp_workspace):
    """Test generate_from_layout without stamps (backward compatibility)."""
    generator = VoucherGenerator(template_path=temp_template_pdf)
    
    pages = [
        {
            "pageIndex": 0,
            "fields": {
                "voucherNo": "001",
                "budgetItem": "Test",
                "amount": "1000",
                "purpose": "Testing",
                "receiptCount": "1",
                "payDate": "2026-05-01",
            },
            "images": []
        }
    ]
    
    output_path = str(temp_workspace / "output.pdf")
    
    # Should work without stamps parameter
    result = generator.generate_from_layout(pages, {}, output_path)
    assert result is True
    assert Path(output_path).exists()


def test_generate_from_layout_with_stamps(temp_template_pdf, temp_workspace, mock_stamp_bytes):
    """Test generate_from_layout with stamps."""
    # Create test stamp files
    stamp_files = {}
    for role in ["handler", "president", "club_seal", "fin_original", "fin_audited"]:
        stamp_file = temp_workspace / f"{role}_stamp.png"
        stamp_file.write_bytes(mock_stamp_bytes)
        stamp_files[role] = str(stamp_file)
    
    generator = VoucherGenerator(template_path=temp_template_pdf)
    
    pages = [
        {
            "pageIndex": 0,
            "fields": {
                "voucherNo": "001",
                "budgetItem": "Test",
                "amount": "1000",
                "purpose": "Testing",
                "receiptCount": "1",
                "payDate": "2026-05-01",
            },
            "images": []
        }
    ]
    
    output_path = str(temp_workspace / "output_with_stamps.pdf")
    
    # Generate with stamps
    result = generator.generate_from_layout(pages, {}, output_path, stamps=stamp_files)
    assert result is True
    assert Path(output_path).exists()
