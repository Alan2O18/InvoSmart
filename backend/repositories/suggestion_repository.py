# backend/repositories/suggestion_repository.py
"""
建議詞自動完成功能 - Suggestion Repository (SQLAlchemy 版)

Schema 欄位：
  id            - 主鍵
  category      - 分類標籤 (嚴格定義，見 VALID_CATEGORIES)
  value         - 建議詞內容
  count         - 使用次數 (越高 = 越優先提供給 AI)
  last_used_at  - 最後使用時間 (越近 = 越優先提供給 AI)

AI RAG 排序：依 last_used_at DESC, count DESC (最近常用優先)
"""

import time
import logging
from typing import List, Optional, Dict, Any, Callable

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Suggestion

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
}

# RAG Prompt 提供的每個分類最大建議數
RAG_TOP_N = 30


class SuggestionRepository:
    """管理跨專案共用的建議詞資料庫 (SQLAlchemy ORM 版)"""

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self.session_factory = session_factory

    # =========================================================
    # 基本 CRUD
    # =========================================================

    async def search(self, category: str, query: str = "", limit: int = 20) -> List[str]:
        """
        搜尋建議詞（依最近使用時間 + 頻率排序）
        """
        async with self.session_factory() as session:
            stmt = select(Suggestion.value).where(Suggestion.category == category)
            if query:
                stmt = stmt.where(Suggestion.value.like(f"%{query}%"))
                
            stmt = stmt.order_by(Suggestion.last_used_at.desc(), Suggestion.count.desc()).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def add_or_update(self, category: str, value: str) -> bool:
        """
        新增或更新建議詞（若已存在則增加計數並更新時間）
        """
        if not value or not value.strip():
            return False

        value = value.strip()
        now = time.time()
        
        try:
            async with self.session_factory() as session:
                stmt = select(Suggestion).where(Suggestion.category == category, Suggestion.value == value)
                suggestion = (await session.execute(stmt)).scalar_one_or_none()
                
                if suggestion:
                    suggestion.count += 1
                    suggestion.last_used_at = now
                else:
                    suggestion = Suggestion(
                        category=category,
                        value=value,
                        count=1,
                        last_used_at=now
                    )
                    session.add(suggestion)
                    
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"[SuggestionRepo] 儲存失敗: {e}")
            return False

    async def bulk_add(self, category: str, values: List[str]) -> int:
        """批次新增建議詞"""
        added = 0
        for value in values:
            if await self.add_or_update(category, value):
                added += 1
        return added

    # =========================================================
    # AI 回饋機制 (Feedback Loop)
    # =========================================================

    async def extract_from_manual_json(self, json_data: dict) -> int:
        """
        從使用者手動儲存的 JSON 中萃取知識，寫入建議詞庫。
        """
        added = 0
        header = json_data.get("header", {})

        # 買方
        buyer = header.get("buyer", "")
        if buyer:
            added += int(await self.add_or_update("buyer_name", buyer))

        # 賣方 / 供應商
        supplier = header.get("supplier", "")
        if supplier:
            added += int(await self.add_or_update("supplier_name", supplier))

        # 賣方統編
        tax_id = header.get("tax_id", "")
        if tax_id:
            added += int(await self.add_or_update("supplier_tax_id", tax_id))

        # 店章名稱
        verification = json_data.get("verification", {})
        stamp_shop = verification.get("stamp_shop_name", "")
        if stamp_shop:
            added += int(await self.add_or_update("shop_name", stamp_shop))

        # 品項名稱
        for item in json_data.get("items", []):
            name = item.get("name", "")
            if name:
                added += int(await self.add_or_update("item_name", name))

        logger.info(f"[SuggestionRepo] 從 manual_json 萃取 {added} 筆知識")
        return added

    # =========================================================
    # AI RAG Context Builder
    # =========================================================

    async def build_rag_context(self, top_n: int = RAG_TOP_N) -> str:
        """
        建立給 VLM 的 RAG Prompt 上下文。
        格式為人類可讀的繁體中文清單，讓 AI 在辨識時優先參考。
        若清單不存在的詞彙請依圖片辨識，不要強行湊合。
        """
        suppliers = await self.search("supplier_name", limit=top_n)
        buyers    = await self.search("buyer_name", limit=top_n)
        items     = await self.search("item_name", limit=top_n)
        shops     = await self.search("shop_name", limit=top_n)
        tax_ids   = await self.search("supplier_tax_id", limit=top_n)

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
