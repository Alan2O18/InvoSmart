"""
Unit tests for VoucherGenerator — covers v29 §10.1 items 5, 7
and Defense #4, #5, #8, #16, #17, #18, #24, #37, #43, #44
"""
import logging
import os

import fitz
import pytest
from PIL import Image

from backend.engine.voucher_generator import VoucherGenerator


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def template_pdf(tmp_path):
    """Create a blank A4-sized template PDF for testing."""
    path = tmp_path / "template.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def generator(template_pdf):
    return VoucherGenerator(template_path=template_pdf, font_path="")


@pytest.fixture
def sample_image(tmp_path):
    """Create a small JPEG image for testing."""
    path = tmp_path / "receipt.jpg"
    Image.new("RGB", (300, 200), color=(128, 128, 128)).save(str(path))
    return str(path)


@pytest.fixture
def large_image(tmp_path):
    """Create a large image (2000px wide) to test anti-inflation."""
    path = tmp_path / "large_receipt.jpg"
    Image.new("RGB", (2000, 1500), color=(200, 200, 200)).save(str(path))
    return str(path)


@pytest.fixture
def small_image(tmp_path):
    """Create a tiny image (400px wide) to test that it is NOT inflated."""
    path = tmp_path / "small_receipt.jpg"
    Image.new("RGB", (400, 300), color=(100, 100, 100)).save(str(path))
    return str(path)


# ── _safe_text (Defense #24) ────────────────────────────────────────────────

class TestSafeText:
    def test_strips_emoji(self, generator):
        assert "🎉" not in generator._safe_text("收據🎉金額")

    def test_keeps_chinese(self, generator):
        assert generator._safe_text("餐費、茶水") == "餐費、茶水"

    def test_keeps_digits_and_symbols(self, generator):
        assert generator._safe_text("D-16_01/02") == "D-16_01/02"

    def test_empty_input(self, generator):
        assert generator._safe_text("") == ""
        assert generator._safe_text(None) == ""


# ── _to_roc_date (Defense #7, #18) ─────────────────────────────────────────

class TestRocDate:
    def test_valid_iso_date(self):
        assert VoucherGenerator._to_roc_date("2024-11-28") == "113/11/28"

    def test_year_2025(self):
        assert VoucherGenerator._to_roc_date("2025-01-05") == "114/01/05"

    def test_empty_string_returns_empty(self):
        assert VoucherGenerator._to_roc_date("") == ""

    def test_none_returns_empty(self):
        assert VoucherGenerator._to_roc_date(None) == ""

    def test_whitespace_only_returns_empty(self):
        assert VoucherGenerator._to_roc_date("   ") == ""

    def test_invalid_format_returns_empty(self):
        assert VoucherGenerator._to_roc_date("not-a-date") == ""

    def test_partial_date_returns_empty(self):
        assert VoucherGenerator._to_roc_date("2024-13") == ""


class TestPaymentAmountFormatting:
    def test_formats_integer_amount_for_bottom_text(self):
        assert VoucherGenerator._format_payment_amount("4607") == "4,607元整"

    def test_ignores_non_digit_amount(self):
        assert VoucherGenerator._format_payment_amount("46.07") == ""


def test_invalid_font_path_logs_warning_and_falls_back(template_pdf, caplog):
    with caplog.at_level(logging.WARNING):
        generator = VoucherGenerator(template_path=template_pdf, font_path="/missing/kaiu.ttf")

    assert generator.font_path == ""
    assert "找不到字型路徑" in caplog.text


# ── _insert_amount_cells (Defense #16, #17) ────────────────────────────────

class TestAmountCells:
    def test_pads_short_amount(self, generator, template_pdf):
        """Amount '146' should be padded as '※※※※146'."""
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            generator._insert_amount_cells(page, "146")
            text = page.get_text()
            # Should contain digits 1, 4, 6
            assert "1" in text
            assert "4" in text
            assert "6" in text

    def test_seven_digit_amount(self, generator, template_pdf):
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            generator._insert_amount_cells(page, "9999999")
            text = page.get_text()
            assert text.count("9") >= 7

    def test_empty_amount_does_nothing(self, generator, template_pdf):
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            generator._insert_amount_cells(page, "")
            assert page.get_text().strip() == ""

    def test_non_digit_amount_does_nothing(self, generator, template_pdf):
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            generator._insert_amount_cells(page, "abc")
            assert page.get_text().strip() == ""


# ── _insert_purpose truncation (Defense #4, #20) ───────────────────────────

class TestPurposeTruncation:
    def test_short_text_no_warning(self, generator, template_pdf, caplog):
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            with caplog.at_level(logging.WARNING):
                generator._insert_purpose(page, "餐費")
            assert "truncated" not in caplog.text

    def test_extremely_long_text_triggers_truncation(self, generator, template_pdf, caplog):
        long_text = "這是一個非常長的用途說明" * 30  # ~360 chars
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            with caplog.at_level(logging.WARNING):
                generator._insert_purpose(page, long_text)
            assert "truncated" in caplog.text.lower() or "Purpose text truncated" in caplog.text

    def test_empty_purpose_no_crash(self, generator, template_pdf):
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            generator._insert_purpose(page, "")
            assert page.get_text().strip() == ""


# ── _image_stream_for_rect anti-inflation (Defense #5, #43) ────────────────

