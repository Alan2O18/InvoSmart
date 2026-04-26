import time
from typing import Any


CATEGORY_SORT_WEIGHTS: dict[str, int] = {
    "保險": 0,
    "膳食(課程會)": 1,
    "餐食": 2,
    "茶水": 3,
    "消耗性教材": 4,
}


def _category_sort_key(category: Any) -> tuple[int, str]:
    category_text = str(category or "未分類")
    return CATEGORY_SORT_WEIGHTS.get(category_text, 999), category_text


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
    all_flattened_items: list[dict[str, Any]] = []
    sum_total = 0.0

    for payload in job_payloads:
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "未分類")
            copied = dict(item)
            copied["_category"] = category
            all_flattened_items.append(copied)
            sum_total += _coerce_amount(item.get("total"))

    all_flattened_items.sort(
        key=lambda item: (
            *_category_sort_key(item.get("_category")),
            str(item.get("voucher_id") or ""),
            str(item.get("name") or ""),
        )
    )

    grouped_items: dict[str, list[dict[str, Any]]] = {}
    categories: list[str] = []
    for item in all_flattened_items:
        category = str(item.get("_category") or "未分類")
        if category not in grouped_items:
            grouped_items[category] = []
            categories.append(category)
        grouped_items[category].append(item)

    return {
        "version": 1,
        "generatedAt": time.time(),
        "sourceSignature": source_signature,
        "groupedItems": grouped_items,
        "categories": categories,
        "allFlattenedItems": all_flattened_items,
        "sumTotal": int(sum_total),
    }


def build_export_payload_from_db(
    job_dicts: list[dict[str, Any]],
    items_by_job_id: dict[str, list[dict[str, Any]]],
    *,
    source_signature: str = "db_export",
) -> dict[str, Any]:
    """Build aggregated flatten payload from DB-native job/item structures."""
    job_payloads: list[dict[str, Any]] = []

    for job in job_dicts:
        if not isinstance(job, dict):
            continue

        job_id = str(job.get("job_id") or "")
        header = {
            "voucher_id": job.get("voucher_id") or "",
            "supplier": job.get("supplier") or "",
            "date": job.get("invoice_date") or "",
        }
        summary = {
            "purpose": job.get("purpose") or "",
            "total": job.get("total_amount") if job.get("total_amount") is not None else "",
        }

        normalized_items: list[dict[str, Any]] = []
        for item in items_by_job_id.get(job_id, []):
            if not isinstance(item, dict):
                continue
            qty = item.get("quantity")
            if qty in (None, ""):
                qty = item.get("qty", "")

            normalized_items.append(
                {
                    "category": item.get("category") or "未分類",
                    "name": item.get("name") or item.get("description") or "",
                    "qty": qty,
                    "price": item.get("price", ""),
                    "total": item.get("total", ""),
                }
            )

        payload = build_job_flatten_payload(
            {
                "header": header,
                "summary": summary,
                "items": normalized_items,
            },
            project_group=str(job.get("project_group") or ""),
            source="db",
            job_id=job_id,
        )
        job_payloads.append(payload)

    return aggregate_flattened_jobs(job_payloads, source_signature=source_signature)