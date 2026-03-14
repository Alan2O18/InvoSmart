from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "voucher_template_config.json"

VOUCHER_FONT_CONFIG: dict[str, str] = {
    "family": "VoucherKaiU",
    "url": "/api/voucher/fonts/kaiu.ttf",
}

TEXT_FIELD_CONFIG: dict[str, dict[str, Any]] = {
    "voucherNo": {
        "type": "text",
        "point": [78.5, 255],
        "fontSize": 16,
        "minFontSize": 8,
        "maxWidth": 62,
        "autoScale": True,
        "lineStep": 17,
        "maxLines": 5,
        "preview": {"baselineRatio": 0.82},
    },
    "budgetItem": {
        "type": "text",
        "point": [149, 270],
        "fontSize": 18,
        "minFontSize": 14,
        "maxWidth": 65,
        "autoScale": True,
        "maxChars": 3,
        "preview": {"baselineRatio": 0.82},
    },
    "amount": {
        "type": "amount_cells",
        "y": 270,
        "xList": [208, 228, 250.5, 271.5, 291, 312],
        "fontSize": 16,
        "padLength": 6,
        "padChar": "※",
        "digitPolicy": 6,
        "legacyMaxDigits": 7,
        "preview": {"baselineRatio": 0.82},
    },
    "purpose": {
        "type": "textbox",
        "rect": [333, 240, 523, 328],
        "fontSize": 18,
        "minFontSize": 10,
        "lineHeight": 1.2,
        "truncateAt": 80,
        "truncateSuffix": "...(略)",
    },
    "receiptCount": {
        "type": "text",
        "point": [473.5, 105],
        "fontSize": 16,
        "preview": {"baselineRatio": 0.82},
    },
    "payDate": {
        "type": "text",
        "point": [205, 785],
        "fontSize": 20,
        "preview": {"baselineRatio": 0.82},
    },
    "paymentAmount": {
        "type": "text",
        "point": [314, 785],
        "fontSize": 20,
        "preview": {"baselineRatio": 0.82},
    }
}


DEFAULT_SAFE_ZONE: dict[str, float] = {"x0": 30, "y0": 394, "x1": 565, "y1": 730}

DEFAULT_BLOCKED_ZONES: list[dict[str, Any]] = [
    {
        "key": "stamp_top",
        "rect": [428, 392, 135, 56],
        "label": "蓋章區",
        "visible": True,
    }
]

DEFAULT_PREVIEW_CONFIG: dict[str, bool] = {
    "showSafeZone": True,
    "showBlockedZones": True,
}


def _build_defaults() -> dict[str, Any]:
    return {
        "version": "0.0.9",
        "font": dict(VOUCHER_FONT_CONFIG),
        "textFields": deepcopy(TEXT_FIELD_CONFIG),
        "safeZone": deepcopy(DEFAULT_SAFE_ZONE),
        "blockedZones": deepcopy(DEFAULT_BLOCKED_ZONES),
        "preview": deepcopy(DEFAULT_PREVIEW_CONFIG),
    }


def get_full_template_layout() -> dict[str, Any]:
    """Load template layout from JSON config, falling back to hardcoded defaults."""
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                custom = json.load(f)
            logger.info("使用自訂座標配置: %s", _CONFIG_PATH)
            defaults = _build_defaults()
            defaults.update(custom)
            return defaults
        except Exception as exc:  # noqa: BLE001
            logger.warning("讀取配置檔失敗，使用預設值: %s", exc)
    return _build_defaults()


def get_text_field_config() -> dict[str, dict[str, Any]]:
    return get_full_template_layout()["textFields"]


def get_voucher_text_config_payload() -> dict[str, Any]:
    layout = get_full_template_layout()
    return {
        "version": layout.get("version", "0.0.9"),
        "font": layout["font"],
        "fields": layout["textFields"],
        "safeZone": layout["safeZone"],
        "blockedZones": layout["blockedZones"],
        "preview": layout.get("preview", deepcopy(DEFAULT_PREVIEW_CONFIG)),
    }


