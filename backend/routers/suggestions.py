# Suggestions Router - 建議詞 API
import logging
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from typing import List
from backend.repositories.suggestion_repository import SuggestionRepository
from backend.dependencies import get_engine
from backend.engine.core import Engine

logger = logging.getLogger(__name__)
router = APIRouter()


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
    limit: int = Query(20, description="回傳數量上限"),
    engine: Engine = Depends(get_engine)
) -> List[str]:
    """查詢建議詞"""
    repo = SuggestionRepository(db_path=engine.global_db_path)
    return repo.search(category, q, limit)


@router.post("/suggestions")
def add_suggestion(request: SuggestionRequest, engine: Engine = Depends(get_engine)):
    """新增或更新建議詞"""
    repo = SuggestionRepository(db_path=engine.global_db_path)
    success = repo.add_or_update(request.category, request.value)
    return {"status": "ok" if success else "failed"}


@router.post("/suggestions/bulk")
def bulk_add_suggestions(request: BulkSuggestionRequest, engine: Engine = Depends(get_engine)):
    """批次新增建議詞"""
    repo = SuggestionRepository(db_path=engine.global_db_path)
    added = repo.bulk_add(request.category, request.values)
    return {"status": "ok", "added": added}
