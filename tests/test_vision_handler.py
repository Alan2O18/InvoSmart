"""
Unit Tests for VisionHandler (Gemini 2.5)

Tests basic initialization and configuration.
Complex API mocking is skipped due to google-genai SDK internals.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
import numpy as np

# Ensure project root is in path
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestVisionHandler:
    """VisionHandler Tests"""

    def test_import(self):
        """Test that VisionHandler can be imported."""
        from backend.processing.vision_handler import VisionHandler
        assert VisionHandler is not None

    def test_init_without_api_key(self):
        """Test initialization without API key logs warning but doesn't crash."""
        from backend.processing.vision_handler import VisionHandler
        
        # Temporarily remove API key from environment
        with patch.dict(os.environ, {}, clear=True):
            config = {"vision_settings": {}}
            handler = VisionHandler(config)
            
            assert handler.model_name == "gemini-2.5-flash-lite"
            assert handler._client is None  # No client without API key

    def test_init_with_config(self):
        """Test initialization with custom config."""
        from backend.processing.vision_handler import VisionHandler
        
        with patch.dict(os.environ, {}, clear=True):
            config = {
                "vision_settings": {
                    "model_name": "custom-model",
                    "temperature": 0.5,
                    "think_mode": True,
                    "max_retries": 5
                }
            }
            handler = VisionHandler(config)
            
            assert handler.model_name == "custom-model"
            assert handler.temperature == 0.5
            assert handler.think_mode is True
            assert handler.max_retries == 5

    def test_clean_json_response(self):
        """Test JSON response cleaning."""
        from backend.processing.vision_handler import VisionHandler
        
        with patch.dict(os.environ, {}, clear=True):
            handler = VisionHandler({"vision_settings": {}})
            
            # Test markdown code fence removal
            assert handler._clean_json_response('```json\n{"key": "value"}\n```') == '{"key": "value"}'
            assert handler._clean_json_response('```\n{"key": "value"}\n```') == '{"key": "value"}'
            assert handler._clean_json_response('{"key": "value"}') == '{"key": "value"}'

    @pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY"),
        reason="Requires GOOGLE_API_KEY for integration test"
    )
    def test_process_handwritten_integration(self):
        """Integration test with real API (skipped without API key)."""
        from backend.processing.vision_handler import VisionHandler
        import cv2
        
        config = {"vision_settings": {"think_mode": True}}
        handler = VisionHandler(config)
        
        # Create a simple test image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.putText(img, "Test", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        result, stats = handler.process_handwritten(img)
        
        assert "processor" in stats
        assert stats["processor"] == "Gemini-2.5"
