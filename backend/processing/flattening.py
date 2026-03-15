import time
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _coerce_amount(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def build_job_flatten_payload(
    result: dict[str, Any],
    *,
    project_group: str = "",
    source: str = "unknown",
    job_id: str = "",
) -> dict[str, Any]:
    header = _as_dict(result.get("header"))
    summary = _as_dict(result.get("summary"))
    items = _as_list(result.get("items"))

    voucher_id = str(header.get("voucher_id") or summary.get("voucher_id") or "")
    purpose = str(summary.get("purpose") or header.get("purpose") or "")

    flattened_items: list[dict[str, Any]] = []
    categories: list[str] = []
    seen_categories: set[str] = set()
    sum_total = 0.0

    for item in items:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "未分類")
        if category not in seen_categories:
            categories.append(category)
            seen_categories.add(category)

        normalized = {
            "job_id": job_id,
            "project_group": project_group,
            "voucher_id": voucher_id,
            "category": category,
            "name": item.get("name") or item.get("description", ""),
            "qty": item.get("qty") or item.get("quantity", ""),
            "price": item.get("price", ""),
            "total": item.get("total", ""),
            "purpose": purpose,
        }
        flattened_items.append(normalized)
        sum_total += _coerce_amount(normalized.get("total"))

    return {
        "version": 1,
        "generatedAt": time.time(),
        "jobId": job_id,
        "source": source,
        "projectGroup": project_group,
        "header": header,
        "summary": summary,
        "categories": categories,
        "items": flattened_items,
        "sumTotal": int(sum_total),
    }


def aggregate_flattened_jobs(
    job_payloads: list[dict[str, Any]],
    *,
    source_signature: str,
) -> dict[str, Any]:
    grouped_items: dict[str, list[dict[str, Any]]] = {}
    categories: list[str] = []
    all_flattened_items: list[dict[str, Any]] = []
    sum_total = 0.0

    for payload in job_payloads:
        for category in payload.get("categories", []):
            if category not in grouped_items:
                grouped_items[category] = []
                categories.append(category)

        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "未分類")
            grouped_items.setdefault(category, []).append(item)
            copied = dict(item)
            copied["_category"] = category
            all_flattened_items.append(copied)
            sum_total += _coerce_amount(item.get("total"))

    return {
        "version": 1,
        "generatedAt": time.time(),
        "sourceSignature": source_signature,
        "groupedItems": grouped_items,
        "categories": categories,
        "allFlattenedItems": all_flattened_items,
        "sumTotal": int(sum_total),
    }