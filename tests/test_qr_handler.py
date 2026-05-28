"""
Unit Tests for QRHandler

Tests parsing logic and QR detection for Taiwan Electronic Invoices.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from backend.processing.qr_handler import QRHandler

class TestQRHandler:
    """QR Code Handler Tests"""

    def setup_method(self):
        """Setup QR handler."""
        self.handler = QRHandler({})

    # ============================================================================
    # Parser Logic Tests (Pure Logic)
    # ============================================================================

    def test_parse_taiwan_einvoice_qr_valid(self):
        """Test parsing a valid Taiwan E-Invoice QR code string."""
        # Construct a valid QR string (77 chars)
        # Pos 0-9: Invoice No (AB12345678)
        # Pos 10-16: Date (1130115 -> 2024-01-15)
        # Pos 17-20: Random Code (1234)
        # Pos 21-29: Amount (00000064 -> 100 in hex) -> 100
        # Pos 30-37: Tax Amount (00000000 -> 0)
        # Pos 38-45: Buyer ID (00000000)
        # Pos 46-53: Seller ID (12345678)
        # Pos 54-77: Encryption info
        
        # Based on common spec:
        # 0-2: Inv Id (AB)
        # 2-10: Inv Num (12345678)
        # 10-17: Date (1130115)
        # 17-21: Random (1234)
        # 21-29: Sales Amount (Hex)
        # 29-37: Tax Amount (Hex)
        # 37-45: Buyer ID
        # 45-53: Seller ID
        # 53-77: Encrypt
        
        # Untaxed=100 (64), Tax=0 (00)
        qr_content = "AB123456781130115123400000064000000000000000012345678aabbccddeeffgghhiijjkk"
        # Length check: 10+7+4+8+8+8+8+24 = 77 characters.
        
        result = self.handler._parse_taiwan_einvoice_qr(qr_content)
        
        assert result is not None
        assert result["invoice_id"] == "AB12345678"
        assert result["date"] == "2024-01-15"
        # Hex 64 is 100 decimal + 0 tax
        assert result["total"] == 100
        assert result["seller_id"] == "12345678"

    def test_parse_taiwan_einvoice_qr_invalid_length(self):
        """Test parsing short string."""
        short_qr = "AB12345678"
        result = self.handler._parse_taiwan_einvoice_qr(short_qr)
        assert result is None

    def test_parse_taiwan_einvoice_qr_invalid_date(self):
        """Test parsing invalid date."""
        # Date 9990101 (Year 999 -> 2910?) Valid format but maybe logic handles it?
        # Let's try non-numeric date
        qr_content = "AB12345678ABCDEFG123400000064000000640000000012345678..."
        result = self.handler._parse_taiwan_einvoice_qr(qr_content)
        # Should catch ValueError during date parsing or hex parsing
        assert result is None

    def test_parse_amount_hex_handling(self):
        """Test specific hex amount parsing."""
        # Amount 1A -> 26, Tax 0
        qr_content = "AB12345678113011512340000001A000000000000000012345678..."
        # Pad to sufficient length
        qr_content = qr_content.ljust(80, '0')
        
        result = self.handler._parse_taiwan_einvoice_qr(qr_content)
        assert result["total"] == 26

    # ============================================================================
    # Detection Tests (Mocked QReader)
    # ============================================================================

    @patch("qreader.QReader")
    def test_detect_and_decode_success(self, MockQReader):
        """Test successful detection and decoding with QReader."""
        # Setup mock
        mock_instance = MockQReader.return_value
        # QReader.detect_and_decode returns a tuple/list of strings
        valid_qr = "AB123456781130115123400000064000000000000000012345678aabbccddeeffgghhiijjkk"
        mock_instance.detect_and_decode.return_value = (valid_qr,)
        
        # We need to force reload handler to use the mock class during init
        # But we can just assign the mock if __init__ checked the original class
        # Alternatively, create handler inside the patch scope
        handler = QRHandler({})
        # Ensure qreader is our mock
        handler.qreader = mock_instance
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        result = handler.detect_and_decode(img)
        
        assert result is not None
        assert result["invoice_id"] == "AB12345678"
        assert result["raw_data"] == valid_qr

    @patch("qreader.QReader")
    def test_detect_and_decode_no_qr(self, MockQReader):
        """Test no QR code detected."""
        mock_instance = MockQReader.return_value
        mock_instance.detect_and_decode.return_value = ()
        
        handler = QRHandler({})
        handler.qreader = mock_instance
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        result = handler.detect_and_decode(img)
        assert result is None

    @patch("qreader.QReader")
    def test_detect_and_decode_corrupted_qr(self, MockQReader):
        """Test detected QR but invalid content."""
        mock_instance = MockQReader.return_value
        mock_instance.detect_and_decode.return_value = ("JUNK_DATA",)
        
        handler = QRHandler({})
        handler.qreader = mock_instance
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        
        result = handler.detect_and_decode(img)
        # Should return None because parsing failed
        assert result is None

    # ============================================================================
    # Additional Branch Coverage Tests
    # ============================================================================

    def test_init_qreader_available_false(self):
        with patch.dict("sys.modules", {"qreader": None}):
            handler = QRHandler({})
            assert handler.qreader is None
            assert handler.detect_and_decode(np.zeros((10, 10, 3))) is None
            assert handler.get_qr_locations(np.zeros((10, 10, 3))) == []

    @patch('qreader.QReader')
    def test_init_qreader_exception(self, MockQReader):
        MockQReader.side_effect = Exception("Init error")
        handler = QRHandler({})
        assert handler.qreader is None

    @patch('qreader.QReader')
    def test_detect_and_decode_gray_image(self, MockQReader):
        mock_instance = MockQReader.return_value
        mock_instance.detect_and_decode.return_value = ("AB123456781130115123400000064000000000000000012345678aabbccddeeffgghhiijjkk",)
        handler = QRHandler({})
        handler.qreader = mock_instance
        
        # 2D grayscale array
        img = np.zeros((100, 100), dtype=np.uint8)
        result = handler.detect_and_decode(img)
        assert result is not None

    @patch('qreader.QReader')
    def test_detect_and_decode_empty_text_in_list(self, MockQReader):
        mock_instance = MockQReader.return_value
        # First is empty string, second is valid
        mock_instance.detect_and_decode.return_value = ("", "AB123456781130115123400000064000000000000000012345678aabbccddeeffgghhiijjkk")
        handler = QRHandler({})
        handler.qreader = mock_instance
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = handler.detect_and_decode(img)
        assert result is not None

    @patch('qreader.QReader')
    def test_detect_and_decode_exception(self, MockQReader):
        mock_instance = MockQReader.return_value
        mock_instance.detect_and_decode.side_effect = Exception("Decode err")
        handler = QRHandler({})
        handler.qreader = mock_instance
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert handler.detect_and_decode(img) is None

    def test_parse_taiwan_einvoice_qr_invalid_invoice_number(self):
        # Starts with digits instead of letters
        qr_content = "12345678901130115123400000064000000000000000012345678"
        qr_content = qr_content.ljust(80, '0')
        assert self.handler._parse_taiwan_einvoice_qr(qr_content) is None

    def test_parse_taiwan_einvoice_qr_value_errors(self):
        """Provide invalid hex strings so ValueError is raised and defaults to 0"""
        qr_content = "AB1234567811301151234XXXXXXXXYYYYYYYY0000000012345678"
        qr_content = qr_content.ljust(80, '0')
        result = self.handler._parse_taiwan_einvoice_qr(qr_content)
        assert result is not None
        assert result["untaxed_amount"] == 0
        assert result["tax_amount"] == 0
        assert result["total"] == 0

    def test_parse_taiwan_einvoice_qr_exception(self):
        # Pass list instead of string to raise AttributeError on .isalpha() and hit Exception block
        assert self.handler._parse_taiwan_einvoice_qr([0] * 80) is None

    @patch('backend.processing.qr_handler.QRHandler.detect_and_decode')
    def test_is_electronic_invoice(self, mock_detect):
        mock_detect.return_value = {"invoice_id": "AB12345678"}
        assert self.handler.is_electronic_invoice(np.zeros((10,10,3))) is True
        
        mock_detect.return_value = None
        assert self.handler.is_electronic_invoice(np.zeros((10,10,3))) is False

    @patch('qreader.QReader')
    def test_get_qr_locations(self, MockQReader):
        mock_instance = MockQReader.return_value
        
        # Valid tuple list
        mock_instance.detect_and_decode.return_value = [
            ("text1", (10, 20, 30, 40)),
            ("text2", (50, 60, 100, 120))
        ]
        
        handler = QRHandler({})
        handler.qreader = mock_instance
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        locs = handler.get_qr_locations(img)
        assert len(locs) == 2
        
        # First loc: x1=10, y1=20, w=30-10=20, h=40-20=20
        assert locs[0] == (10, 20, 20, 20)
        assert locs[1] == (50, 60, 50, 60)

    @patch('qreader.QReader')
    def test_get_qr_locations_invalid_item(self, MockQReader):
        mock_instance = MockQReader.return_value
        # One valid item, one item without enough elements in tuple, one scalar
        mock_instance.detect_and_decode.return_value = [
            ("text1", (10, 20, 30, 40)),
            ("text2", (50, 60)), # Too few coordinates
            "not_a_tuple",
            ("text3", None)      # None bbox
        ]
        
        handler = QRHandler({})
        handler.qreader = mock_instance
        
        locs = handler.get_qr_locations(np.zeros((100,100), dtype=np.uint8))
        assert len(locs) == 1

    @patch('qreader.QReader')
    def test_get_qr_locations_empty(self, MockQReader):
        mock_instance = MockQReader.return_value
        mock_instance.detect_and_decode.return_value = []
        handler = QRHandler({})
        handler.qreader = mock_instance
        locs = handler.get_qr_locations(np.zeros((10,10,3)))
        assert locs == []

    @patch('qreader.QReader')
    def test_get_qr_locations_catch_error(self, MockQReader):
        mock_instance = MockQReader.return_value
        # Trigger ValueError / TypeError during map(int, bbox[:4])
        mock_instance.detect_and_decode.return_value = [
            ("text", ("a", "b", "c", "d"))
        ]
        handler = QRHandler({})
        handler.qreader = mock_instance
        locs = handler.get_qr_locations(np.zeros((10,10,3)))
        assert locs == []

    @patch('qreader.QReader')
    def test_get_qr_locations_exception(self, MockQReader):
        mock_instance = MockQReader.return_value
        mock_instance.detect_and_decode.side_effect = Exception("Detect err")
        
        handler = QRHandler({})
        handler.qreader = mock_instance
        
        locs = handler.get_qr_locations(np.zeros((10,10,3)))
        assert locs == []
