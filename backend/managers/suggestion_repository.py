# 建議詞自動完成功能 - Suggestion Repository

import sqlite3
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 全域資料庫路徑
GLOBAL_DB_PATH = Path(__file__).parent.parent / "data" / "global.db"


class SuggestionRepository:
    """管理跨專案共用的建議詞資料庫"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or GLOBAL_DB_PATH
        self._ensure_db()
    
    def _ensure_db(self):
        """確保資料庫和表格存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    value TEXT NOT NULL,
                    count INTEGER DEFAULT 1,
                    UNIQUE(category, value)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_suggestions_category ON suggestions(category)")
            conn.commit()
            logger.info(f"[SuggestionRepo] 資料庫初始化完成: {self.db_path}")
        finally:
            conn.close()
    
    def search(self, category: str, query: str = "", limit: int = 20) -> List[str]:
        """
        搜尋建議詞
        
        Args:
            category: 分類 (supplier, item_name, buyer, seller_id, buyer_id, stamp_shop_name)
            query: 搜尋關鍵字 (模糊匹配)
            limit: 回傳數量上限
        
        Returns:
            匹配的建議詞列表 (依使用次數排序)
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            if query:
                cur = conn.execute(
                    "SELECT value FROM suggestions WHERE category = ? AND value LIKE ? ORDER BY count DESC LIMIT ?",
                    (category, f"%{query}%", limit)
                )
            else:
                cur = conn.execute(
                    "SELECT value FROM suggestions WHERE category = ? ORDER BY count DESC LIMIT ?",
                    (category, limit)
                )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
    
    def add_or_update(self, category: str, value: str) -> bool:
        """
        新增或更新建議詞 (若已存在則增加計數)
        
        Args:
            category: 分類
            value: 建議值
        
        Returns:
            成功與否
        """
        if not value or not value.strip():
            return False
        
        value = value.strip()
        conn = sqlite3.connect(str(self.db_path))
        try:
            # 使用 UPSERT (INSERT OR REPLACE with count increment)
            cur = conn.execute(
                "SELECT count FROM suggestions WHERE category = ? AND value = ?",
                (category, value)
            )
            row = cur.fetchone()
            
            if row:
                # 更新計數
                conn.execute(
                    "UPDATE suggestions SET count = count + 1 WHERE category = ? AND value = ?",
                    (category, value)
                )
            else:
                # 新增
                conn.execute(
                    "INSERT INTO suggestions (category, value, count) VALUES (?, ?, 1)",
                    (category, value)
                )
            
            conn.commit()
            logger.debug(f"[SuggestionRepo] 儲存建議: {category} -> {value}")
            return True
        except Exception as e:
            logger.error(f"[SuggestionRepo] 儲存失敗: {e}")
            return False
        finally:
            conn.close()
    
    def bulk_add(self, category: str, values: List[str]) -> int:
        """批次新增建議詞"""
        added = 0
        for value in values:
            if self.add_or_update(category, value):
                added += 1
        return added
