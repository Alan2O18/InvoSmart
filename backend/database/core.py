import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy import MetaData

logger = logging.getLogger(__name__)

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

Base = declarative_base(metadata=MetaData(naming_convention=convention))

# Global variables to hold engines and sessionmakers
async_engine = None
AsyncSessionLocal = None
sync_engine = None
SyncSessionLocal = None


def get_global_db_path() -> Path:
    """Read config.json and return the absolute path to global.db, or fallback."""
    from backend.utils.config import load_config
    
    db_path_str = "backend/data/global.db"
    try:
        config = load_config()
        pm_settings = config.get("project_manager_settings", {})
        db_path_str = pm_settings.get("global_db_path", db_path_str)
    except Exception as e:
        logger.warning(f"[DB] Failed to get global_db_path from config, using default: {e}")

    # Ensure path is expanded and absolute
    return Path(db_path_str).expanduser().resolve()


def set_sqlite_pragma(dbapi_connection, connection_record):
    """Event listener to force foreign_keys=ON and journal_mode=WAL on SQLite connects."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    except Exception as e:
        logger.warning(f"[DB] Failed to set PRAGMA: {e}")


async def init_db(db_path: Path = None):
    """Initialize engines and session factories and create tables asynchronously. Safe to call multiple times."""
    global async_engine, AsyncSessionLocal, sync_engine, SyncSessionLocal

    if db_path is None:
        db_path = get_global_db_path()

    if ":memory:" not in str(db_path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url_async = f"sqlite+aiosqlite:///{db_path}"
        database_url_sync = f"sqlite:///{db_path}"
    else:
        # For in-memory testing
        database_url_async = "sqlite+aiosqlite:///:memory:"
        database_url_sync = "sqlite:///:memory:"

    logger.info(f"[DB] Initializing Async ORM connection: {database_url_async}")

    # --- Async Engine ---
    # NullPool is vital for SQLite + Asyncio to prevent 'database is locked' errors under concurrency
    async_engine = create_async_engine(
        database_url_async,
        poolclass=NullPool,
        echo=False
    )
    
    # Attach PRAGMA listener to underlying sync connection of async_engine
    event.listen(async_engine.sync_engine, "connect", set_sqlite_pragma)

    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    # --- Sync Engine (Used by Background Workers) ---
    logger.info(f"[DB] Initializing Sync ORM connection: {database_url_sync}")
    
    sync_engine = create_engine(
        database_url_sync,
        poolclass=NullPool,
        echo=False
    )
    
    # Attach PRAGMA listener to sync_engine
    event.listen(sync_engine, "connect", set_sqlite_pragma)
    
    SyncSessionLocal = sessionmaker(
        bind=sync_engine,
        autoflush=False,
        expire_on_commit=False
    )
    
    # --- Create Tables ---
    # This replaces the need for Alembic in simple SQLite deployments
    # Import models here to ensure SQLAlchemy metadata includes all tables.
    from backend.database import models as _models  # noqa: F401
    async with async_engine.begin() as conn:
        logger.info("[DB] Creating core tables if they don't exist...")
        await conn.run_sync(Base.metadata.create_all)
