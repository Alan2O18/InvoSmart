# 建議詞自動完成功能 - Suggestion Repository (Phase 1: Unified)
"""
統一建議詞庫（合併自 vocabulary + suggestions）

Schema 欄位：
  id            - 主鍵
  category      - 分類標籤 (嚴格定義，見 VALID_CATEGORIES)
  value         - 建議詞內容
  count         - 使用次數 (越高 = 越優先提供給 AI)
  last_used_at  - 最後使用時間 (越近 = 越優先提供給 AI)

AI RAG 排序：依 last_used_at DESC, count DESC (最近常用優先)
"""

import sqlite3
import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# 嚴格定義的分類標籤 (避免 AI 混淆欄位屬性)
VALID_CATEGORIES = {
    "supplier_name":   "賣方/供應商名稱",
    "buyer_name":      "買方/買受人名稱",
    "supplier_tax_id": "賣方統一編號",
    "buyer_tax_id":    "買方統一編號",
    "item_name":       "品項名稱",
    "shop_name":       "店家/章名稱",
    "expense_category":"報帳名目",
    # 舊版相容 (legacy)
    "supplier":        "賣方 (舊版相容)",
    "buyer":           "買方 (舊版相容)",
    "seller_id":       "賣方統編 (舊版相容)",
    "buyer_id":        "買方統編 (舊版相容)",
    "stamp_shop_name": "店章 (舊版相容)",
}

# RAG Prompt 提供的每個分類最大建議數
RAG_TOP_N = 30


