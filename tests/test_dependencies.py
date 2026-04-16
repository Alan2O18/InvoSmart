import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend import dependencies
from backend.database import core as database_core


@pytest.mark.asyncio
async def test_get_db_reads_latest_async_session_local():
    old_factory = database_core.AsyncSessionLocal
    async_engine = None

    try:
        database_core.AsyncSessionLocal = None
        with pytest.raises(HTTPException):
            agen = dependencies.get_db()
            await agen.__anext__()

        async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        database_core.AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        agen = dependencies.get_db()
        session = await agen.__anext__()
        assert isinstance(session, AsyncSession)
        await agen.aclose()
    finally:
        database_core.AsyncSessionLocal = old_factory
        if async_engine is not None:
            await async_engine.dispose()


def test_get_sync_db_reads_latest_sync_session_local():
    old_factory = database_core.SyncSessionLocal
    sync_engine = None

    try:
        database_core.SyncSessionLocal = None
        with pytest.raises(HTTPException):
            gen = dependencies.get_sync_db()
            next(gen)

        sync_engine = create_engine("sqlite:///:memory:", echo=False)
        database_core.SyncSessionLocal = sessionmaker(
            bind=sync_engine,
            autoflush=False,
            expire_on_commit=False,
        )

        gen = dependencies.get_sync_db()
        session = next(gen)
        assert session is not None
        gen.close()
    finally:
        database_core.SyncSessionLocal = old_factory
        if sync_engine is not None:
            sync_engine.dispose()
