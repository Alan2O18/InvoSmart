import json
from unittest.mock import AsyncMock

import anyio
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.database.core import Base
from backend.main import app
from backend.routers import stamps as stamps_router


def _build_sheet_image_bytes() -> bytes:
    image = np.full((300, 300, 3), 255, dtype=np.uint8)
    cv2.circle(image, (95, 100), 36, (0, 0, 220), -1)
    cv2.circle(image, (210, 190), 32, (0, 0, 210), -1)
    ok, buf = cv2.imencode('.png', image)
    assert ok
    return buf.tobytes()


@pytest.fixture
def stamp_client(tmp_path):
    db_engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def init_tables():
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    anyio.run(init_tables)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    old_storage_dir = stamps_router.STAMPS_STORAGE_DIR
    stamps_router.STAMPS_STORAGE_DIR = tmp_path / 'stamps'
    stamps_router.STAMPS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    app.dependency_overrides[stamps_router.get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(stamps_router.get_db, None)
    stamps_router.STAMPS_STORAGE_DIR = old_storage_dir
    anyio.run(db_engine.dispose)


def test_register_list_and_delete_stamp_roundtrip(stamp_client):
    image_bytes = _build_sheet_image_bytes()
    selections = [
        {
            'x': 50,
            'y': 55,
            'w': 95,
            'h': 95,
            'name': '測試社章',
            'category': '社團',
            'group_name': '美術組',
        }
    ]

    register = stamp_client.post(
        '/api/stamps/register',
        data={
            'mode': 'red',
            'selections': json.dumps(selections, ensure_ascii=False),
        },
        files={'file': ('sheet.png', image_bytes, 'image/png')},
    )

    assert register.status_code == 200
    register_payload = register.json()
    assert register_payload['status'] == 'registered'
    assert register_payload['count'] == 1

    created = register_payload['items'][0]
    created_path = created['image_path']

    listed = stamp_client.get('/api/stamps')
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]['name'] == '測試社章'

    delete_resp = stamp_client.delete(f"/api/stamps/{created['id']}")
    assert delete_resp.status_code == 200

    listed_after_delete = stamp_client.get('/api/stamps')
    assert listed_after_delete.status_code == 200
    assert listed_after_delete.json() == []

    if created_path.startswith('/') or ':' in created_path:
        from pathlib import Path

        assert not Path(created_path).exists()


def test_register_rejects_invalid_mode(stamp_client):
    image_bytes = _build_sheet_image_bytes()
    response = stamp_client.post(
        "/api/stamps/register",
        data={
            "mode": "blue",
            "selections": json.dumps([{"x": 1, "y": 1, "w": 10, "h": 10, "name": "A", "category": "社章"}], ensure_ascii=False),
        },
        files={"file": ("sheet.png", image_bytes, "image/png")},
    )
    assert response.status_code == 400


def test_register_rejects_invalid_selections_json(stamp_client):
    image_bytes = _build_sheet_image_bytes()
    response = stamp_client.post(
        "/api/stamps/register",
        data={"mode": "red", "selections": "{not-json"},
        files={"file": ("sheet.png", image_bytes, "image/png")},
    )
    assert response.status_code == 400


def test_register_rejects_empty_selections(stamp_client):
    image_bytes = _build_sheet_image_bytes()
    response = stamp_client.post(
        "/api/stamps/register",
        data={"mode": "red", "selections": json.dumps([], ensure_ascii=False)},
        files={"file": ("sheet.png", image_bytes, "image/png")},
    )
    assert response.status_code == 400


def test_register_rejects_invalid_selection_item(stamp_client):
    image_bytes = _build_sheet_image_bytes()
    response = stamp_client.post(
        "/api/stamps/register",
        data={"mode": "red", "selections": json.dumps([{"x": 1}], ensure_ascii=False)},
        files={"file": ("sheet.png", image_bytes, "image/png")},
    )
    assert response.status_code == 400


def test_register_rejects_blank_name_or_category(stamp_client):
    image_bytes = _build_sheet_image_bytes()
    response = stamp_client.post(
        "/api/stamps/register",
        data={
            "mode": "red",
            "selections": json.dumps([
                {"x": 1, "y": 1, "w": 10, "h": 10, "name": " ", "category": "社章"}
            ], ensure_ascii=False),
        },
        files={"file": ("sheet.png", image_bytes, "image/png")},
    )
    assert response.status_code == 400


def test_register_maps_service_value_error_to_400(stamp_client):
    image_bytes = _build_sheet_image_bytes()

    fake_service = AsyncMock()
    fake_service.register_stamps = AsyncMock(side_effect=ValueError("bad selection"))
    app.dependency_overrides[stamps_router.get_stamp_service] = lambda: fake_service
    try:
        response = stamp_client.post(
            "/api/stamps/register",
            data={
                "mode": "red",
                "selections": json.dumps([
                    {"x": 1, "y": 1, "w": 10, "h": 10, "name": "A", "category": "社章"}
                ], ensure_ascii=False),
            },
            files={"file": ("sheet.png", image_bytes, "image/png")},
        )
    finally:
        app.dependency_overrides.pop(stamps_router.get_stamp_service, None)

    assert response.status_code == 400


def test_register_maps_service_error_to_500(stamp_client):
    image_bytes = _build_sheet_image_bytes()

    fake_service = AsyncMock()
    fake_service.register_stamps = AsyncMock(side_effect=RuntimeError("service down"))
    app.dependency_overrides[stamps_router.get_stamp_service] = lambda: fake_service
    try:
        response = stamp_client.post(
            "/api/stamps/register",
            data={
                "mode": "red",
                "selections": json.dumps([
                    {"x": 1, "y": 1, "w": 10, "h": 10, "name": "A", "category": "社章"}
                ], ensure_ascii=False),
            },
            files={"file": ("sheet.png", image_bytes, "image/png")},
        )
    finally:
        app.dependency_overrides.pop(stamps_router.get_stamp_service, None)

    assert response.status_code == 500


def test_delete_stamp_not_found(stamp_client):
    response = stamp_client.delete("/api/stamps/999999")
    assert response.status_code == 404


def test_resolve_image_path_absolute_and_relative(tmp_path):
    relative = stamps_router._resolve_image_path("backend/data/stamps/x.png")
    assert str(relative).endswith("backend\\data\\stamps\\x.png")

    absolute_input = str(tmp_path / "abs.png")
    absolute = stamps_router._resolve_image_path(absolute_input)
    assert str(absolute) == absolute_input