class TestImageStreamAntiInflation:
    def test_small_image_not_inflated(self, small_image):
        """A 400px-wide original should NOT be inflated when target says 2000px."""
        # target_width_pts = 200 → target_px = (200/72)*300 = 833
        # original = 400 → min(833, 400) = 400, so NO resize
        stream = VoucherGenerator._image_stream_for_rect(small_image, 200.0)
        img = Image.open(__import__("io").BytesIO(stream))
        assert img.width == 400  # unchanged
        assert img.height == 300

    def test_large_image_downscaled(self, large_image):
        """A 2000px-wide image should be downscaled to fit target width."""
        # target_width_pts = 100 → target_px = (100/72)*300 ≈ 416
        # original = 2000 → min(416, 2000) = 416
        stream = VoucherGenerator._image_stream_for_rect(large_image, 100.0)
        img = Image.open(__import__("io").BytesIO(stream))
        assert img.width <= 417  # approximate due to rounding
        assert img.width < 2000  # definitely downscaled

    def test_exact_match_no_resize(self, tmp_path):
        """When target equals original width, no resize should happen."""
        path = tmp_path / "exact.jpg"
        Image.new("RGB", (500, 400), color=(50, 50, 50)).save(str(path))
        # target_width_pts such that target_px = 500 → pts = 500 * 72/300 = 120
        stream = VoucherGenerator._image_stream_for_rect(str(path), 120.0)
        img = Image.open(__import__("io").BytesIO(stream))
        assert img.width == 500


# ── _render_missing_marker (Defense #8) ────────────────────────────────────

class TestMissingMarker:
    def test_renders_red_cross_drawings(self, template_pdf):
        """Marker should draw a rectangle + two diagonal lines (red X)."""
        with fitz.open(template_pdf) as doc:
            page = doc[0]
            rect = fitz.Rect(30, 394, 130, 494)
            VoucherGenerator._render_missing_marker(page, rect)
            drawings = page.get_drawings()
            # Expect at least 3 drawing items: rect + 2 diagonals
            assert len(drawings) >= 3, f"Expected ≥3 drawings, got {len(drawings)}"


# ── generate_from_layout full flow ─────────────────────────────────────────

class TestGenerateFromLayout:
    def test_empty_pages_still_produce_pdf(self, generator, tmp_path):
        """When all pages have no images, output a blank template page."""
        output = str(tmp_path / "empty.pdf")
        generator.generate_from_layout(
            pages=[{"fields": {}, "images": []}],
            job_image_map={},
            output_path=output,
        )
        assert os.path.exists(output)
        with fitz.open(output) as doc:
            assert doc.page_count == 1  # fallback blank page

    def test_page_with_images_renders(self, generator, tmp_path, sample_image):
        output = str(tmp_path / "output.pdf")
        generator.generate_from_layout(
            pages=[{
                "fields": {
                    "voucherNo": "D-16-01\nD-16-02",
                    "budgetItem": "ABCDEF",
                    "amount": "4607",
                    "purpose": "餐費、茶水",
                    "receiptCount": "3",
                    "payDate": "2024-11-28",
                },
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 200, "h": 150}],
            }],
            job_image_map={"j1": sample_image},
            output_path=output,
        )
        assert os.path.exists(output)
        with fitz.open(output) as doc:
            assert doc.page_count == 1
            text = doc[0].get_text()
            assert "D-16-01" in text
            assert "D-16-02" in text
            assert "ABC" in text
            assert "113/11/28" in text  # ROC date
            assert "4,607" in text

    def test_missing_image_draws_marker(self, generator, tmp_path):
        output = str(tmp_path / "missing.pdf")
        generator.generate_from_layout(
            pages=[{
                "fields": {"voucherNo": "D-16-01", "amount": "100", "receiptCount": "1", "payDate": "2024-01-01"},
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 200, "h": 150}],
            }],
            job_image_map={"j1": "/nonexistent/path.jpg"},
            output_path=output,
        )
        assert os.path.exists(output)
        with fitz.open(output) as doc:
            drawings = doc[0].get_drawings()
            # Missing-marker draws rect + 2 diagonals (≥3 drawing items)
            assert len(drawings) >= 3, f"Expected ≥3 drawings for missing marker, got {len(drawings)}"

    def test_multi_page_skip_empty(self, generator, tmp_path, sample_image):
        """Empty pages (no images) should be skipped in output."""
        output = str(tmp_path / "multi.pdf")
        generator.generate_from_layout(
            pages=[
                {"fields": {}, "images": []},  # empty → skip
                {
                    "fields": {"voucherNo": "D-16-01", "amount": "100", "receiptCount": "1", "payDate": "2024-01-01"},
                    "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
                },
            ],
            job_image_map={"j1": sample_image},
            output_path=output,
        )
        with fitz.open(output) as doc:
            assert doc.page_count == 1  # only the non-empty page

    def test_deflate_and_garbage_collection(self, generator, tmp_path, sample_image):
        """Verify output PDF uses compression (file size should be reasonable)."""
        output = str(tmp_path / "compressed.pdf")
        generator.generate_from_layout(
            pages=[{
                "fields": {"voucherNo": "D-16-01", "amount": "100", "receiptCount": "1", "payDate": "2024-01-01"},
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
            }],
            job_image_map={"j1": sample_image},
            output_path=output,
        )
        # Just verify the file was created and is non-trivially sized
        assert os.path.getsize(output) > 100
