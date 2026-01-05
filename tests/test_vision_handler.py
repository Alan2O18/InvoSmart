"""
Unit Tests for VisionHandler

Tests image encoding, VLM processing, and response parsing using mocks.
"""
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
from backend.processing.vision_handler import VisionHandler

class TestVisionHandler:
    """VisionHandler Tests with Mocks"""

    @pytest.fixture
    def mock_ollama(self):
        """Mock the ollama library."""
        with patch('backend.processing.vision_handler.ollama') as MockOllama:
            yield MockOllama

    def setup_method(self):
        self.handler = VisionHandler({})

    def test_encode_image_to_base64(self):
        """Test encoding numpy image to base64."""
        # Create a tiny 1x1 black image
        img = np.zeros((1, 1, 3), dtype=np.uint8)
        
        b64 = self.handler._encode_image(img)
        
        assert isinstance(b64, str)
        assert len(b64) > 0
        # Basic base64 validation
        import base64
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

    def test_process_handwritten_returns_tuple(self, mock_ollama):
        """Test process_handwritten returns (text, stats)."""
        # Mock streaming response
        mock_chunk = {
            'message': {'content': '{"key": "value"}'},
            'done': True,
            'eval_count': 10,
            'eval_duration': 1000000000,
            'prompt_eval_count': 5,
            'prompt_eval_duration': 100000000
        }
        mock_ollama.chat.return_value = [mock_chunk]
        
        # Ensure streaming is on (default)
        self.handler.use_streaming = True
        
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        result_text, stats = self.handler.process_handwritten(img)
        
        assert result_text == '{"key": "value"}'
        assert stats["model"] == "qwen3-vl:2b"

    def test_process_handwritten_empty_response(self, mock_ollama):
        """Test handling of empty response from Ollama."""
        mock_ollama.chat.return_value = []
        
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        result_text, stats = self.handler.process_handwritten(img)
        
        assert result_text == ""
        assert "error" not in stats # Should be empty stats or partial

    def test_describe_image_custom_prompt(self, mock_ollama):
        """Test describe_image with custom prompt."""
        # Using streaming by default
        mock_chunk = {'message': {'content': 'Description'}, 'done': True}
        mock_ollama.chat.return_value = [mock_chunk]
        
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        prompt = "Describe this."
        
        text, stats = self.handler.describe_image(img, custom_prompt=prompt)
        
        assert text == "Description"
        
        # Verify call arguments
        # chat(model=..., messages=[...], ...)
        call_args = mock_ollama.chat.call_args[1]
        messages = call_args["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == prompt
        assert len(messages[0]["images"]) == 1

    def test_image_to_markdown_calls_process_handwritten(self, mock_ollama):
        """Test that image_to_markdown is just an alias or similar workflow."""
        mock_chunk = {'message': {'content': '# Markdown'}, 'done': True}
        mock_ollama.chat.return_value = [mock_chunk]
        
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        
        if hasattr(self.handler, 'image_to_markdown'):
            text, stats = self.handler.image_to_markdown(img)
            assert text == "# Markdown"
