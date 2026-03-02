# Config Router - 設定管理端點
import logging
import json
import os
from fastapi import APIRouter, HTTPException, Body, Depends
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()

from backend.utils.config import load_config, save_config

@router.get("/")
def get_config(engine: Engine = Depends(get_engine)):
    """Get current configuration (masked API keys)."""
    config = engine.config.copy()
    
    # Mask API Key for security
    if "vision_settings" in config:
        settings = config["vision_settings"]
        if settings.get("api_key"):
            settings = settings.copy()
            key = settings["api_key"]
            if len(key) > 8:
                settings["api_key"] = key[:4] + "***" + key[-4:]
            else:
                settings["api_key"] = "***"
            config["vision_settings"] = settings
            
    return config

@router.post("/")
def update_config(
    new_settings: dict = Body(...),
    engine: Engine = Depends(get_engine)
):
    """
    Update configuration and save to file.
    Only updates 'vision_settings' logic for now.
    """
    try:
        # 1. Load existing config from file to ensure we don't lose other settings
        current_config = load_config()
        
        # 2. Merge updates
        # 我們假設前端傳來的是部分更新，主要針對 vision_settings
        if "vision_settings" in new_settings:
            # 如果前端傳來的 API key 是 masked 的 (含有 ***)，則保留舊的 key
            incoming_vision = new_settings["vision_settings"]
            existing_vision = current_config.get("vision_settings", {})
            
            incoming_key = incoming_vision.get("api_key")
            if incoming_key and "***" in incoming_key:
                # 保留舊 Key
                incoming_vision["api_key"] = existing_vision.get("api_key")
            
            # 更新 vision_settings
            current_config["vision_settings"] = {**existing_vision, **incoming_vision}
            
        # 也可以支援其他 section 的更新...
        
        # 3. Save to file
        success = save_config(current_config)
        if not success:
             logger.warning("Failed to save config to disk, but runtime config will be updated.")
            
        # 4. Update Engine (Runtime)
        engine.update_config(current_config)
        
        return {"status": "success", "message": "Configuration updated and reloaded"}
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
