import os
import json
import logging

logger = logging.getLogger(__name__)

# Calculate absolute project root once
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Environment-aware config resolution
# APP_ENV = "dev"  → config.json  (default)
# APP_ENV = "prod" → config.prod.json
# ---------------------------------------------------------------------------
_ENV_CONFIG_MAP = {
    "dev":  "config.json",
    "prod": "config.prod.json",
    "test": "config.test.json",
}

def get_active_env() -> str:
    """Return the current environment name (dev / prod)."""
    return os.environ.get("APP_ENV", "dev").lower()

def _resolve_config_path() -> str:
    """Return the absolute path to the config file for the active environment."""
    env = get_active_env()
    filename = _ENV_CONFIG_MAP.get(env, "config.json")
    return os.path.join(PROJECT_ROOT, filename)

# Backward-compatible module-level constant (points to active config)
CONFIG_PATH = _resolve_config_path()

def load_config() -> dict:
    """Load configuration from the environment-specific config file.

    Resolution order:
      1. ``APP_ENV=prod`` → ``config.prod.json``
      2. ``APP_ENV=dev`` (or unset) → ``config.json``
    """
    path = _resolve_config_path()
    if not os.path.exists(path):
        logger.warning(f"Config file not found at {path}. Using empty dictionary.")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"Loaded config from {path}  (APP_ENV={get_active_env()})")
        return config
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return {}


def save_config(config: dict) -> bool:
    """Save configuration to the environment-specific config file."""
    path = _resolve_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error writing to {path}: {e}")
        return False
