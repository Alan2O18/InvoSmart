# backend/dependencies.py
"""
FastAPI 依賴注入模組

提供 Engine 實例的獲取和管理功能。
- 生產環境：使用 get_engine() 獲取全局實例
- 測試環境：使用 set_engine() 注入測試實例
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# 全局 Engine 實例（延遲初始化）
_engine_instance = None


def get_engine():
    """
    獲取 Engine 實例。
    
    生產環境：返回全局單例（在 lifespan startup 中預先初始化）
    測試環境：返回通過 set_engine() 設置的實例
    
    Returns:
        Engine: 配置好的 Engine 實例
    """
    global _engine_instance
    if _engine_instance is None:
        from backend.engine.core import Engine
        logger.info("[Dependencies] 創建新的 Engine 實例")
        _engine_instance = Engine(start_workers=True)
    return _engine_instance


def set_engine(engine) -> None:
    """
    設置 Engine 實例（用於測試）。
    
    Args:
        engine: 要設置的 Engine 實例（可以是 mock）
    """
    global _engine_instance
    _engine_instance = engine
    logger.info("[Dependencies] Engine 實例已設置")


def reset_engine() -> None:
    """
    重置 Engine 實例（用於測試清理）。
    
    會觸發 shutdown event 讓 Worker 線程結束。
    """
    global _engine_instance
    if _engine_instance is not None:
        if hasattr(_engine_instance, '_shutdown_event'):
            _engine_instance._shutdown_event.set()
        logger.info("[Dependencies] Engine 實例已重置")
    _engine_instance = None

from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from backend.database.core import AsyncSessionLocal, SyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """獲取非同步 DB Session (用於 FastAPI Router)"""
    async with AsyncSessionLocal() as session:
        yield session

def get_sync_db() -> Generator[Session, None, None]:
    """獲取同步 DB Session (用於背景 Thread 或特殊同步情境)"""
    with SyncSessionLocal() as session:
        yield session
