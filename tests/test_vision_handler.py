"""
Unit Tests for VisionHandler (OpenAI Compatible)

Tests initialization, config, JSON cleaning, and API call mocking.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
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
        
        with patch.dict(os.environ, {}, clear=True):
            config = {"vision_settings": {}}
            handler = VisionHandler(config)
            
            assert handler.model_name == "gemini-2.5-flash-lite"
            assert handler._client is None

    def test_init_with_config(self):
        """Test initialization with custom config."""
        from backend.processing.vision_handler import VisionHandler
        
        with patch.dict(os.environ, {}, clear=True):
            config = {
                "vision_settings": {
                    "model_name": "custom-model",
                    "temperature": 0.5,
                    "reasoning_effort": "high",
                    "max_retries": 5,
                    "base_url": "https://openrouter.ai/api/v1"
                }
            }
            handler = VisionHandler(config)
            
            assert handler.model_name == "custom-model"
            assert handler.temperature == 0.5
            assert handler.reasoning_effort == "high"
            assert handler.max_retries == 5
            assert handler.base_url == "https://openrouter.ai/api/v1"

    def test_clean_json_response(self):
        """Test JSON response cleaning."""
        from backend.processing.vision_handler import VisionHandler
        
        with patch.dict(os.environ, {}, clear=True):
            handler = VisionHandler({"vision_settings": {}})
            
            assert handler._clean_json_response('```json\n{"key": "value"}\n```') == '{"key": "value"}'
            assert handler._clean_json_response('```\n{"key": "value"}\n```') == '{"key": "value"}'
            assert handler._clean_json_response('{"key": "value"}') == '{"key": "value"}'

    def test_prepare_image_b64(self):
        """Test image encoding to base64."""
        from backend.processing.vision_handler import VisionHandler
        
        with patch.dict(os.environ, {}, clear=True):
            handler = VisionHandler({"vision_settings": {}})
            
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            result = handler._prepare_image_b64(img)
            
            assert result.startswith("data:image/jpeg;base64,")
            assert len(result) > 50

    @patch("backend.processing.vision_handler.OpenAI")
    def test_process_image_success(self, mock_openai_cls):
        """Test successful process_image with mocked OpenAI client."""
        from backend.processing.vision_handler import VisionHandler
        
        # Setup mock
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"receipt_type": "電子發票", "header": {"supplier": "測試店"}}'
        mock_response.model = "gemini-2.5-flash-lite"
        mock_response.usage = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        
        config = {"vision_settings": {"api_key": "test-key"}}
        handler = VisionHandler(config)
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result, stats = handler.process_image(img)
        
        assert result["receipt_type"] == "電子發票"
        assert stats["processor"] == "VLM-OpenAI"
        mock_client.chat.completions.create.assert_called_once()

    @patch("backend.processing.vision_handler.OpenAI")
    def test_process_image_retry(self, mock_openai_cls):
        """Test that API retries work correctly."""
        from backend.processing.vision_handler import VisionHandler
        
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"receipt_type": "test"}'
        mock_response.model = "test"
        mock_response.usage = MagicMock()
        
        mock_client.chat.completions.create.side_effect = [
            ConnectionError("timeout"),
            mock_response
        ]
        
        config = {"vision_settings": {"api_key": "test-key", "max_retries": 3}}
        handler = VisionHandler(config)
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("time.sleep"):  # Skip actual sleep
            result, stats = handler.process_image(img)
        
        assert result["receipt_type"] == "test"
        assert mock_client.chat.completions.create.call_count == 2

    @patch("backend.processing.vision_handler.OpenAI")
    def test_process_image_all_retries_fail(self, mock_openai_cls):
        """Test that all retries exhausted returns error."""
        from backend.processing.vision_handler import VisionHandler
        
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = ConnectionError("fail")
        
        config = {"vision_settings": {"api_key": "test-key", "max_retries": 2}}
        handler = VisionHandler(config)
        
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("time.sleep"):
            result, stats = handler.process_image(img)
        
        assert result == {}
        assert "error" in stats
