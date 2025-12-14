# backend/engine/__init__.py
"""
Engine 模塊

提供 Engine 類和 get_engine() 工廠函數。
不再在模塊加載時創建實例，改為延遲初始化。
"""
from .core import Engine
from backend.dependencies import get_engine

# 為向後兼容提供 engine 屬性（延遲獲取）
# 注意：這是一個函數調用的結果，不是模塊級別的實例
def __getattr__(name):
    if name == 'engine':
        return get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ['Engine', 'get_engine']
