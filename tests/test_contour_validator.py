import pytest
import numpy as np
from backend.processing.contour_validator import ContourValidator


class TestContourValidator:
    """Test ContourValidator class."""
    
    def test_init_default_aspect_ratio(self):
        """Test default aspect ratio range initialization."""
        validator = ContourValidator()
        assert validator.aspect_ratio_range == (0.1, 0.9)
    
    def test_init_custom_aspect_ratio(self):
        """Test custom aspect ratio range initialization."""
        validator = ContourValidator(aspect_ratio_range=(0.3, 0.7))
        assert validator.aspect_ratio_range == (0.3, 0.7)
    
    def test_order_points_standard_rectangle(self):
        """Test ordering points for a standard rectangle."""
        validator = ContourValidator()
        # Points: TL, BR, BL, TR (unordered)
        pts = np.array([[10, 10], [90, 90], [10, 90], [90, 10]], dtype="float")
        ordered = validator.order_points(pts)
        
        # Expected: TL, TR, BR, BL
        assert np.allclose(ordered[0], [10, 10])  # TL
        assert np.allclose(ordered[1], [90, 10])  # TR
        assert np.allclose(ordered[2], [90, 90])  # BR
        assert np.allclose(ordered[3], [10, 90])  # BL
        assert ordered.dtype == np.float32
    
    def test_order_points_rotated(self):
        """Test ordering points for a rotated rectangle."""
        validator = ContourValidator()
        # Rotated points
        pts = np.array([[50, 20], [80, 50], [50, 80], [20, 50]], dtype="float")
        ordered = validator.order_points(pts)
        
        # Should still establish TL->TR->BR->BL ordering by y then x
        assert ordered.shape == (4, 2)
        assert ordered.dtype == np.float32
        # First point should be top-most (or among top two)
        # Last two points should have higher y values than first two
        top_y_avg = (ordered[0][1] + ordered[1][1]) / 2
        bottom_y_avg = (ordered[2][1] + ordered[3][1]) / 2
        assert top_y_avg < bottom_y_avg
    
    def test_validate_aspect_ratio_valid(self):
        """Test aspect ratio validation with valid rectangle."""
        validator = ContourValidator(aspect_ratio_range=(0.5, 0.8))
        # 100x200 -> aspect = 100/200 = 0.5
        assert validator.validate_aspect_ratio((100, 200)) is True
        # 80x100 -> aspect = 80/100 = 0.8
        assert validator.validate_aspect_ratio((80, 100)) is True
        # 70x100 -> aspect = 70/100 = 0.7
        assert validator.validate_aspect_ratio((70, 100)) is True
    
    def test_validate_aspect_ratio_invalid(self):
        """Test aspect ratio validation with invalid rectangle."""
        validator = ContourValidator(aspect_ratio_range=(0.5, 0.8))
        # 40x100 -> aspect = 40/100 = 0.4 (too narrow)
        assert validator.validate_aspect_ratio((40, 100)) is False
        # 90x100 -> aspect = 90/100 = 0.9 (too wide)
        assert validator.validate_aspect_ratio((90, 100)) is False
    
    def test_validate_aspect_ratio_zero_width(self):
        """Test aspect ratio validation with zero width."""
        validator = ContourValidator()
        assert validator.validate_aspect_ratio((0, 100)) is False
    
    def test_validate_aspect_ratio_zero_height(self):
        """Test aspect ratio validation with zero height."""
        validator = ContourValidator()
        assert validator.validate_aspect_ratio((100, 0)) is False
    
    def test_validate_aspect_ratio_negative_dimensions(self):
        """Test aspect ratio validation with negative dimensions."""
        validator = ContourValidator()
        assert validator.validate_aspect_ratio((-100, 200)) is False
        assert validator.validate_aspect_ratio((100, -200)) is False
        assert validator.validate_aspect_ratio((-100, -200)) is False
    
    def test_validate_aspect_ratio_rotation_invariant(self):
        """Test that aspect ratio is rotation-invariant."""
        validator = ContourValidator(aspect_ratio_range=(0.5, 0.8))
        # Landscape orientation
        assert validator.validate_aspect_ratio((200, 100)) is True
        # Portrait orientation (same aspect ratio)
        assert validator.validate_aspect_ratio((100, 200)) is True
    
    def test_validate_aspect_ratio_exact_bounds(self):
        """Test aspect ratio validation at exact boundary values."""
        validator = ContourValidator(aspect_ratio_range=(0.5, 0.8))
        # Exactly at lower bound
        assert validator.validate_aspect_ratio((50, 100)) is True
        # Exactly at upper bound
        assert validator.validate_aspect_ratio((80, 100)) is True
        # Just below lower bound
        assert validator.validate_aspect_ratio((49, 100)) is False
        # Just above upper bound
        assert validator.validate_aspect_ratio((81, 100)) is False
