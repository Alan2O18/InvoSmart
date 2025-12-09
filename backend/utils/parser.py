import json
from typing import Optional, Dict, Any

def extract_structured_data(raw_text_or_json: Optional[str]) -> Dict[str, Any]:
    """
    輸入可能是空、json string 或已序列化字串
    目標：回傳 dict，格式盡量包含：
        supplier, invoice_id, date, items (list of dict with description, quantity, price), total_amount
    支援的來源範例：
    {"corrected_full_text": "...", "structured_data": {"supplier": "...", "items":[{...}] , "total_amount": 123}}
    也支援 llm 直接回 {"supplier":..., "items":[...]}
    """
    if not raw_text_or_json:
        return {}
    parsed = None
    if isinstance(raw_text_or_json, str):
        s = raw_text_or_json.strip()
        try:
            parsed = json.loads(s)
        except Exception:
            # 不是 JSON 就回空
            return {}
    elif isinstance(raw_text_or_json, dict):
        parsed = raw_text_or_json
    else:
        return {}

    out = {}
    # 優先尋找 structured_data 欄位
    sd = parsed.get("structured_data") if isinstance(parsed, dict) else None
    if isinstance(sd, dict):
        out.update(sd)
    else:
        # 若沒有 structured_data，直接嘗試 top-level
        out.update(parsed if isinstance(parsed, dict) else {})

    # normalize items: 期望 items 為 list of dict
    items = out.get("items") or out.get("lines") or out.get("details") or []
    normalized_items = []
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                # 嘗試把數字轉成基本型別
                desc = it.get("description") or it.get("desc") or ""
                qty = it.get("quantity") or it.get("qty") or it.get("數量") or None
                price = (
                    it.get("price")
                    or it.get("amount")
                    or it.get("price_nt")
                    or None
                )
                # 嘗試轉型
                try:
                    qty = int(qty) if qty is not None and qty != "" else None
                except Exception:
                    qty = None
                try:
                    price = (
                        float(price) if price is not None and price != "" else None
                    )
                except Exception:
                    price = None
                normalized_items.append(
                    {"description": desc, "quantity": qty, "price": price}
                )
            else:
                normalized_items.append(
                    {"description": str(it), "quantity": None, "price": None}
                )
    out["items"] = normalized_items
    return out
