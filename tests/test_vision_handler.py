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

    @patch("openai.OpenAI")
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

    @patch("openai.OpenAI")
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

    @patch("openai.OpenAI")
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

    # ============================================================================
    # Additional Branch Coverage Tests
    # ============================================================================

    def test_update_config(self):
        """Test updating configuration triggers client re-init correctly."""
        from backend.processing.vision_handler import VisionHandler
        with patch.dict(os.environ, {}, clear=True):
            handler = VisionHandler({"vision_settings": {"api_key": "old-key"}})
            assert handler.api_key == "old-key"
            
            with patch.object(handler, '_init_client') as mock_init:
                handler.update_config({"vision_settings": {"api_key": "new-key", "base_url": "http://new"}})
                assert handler.api_key == "new-key"
                assert handler.base_url == "http://new"
                mock_init.assert_called_once()
                
            # Update config without API key removes client
            handler.update_config({"vision_settings": {}})
            assert handler.api_key is None
            assert handler._client is None

    def test_init_client_exception(self):
        """Test exception inside client initialization."""
        from backend.processing.vision_handler import VisionHandler
        with patch.dict(os.environ, {}, clear=True):
            with patch("openai.OpenAI", side_effect=Exception("Init Failed")):
                handler = VisionHandler({"vision_settings": {"api_key": "key"}})
                assert handler._client is None

    def test_prepare_image_b64_exception(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {}})
        
        with patch("cv2.imencode", return_value=(False, None)):
            with pytest.raises(ValueError, match="圖片編碼失敗"):
                handler._prepare_image_b64(np.zeros((10, 10, 3), dtype=np.uint8))

    def test_process_handwritten_success(self):
        from backend.processing.vision_handler import VisionHandler
        with patch.dict(os.environ, {}, clear=True):
            handler = VisionHandler({"vision_settings": {"api_key": "test"}})
            handler._client = MagicMock()
            
            with patch.object(handler, '_call_with_retry', return_value='{"status": "ok"}'):
                res_text, stats = handler.process_handwritten(np.zeros((10,10,3), dtype=np.uint8), "Context")
                assert "ok" in res_text
                assert stats["stage"] == "primary"

    def test_process_handwritten_no_client(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {}})
        assert getattr(handler, '_client', None) is None
        res, stats = handler.process_handwritten(np.zeros((10,10,3), dtype=np.uint8))
        assert res == ""
        assert "error" in stats

    def test_process_handwritten_exception(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {"api_key": "test"}})
        handler._client = MagicMock()
        with patch.object(handler, '_prepare_image_b64', side_effect=Exception("Prep Error")):
            res, stats = handler.process_handwritten(np.zeros((10,10,3), dtype=np.uint8))
            assert res == ""
            assert stats["error"] == "Prep Error"

    def test_image_to_markdown(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {}})
        with patch.object(handler, 'process_image', return_value=({}, {})) as mock_proc:
            handler.image_to_markdown(np.zeros((10,10,3), dtype=np.uint8))
            mock_proc.assert_called_once()

    def test_process_image_no_client(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {}})
        res, stats = handler.process_image(np.zeros((10,10,3), dtype=np.uint8))
        assert res == {}
        assert "error" in stats

    def test_process_image_json_decode_error(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {"api_key": "test"}})
        handler._client = MagicMock()
        
        with patch.object(handler, '_call_with_retry', return_value='{"incomplete":'):
            res, stats = handler.process_image(np.zeros((10,10,3), dtype=np.uint8))
            assert "raw_text" in res
            assert "incomplete" in res["raw_text"]

    def test_repair_json_heuristics(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {}})
        
        # Test 1: trailing comma at the absolute end
        assert handler._repair_json('[1, 2,') == '[1, 2]'
        
        # Test 2: Incomplete array missing bracket
        assert handler._repair_json('{"values": [1, 2') == '{"values": [1, 2]}'
        
        # Test 3: Instring completion
        assert handler._repair_json('{"key": "value') == '{"key": "value"}'
        
        # Test 4: Escape character inside string
        assert handler._repair_json('{"key": "val\\"ue') == '{"key": "val\\"ue"}'
        
        # Test 5: Broken complex JSON
        assert handler._repair_json('[{"a": {"b": 1}') == '[{"a": {"b": 1}}]'

    def test_describe_image_success(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {"api_key": "test"}})
        handler._client = MagicMock()
        
        with patch.object(handler, '_call_with_retry', return_value="A description"):
            res, stats = handler.describe_image(np.zeros((10,10,3), dtype=np.uint8))
            assert res == "A description"

    def test_describe_image_no_client(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {}})
        res, stats = handler.describe_image(np.zeros((10,10,3), dtype=np.uint8))
        assert res == ""
        assert "error" in stats

    def test_describe_image_exception(self):
        from backend.processing.vision_handler import VisionHandler
        handler = VisionHandler({"vision_settings": {"api_key": "test"}})
        handler._client = MagicMock()
        with patch.object(handler, '_prepare_image_b64', side_effect=Exception("Prep Error")):
            res, stats = handler.describe_image(np.zeros((10,10,3), dtype=np.uint8))
            assert res == ""
            assert stats["error"] == "Prep Error"

    @patch("openai.OpenAI")
    def test_call_with_retry_no_text(self, mock_openai_cls):
        from backend.processing.vision_handler import VisionHandler
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        # message.content is empty/None
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response
        
        handler = VisionHandler({"vision_settings": {"api_key": "test", "max_retries": 1}})
        with pytest.raises(ValueError, match="回應中找不到文字內容"):
            handler._call_with_retry("prompt", "data:image/jpeg;base64,123")

    @patch("openai.OpenAI")
    def test_call_with_retry_with_reasoning(self, mock_openai_cls):
        from backend.processing.vision_handler import VisionHandler
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "result"
        # Mock reasoning_content attribute
        mock_response.choices[0].message.reasoning_content = "thinking"
        mock_client.chat.completions.create.return_value = mock_response
        
        handler = VisionHandler({"vision_settings": {"api_key": "test"}})
        res = handler._call_with_retry("prompt", "data:image/jpeg;base64,123")
        assert res == "result"
