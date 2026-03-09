from __future__ import annotations

from copy import deepcopy
from typing import Any

VOUCHER_FONT_CONFIG: dict[str, str] = {
    "family": "VoucherKaiU",
    "url": "/api/voucher/fonts/kaiu.ttf",
}

TEXT_FIELD_CONFIG: dict[str, dict[str, Any]] = {
    "voucherNo": {
        "type": "text",
        "point": [78.5, 255],
        "fontSize": 16,
        "lineStep": 20,
        "preview": {"baselineRatio": 0.82},
    },
    "budgetItem": {
        "type": "text",
        "point": [149, 270],
        "fontSize": 18,
        "maxChars": 3,
        "preview": {"baselineRatio": 0.82},
    },
    "amount": {
        "type": "amount_cells",
        "y": 270,
        "xList": [188, 208, 228, 250.5, 271.5, 291, 312], # First index = 188 to support 7th digit (millions)
        "fontSize": 16,
        "padLength": 7,
        "padChar": "※",
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

def get_text_field_config() -> dict[str, dict[str, Any]]:
    return deepcopy(TEXT_FIELD_CONFIG)

def get_voucher_text_config_payload() -> dict[str, Any]:
    return {
        "version": "0.0.6",
        "font": dict(VOUCHER_FONT_CONFIG),
        "fields": get_text_field_config(),
    }