class SuggestionRepository:
    """管理跨專案共用的建議詞資料庫（統合版）"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            raise ValueError(
                "SuggestionRepository requires an explicit db_path. "
                "Pass the unified global.db path from Engine/config."
            )
        self.db_path = Path(db_path)
        self._ensure_db()

    def _get_conn(self):
        """取得資料庫連線（含最佳化 PRAGMA）"""
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self):
        """確保資料庫與表格存在，並執行 Schema 遷移"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS suggestions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    category     TEXT NOT NULL,
                    value        TEXT NOT NULL,
                    count        INTEGER DEFAULT 1,
                    last_used_at REAL DEFAULT (strftime('%s','now')),
                    UNIQUE(category, value)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_suggestions_category ON suggestions(category)"
            )

            # Migration: 補充 last_used_at 欄位（若舊版不存在）
            # 必須在建立包含此欄位的複合索引之前先做遷移
            # SQLite ALTER TABLE 不支援 non-constant default，需分兩步
            try:
                conn.execute("SELECT last_used_at FROM suggestions LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE suggestions ADD COLUMN last_used_at REAL")
                conn.execute(f"UPDATE suggestions SET last_used_at = {time.time()} WHERE last_used_at IS NULL")
                logger.info("[SuggestionRepo] 遷移: 已新增 last_used_at 欄位並回填時間")

            # 建立複合索引（依賴 last_used_at 欄位存在）
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_suggestions_rank "
                    "ON suggestions(category, last_used_at, count)"
                )
            except sqlite3.OperationalError as e:
                logger.warning(f"[SuggestionRepo] 建立複合索引失敗（可忽略）: {e}")

            conn.commit()
            logger.info(f"[SuggestionRepo] 資料庫初始化完成: {self.db_path}")
        finally:
            conn.close()

    # =========================================================
    # 基本 CRUD
    # =========================================================

    def search(self, category: str, query: str = "", limit: int = 20) -> List[str]:
        """
        搜尋建議詞（依最近使用時間 + 頻率排序）

        Args:
            category: 分類標籤
            query:    模糊搜尋關鍵字
            limit:    回傳數量上限
        """
        conn = self._get_conn()
        try:
            if query:
                cur = conn.execute(
                    "SELECT value FROM suggestions "
                    "WHERE category = ? AND value LIKE ? "
                    "ORDER BY last_used_at DESC, count DESC LIMIT ?",
                    (category, f"%{query}%", limit),
                )
            else:
                cur = conn.execute(
                    "SELECT value FROM suggestions "
                    "WHERE category = ? "
                    "ORDER BY last_used_at DESC, count DESC LIMIT ?",
                    (category, limit),
                )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def add_or_update(self, category: str, value: str) -> bool:
        """
        新增或更新建議詞（若已存在則增加計數並更新時間）

        Args:
            category: 分類標籤
            value:    建議詞內容
        Returns:
            成功與否
        """
        if not value or not value.strip():
            return False

        value = value.strip()
        now = time.time()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "SELECT id FROM suggestions WHERE category = ? AND value = ?",
                (category, value),
            )
            row = cur.fetchone()

            if row:
                conn.execute(
                    "UPDATE suggestions SET count = count + 1, last_used_at = ? "
                    "WHERE category = ? AND value = ?",
                    (now, category, value),
                )
            else:
                conn.execute(
                    "INSERT INTO suggestions (category, value, count, last_used_at) VALUES (?, ?, 1, ?)",
                    (category, value, now),
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

    # =========================================================
    # AI 回饋機制 (Feedback Loop)
    # =========================================================

    def extract_from_manual_json(self, json_data: dict) -> int:
        """
        從使用者手動儲存的 JSON 中萃取知識，寫入建議詞庫。

        觸發時機：使用者在 Job Editor 儲存 (PUT /jobs/{id}/json) 時呼叫。

        Args:
            json_data: 使用者確認後的完整收據 JSON
        Returns:
            成功寫入的建議詞數量
        """
        added = 0
        header = json_data.get("header", {})

        # 買方
        buyer = header.get("buyer", "")
        if buyer:
            added += int(self.add_or_update("buyer_name", buyer))

        # 賣方 / 供應商
        supplier = header.get("supplier", "")
        if supplier:
            added += int(self.add_or_update("supplier_name", supplier))

        # 賣方統編
        tax_id = header.get("tax_id", "")
        if tax_id:
            added += int(self.add_or_update("supplier_tax_id", tax_id))

        # 店章名稱
        verification = json_data.get("verification", {})
        stamp_shop = verification.get("stamp_shop_name", "")
        if stamp_shop:
            added += int(self.add_or_update("shop_name", stamp_shop))

        # 品項名稱
        for item in json_data.get("items", []):
            name = item.get("name", "")
            if name:
                added += int(self.add_or_update("item_name", name))

        logger.info(f"[SuggestionRepo] 從 manual_json 萃取 {added} 筆知識")
        return added

    # =========================================================
    # AI RAG Context Builder
    # =========================================================

    def build_rag_context(self, top_n: int = RAG_TOP_N) -> str:
        """
        建立給 VLM 的 RAG Prompt 上下文。

        格式為人類可讀的繁體中文清單，讓 AI 在辨識時優先參考。
        若清單不存在的詞彙請依圖片辨識，不要強行湊合。

        Args:
            top_n: 每個分類最多提供的建議數
        Returns:
            格式化的 prompt 字串（若無資料則回傳空字串）
        """
        suppliers = self.search("supplier_name", limit=top_n)
        buyers    = self.search("buyer_name", limit=top_n)
        items     = self.search("item_name", limit=top_n)
        shops     = self.search("shop_name", limit=top_n)
        tax_ids   = self.search("supplier_tax_id", limit=top_n)

        # 若完全沒有資料，回傳空字串（不影響 Prompt）
        if not any([suppliers, buyers, items, shops, tax_ids]):
            return ""

        lines = [
            "【歷史常用詞彙參考清單】",
            "（若發票內容與清單相符，請優先採用清單中的標準寫法；",
            "若清單中沒有相似項，請依照原始圖片辨識，不要強行湊合）",
            "",
        ]

        if suppliers:
            lines.append(f"▸ 常見賣方/供應商：{', '.join(suppliers)}")
        if buyers:
            lines.append(f"▸ 常見買方/買受人：{', '.join(buyers)}")
        if tax_ids:
            lines.append(f"▸ 常見賣方統編：{', '.join(tax_ids)}")
        if shops:
            lines.append(f"▸ 常見店章名稱：{', '.join(shops)}")
        if items:
            lines.append(f"▸ 常見品項名稱：{', '.join(items)}")

        return "\n".join(lines)

    # =========================================================
    # 從 ProjectRepository.vocabulary 遷移資料 (一次性呼叫)
    # =========================================================

    def migrate_from_vocabulary_table(self, global_db_path: Optional[Path] = None) -> int:
        """
        將 global.db 中舊的 vocabulary 表遷移至統一的 suggestions 表。

        這是一次性腳本入口，可由管理介面或 startup 檢查觸發。

        Returns:
            遷移的紀錄數
        """
        source_path = global_db_path or self.db_path
        migrated = 0

        try:
            conn = self._get_conn()
            # 確認 vocabulary 表存在
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='vocabulary'"
            )
            if not cur.fetchone():
                logger.info("[SuggestionRepo] vocabulary 表不存在，無需遷移")
                conn.close()
                return 0

            # 讀取 vocabulary 資料
            cur = conn.execute("SELECT category, term, frequency, last_seen_at FROM vocabulary")
            rows = cur.fetchall()
            conn.close()

            # 映射 vocabulary category -> suggestion category
            category_map = {
                "supplier_name": "supplier_name",
                "buyer_name":    "buyer_name",
                "item_name":     "item_name",
                "supplier":      "supplier_name",
                "buyer":         "buyer_name",
                "item":          "item_name",
            }

            for row in rows:
                cat     = category_map.get(row["category"], row["category"])
                term    = row["term"]
                freq    = row["frequency"] or 1
                last_at = row["last_seen_at"] or time.time()

                if not term:
                    continue

                conn2 = self._get_conn()
                try:
                    existing = conn2.execute(
                        "SELECT id, count FROM suggestions WHERE category=? AND value=?",
                        (cat, term),
                    ).fetchone()

                    if existing:
                        conn2.execute(
                            "UPDATE suggestions SET count=count+?, last_used_at=MAX(last_used_at, ?) "
                            "WHERE category=? AND value=?",
                            (freq, last_at, cat, term),
                        )
                    else:
                        conn2.execute(
                            "INSERT INTO suggestions (category, value, count, last_used_at) "
                            "VALUES (?, ?, ?, ?)",
                            (cat, term, freq, last_at),
                        )
                    conn2.commit()
                    migrated += 1
                finally:
                    conn2.close()

            logger.info(f"[SuggestionRepo] vocabulary 遷移完成: {migrated} 筆")
            return migrated

        except Exception as e:
            logger.error(f"[SuggestionRepo] 遷移失敗: {e}")
            return migrated
