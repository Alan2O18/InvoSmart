# Suggestions Router - 建議詞 API
import logging
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from typing import List
from backend.repositories.suggestion_repository import SuggestionRepository

logger = logging.getLogger(__name__)
router = APIRouter()


class SuggestionRequest(BaseModel):
    category: str
    value: str


class BulkSuggestionRequest(BaseModel):
    category: str
    values: List[str]

def get_suggestion_repo() -> SuggestionRepository:
    """Dependency to provide a SuggestionRepository instance."""
    from backend.database import core
    return SuggestionRepository(session_factory=lambda: core.AsyncSessionLocal())
@router.get("/suggestions")
async def get_suggestions(
    category: str = Query(..., description="分類: supplier_name, buyer_name, supplier_tax_id, buyer_tax_id, item_name, shop_name, expense_category"),
    q: str = Query("", description="搜尋關鍵字"),
    limit: int = Query(20, description="回傳數量上限"),
    repo: SuggestionRepository = Depends(get_suggestion_repo)
) -> List[str]:
    """查詢建議詞"""
    return await repo.search(category, q, limit)


@router.post("/suggestions")
async def add_suggestion(
    request: SuggestionRequest, 
    repo: SuggestionRepository = Depends(get_suggestion_repo)
):
    """新增或更新建議詞"""
    success = await repo.add_or_update(request.category, request.value)
    return {"status": "ok" if success else "failed"}


@router.post("/suggestions/bulk")
async def bulk_add_suggestions(
    request: BulkSuggestionRequest, 
    repo: SuggestionRepository = Depends(get_suggestion_repo)
):
    """批次新增建議詞"""
    added = await repo.bulk_add(request.category, request.values)
    return {"status": "ok", "added": added}
