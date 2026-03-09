import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import text

import backend.database.core as database_core


def test_get_global_db_path_uses_config_value(tmp_path):
    configured_path = tmp_path / "db" / "custom.db"

    with patch(
        "backend.utils.config.load_config",
        return_value={"project_manager_settings": {"global_db_path": str(configured_path)}},
    ):
        assert database_core.get_global_db_path() == configured_path.resolve()


def test_get_global_db_path_falls_back_when_config_load_fails():
    with patch("backend.utils.config.load_config", side_effect=RuntimeError("boom")):
        fallback = database_core.get_global_db_path()

    assert fallback.name == "global.db"
    assert fallback.is_absolute()


def test_set_sqlite_pragma_executes_expected_statements():
    cursor = MagicMock()
    dbapi_connection = MagicMock()
    dbapi_connection.cursor.return_value = cursor

    database_core.set_sqlite_pragma(dbapi_connection, None)

    cursor.execute.assert_any_call("PRAGMA foreign_keys=ON")
    cursor.execute.assert_any_call("PRAGMA journal_mode=WAL")
    cursor.close.assert_called_once()


@pytest.mark.asyncio
async def test_init_db_creates_working_session_factories(tmp_path):
    db_path = tmp_path / "data" / "test.db"

    await database_core.init_db(db_path)

    assert database_core.AsyncSessionLocal is not None
    assert database_core.SyncSessionLocal is not None
    assert db_path.parent.exists()

    async with database_core.AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

    await database_core.async_engine.dispose()
    database_core.sync_engine.dispose()
