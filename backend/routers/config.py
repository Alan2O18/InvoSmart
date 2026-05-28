# Config Router - 設定管理端點
import logging
import os

from fastapi import APIRouter, HTTPException, Body, Depends

from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.utils.config import load_config, save_config

logger = logging.getLogger(__name__)
router = APIRouter()


def _guess_provider(base_url: str) -> str:
    base = (base_url or "").lower()
    if "generativelanguage.googleapis.com" in base or "gemini" in base:
        return "google"
    if "openrouter.ai" in base:
        return "openrouter"
    if "deepseek.com" in base:
        return "deepseek"
    if "api.openai.com" in base:
        return "openai"
    return "openai_compatible"


@router.get("/vision-models")
def list_vision_models(engine: Engine = Depends(get_engine)):
    """Fetch available model ids from the configured OpenAI-compatible provider."""
    try:
        vision = (engine.config or {}).get("vision_settings", {})
        api_key = (vision.get("api_key") or os.environ.get("GOOGLE_API_KEY") or "").strip()
        base_url = (vision.get("base_url") or "https://api.openai.com/v1").strip()

        if not api_key:
            raise HTTPException(status_code=400, detail="Missing vision API key")

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=20.0)
        models = client.models.list()
        model_ids = sorted({m.id for m in (models.data or []) if getattr(m, "id", None)})

        # Lightweight heuristic to bubble up image-capable models first.
        vision_first = [
            model_id for model_id in model_ids
            if any(tag in model_id.lower() for tag in ("vision", "gemini", "gpt-4", "gpt-4o", "claude", "vlm"))
        ]
        fallback = [model_id for model_id in model_ids if model_id not in vision_first]

        return {
            "provider": _guess_provider(base_url),
            "base_url": base_url,
            "models": vision_first + fallback,
            "count": len(model_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching provider models: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch provider models: {e}")


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
