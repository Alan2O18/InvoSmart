from backend.processing.flattening import (
    _category_sort_key,
    aggregate_flattened_jobs,
    build_export_payload_from_db,
    build_job_flatten_payload,
)


def test_category_sort_key_uses_default_for_unknown_category():
    weight, category = _category_sort_key("未知類別")
    assert weight == 999
    assert category == "未知類別"


def test_build_job_flatten_payload_normalizes_items_and_totals():
    payload = build_job_flatten_payload(
        {
            "header": {"voucher_id": "V100"},
            "summary": {"purpose": "茶水", "total": "30"},
            "items": [
                {"category": "茶水", "description": "礦泉水", "quantity": 3, "price": 10, "total": "30"},
                "not-a-dict",
            ],
        },
        project_group="活動組",
        source="manual",
        job_id="job-1",
    )

    assert payload["jobId"] == "job-1"
    assert payload["source"] == "manual"
    assert payload["projectGroup"] == "活動組"
    assert payload["categories"] == ["茶水"]
    assert payload["sumTotal"] == 30
    assert payload["items"][0]["name"] == "礦泉水"
    assert payload["items"][0]["qty"] == 3


def test_aggregate_flattened_jobs_sorts_by_category_weight_then_fields():
    payload = aggregate_flattened_jobs(
        [
            {
                "items": [
                    {"category": "其他", "voucher_id": "B-2", "name": "item-b", "total": 20},
                    {"category": "保險", "voucher_id": "A-1", "name": "item-a", "total": 10},
                ]
            }
        ],
        source_signature="sig-1",
    )

    assert payload["sourceSignature"] == "sig-1"
    assert payload["sumTotal"] == 30
    assert payload["categories"][0] == "保險"
    assert payload["allFlattenedItems"][0]["_category"] == "保險"


def test_build_export_payload_from_db_uses_quantity_fallback_and_description_name():
    jobs = [
        {
            "job_id": "j1",
            "voucher_id": "VX-1",
            "supplier": "供應商A",
            "invoice_date": "2026-04-24",
            "purpose": "用品",
            "total_amount": 120,
            "project_group": "教材費",
        },
        {
            "job_id": "j2",
            "voucher_id": "VX-2",
            "supplier": "供應商B",
            "invoice_date": "2026-04-23",
            "purpose": "保險",
            "total_amount": 40,
            "project_group": "教材費",
        },
    ]
    items_by_job_id = {
        "j1": [
            {"category": "餐食", "description": "餐盒", "quantity": 2, "price": 50, "total": 100},
            {"category": "茶水", "name": "礦泉水", "qty": 2, "price": 10, "total": 20},
        ],
        "j2": [
            {"category": "保險", "description": "團保", "quantity": 1, "price": 40, "total": 40},
        ],
    }

    payload = build_export_payload_from_db(jobs, items_by_job_id, source_signature="db-sig")

    assert payload["sourceSignature"] == "db-sig"
    assert payload["sumTotal"] == 160
    assert payload["categories"][0] == "保險"

    flattened = payload["allFlattenedItems"]
    names = {item["name"] for item in flattened}
    assert "餐盒" in names
    assert "礦泉水" in names
    assert "團保" in names
