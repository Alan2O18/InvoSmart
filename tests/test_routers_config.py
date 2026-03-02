import pytest
from unittest.mock import patch, mock_open

def test_get_config(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.config = {"vision_settings": {"api_key": "1234567890"}}
    response = mock_app_client.get("/api/config/")
    assert response.status_code == 200
    assert response.json()["vision_settings"]["api_key"] == "1234***7890"

def test_get_config_short_key(mock_app_client, mock_engine_for_api):
    mock_engine_for_api.config = {"vision_settings": {"api_key": "123"}}
    response = mock_app_client.get("/api/config/")
    assert response.status_code == 200
    assert response.json()["vision_settings"]["api_key"] == "***"

@patch('backend.routers.config.load_config', return_value={"vision_settings": {"api_key": "old_key"}})
@patch('backend.routers.config.save_config')
def test_update_config(mock_save, mock_load, mock_app_client, mock_engine_for_api):
    response = mock_app_client.post("/api/config/", json={"vision_settings": {"api_key": "123***890", "model": "gemini"}})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify the Engine runtime was updated
    mock_engine_for_api.update_config.assert_called_once()
    args = mock_engine_for_api.update_config.call_args[0][0]
    # Should retain the old key because of the mask, but update other fields
    assert args["vision_settings"]["api_key"] == "old_key"
    assert args["vision_settings"]["model"] == "gemini"
