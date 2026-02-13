# Suggestions Router - 建議詞 API
import logging
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
from backend.repositories.suggestion_repository import SuggestionRepository

logger = logging.getLogger(__name__)
router = APIRouter()

# 全域 Repository 實例
suggestion_repo = SuggestionRepository()


class SuggestionRequest(BaseModel):
    category: str
    value: str


class BulkSuggestionRequest(BaseModel):
    category: str
    values: List[str]


@router.get("/suggestions")
def get_suggestions(
    category: str = Query(..., description="分類: supplier, item_name, buyer, seller_id, buyer_id, stamp_shop_name"),
    q: str = Query("", description="搜尋關鍵字"),
    limit: int = Query(20, description="回傳數量上限")
) -> List[str]:
    """查詢建議詞"""
    return suggestion_repo.search(category, q, limit)


@router.post("/suggestions")
def add_suggestion(request: SuggestionRequest):
    """新增或更新建議詞"""
    success = suggestion_repo.add_or_update(request.category, request.value)
    return {"status": "ok" if success else "failed"}


@router.post("/suggestions/bulk")
def bulk_add_suggestions(request: BulkSuggestionRequest):
    """批次新增建議詞"""
    added = suggestion_repo.bulk_add(request.category, request.values)
    return {"status": "ok", "added": added}
