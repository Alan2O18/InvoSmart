import json

import pytest
import pytest_asyncio

from backend.database.models import Project
from backend.repositories.job_repository import JobRepository


@pytest_asyncio.fixture
async def repo(async_session_factory):
    async with async_session_factory() as session:
        session.add(Project(project_id="proj_v18", meta_data={"group": "教材費"}))
        await session.commit()

    return JobRepository("proj_v18", session_factory=async_session_factory)


@pytest.mark.asyncio
async def test_save_manual_json_updates_normalized_fields_and_items(repo):
    await repo.insert_job("job_manual", "img.jpg", "done")

    payload = {
        "header": {
            "voucher_id": "AB12345678",
            "supplier": "測試供應商",
            "date": "2026-04-20",
        },
        "summary": {
            "purpose": "活動餐費",
            "total": 300,
        },
        "items": [
            {"category": "餐食", "name": "餐盒A", "qty": 1, "price": 100, "total": 100},
            {"category": "餐食", "name": "餐盒B", "qty": 2, "price": 100, "total": 200},
        ],
    }

    ok = await repo.save_manual_json("job_manual", payload)
    assert ok is True

    job = await repo.get_job("job_manual")
    assert job is not None
    assert job["voucher_id"] == "AB12345678"
    assert job["purpose"] == "活動餐費"
    assert job["supplier"] == "測試供應商"
    assert job["invoice_date"] == "2026-04-20"
    assert job["total_amount"] == 300.0
    assert job["manual_json_text"] is None

    items = await repo.list_invoice_items("job_manual")
    assert len(items) == 2
    assert items[0]["description"] == "餐盒A"
    assert items[1]["description"] == "餐盒B"


@pytest.mark.asyncio
async def test_get_job_details_reconstructs_legacy_editor_shape(repo):
    await repo.insert_job("job_details", "img.jpg", "running")

    vlm_payload = {
        "header": {
            "voucher_id": "VX-01",
            "supplier": "店家A",
            "date": "2026-04-19",
        },
        "summary": {"purpose": "文具", "total": 88},
        "items": [
            {"category": "消耗性教材", "name": "白板筆", "qty": 2, "price": 44, "total": 88},
        ],
    }

    ok = await repo.complete_vlm("job_details", vlm_payload)
    assert ok is True

    # Simulate manual save to ensure manual_json_text legacy key remains available in details response.
    await repo.save_manual_json(
        "job_details",
        {
            "header": {"voucher_id": "VX-01", "supplier": "店家A", "date": "2026-04-19"},
            "summary": {"purpose": "文具修正", "total": 90},
            "items": [
                {"category": "消耗性教材", "name": "白板筆", "qty": 2, "price": 45, "total": 90},
            ],
        },
    )

    details = await repo.get_job_details("job_details")
    assert details is not None
    assert isinstance(details["vlm_result"], dict)
    assert details["vlm_result"]["header"]["voucher_id"] == "VX-01"
    assert details["vlm_result"]["summary"]["purpose"] == "文具修正"
    assert len(details["vlm_result"]["items"]) == 1

    # Legacy compatibility key: now dynamically reconstructed from DB truth.
    assert details["manual_json_text"] is not None
    manual_obj = json.loads(details["manual_json_text"])
    assert manual_obj["summary"]["total"] == 90


@pytest.mark.asyncio
async def test_round_trip_manual_write_read_and_flatten_payload(repo):
    await repo.insert_job("job_roundtrip", "img.jpg", "done")

    payload = {
        "header": {
            "voucher_id": "R-001",
            "supplier": "供應商R",
            "date": "2026-04-18",
        },
        "summary": {
            "purpose": "保險費",
            "total": 50,
        },
        "items": [
            {"category": "保險", "name": "團體保險", "qty": 1, "price": 50, "total": 50},
        ],
    }

    await repo.save_manual_json("job_roundtrip", payload)

    display = await repo.get_display_result("job_roundtrip")
    assert display is not None
    assert display["header"]["voucher_id"] == "R-001"
    assert display["summary"]["purpose"] == "保險費"
    assert display["items"][0]["category"] == "保險"



@pytest.mark.asyncio
async def test_update_job_accepts_legacy_vlm_result_json_alias(repo):
    await repo.insert_job("job_alias", "img.jpg", "ready")

    payload_text = json.dumps({"header": {"voucher_id": "A1"}, "summary": {}, "items": []}, ensure_ascii=False)
    ok = await repo.update_job("job_alias", status="done", vlm_result_json=payload_text)
    assert ok is True

    job = await repo.get_job("job_alias")
    assert job is not None
    assert job["vlm_result_json"] == payload_text
    assert job["vlm_raw_json"] == payload_text
