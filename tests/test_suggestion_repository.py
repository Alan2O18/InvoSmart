import pytest_asyncio
import pytest
import time
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.database.models import Base, Suggestion
from backend.repositories.suggestion_repository import SuggestionRepository

@pytest_asyncio.fixture
async def async_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    yield session_factory
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
def suggestion_repo(async_session_factory):
    return SuggestionRepository(async_session_factory)

@pytest.mark.asyncio
async def test_add_or_update_new(suggestion_repo):
    success = await suggestion_repo.add_or_update("supplier_name", "Test Supplier")
    assert success is True
    
    # Verify it was added
    results = await suggestion_repo.search("supplier_name")
    assert len(results) == 1
    assert results[0] == "Test Supplier"

@pytest.mark.asyncio
async def test_add_or_update_existing(suggestion_repo, async_session_factory):
    # Add first time
    await suggestion_repo.add_or_update("item_name", "Coffee")
    time.sleep(0.01) # to ensure last_used_at is slightly different
    
    # Add again
    success = await suggestion_repo.add_or_update("item_name", "Coffee")
    assert success is True
    
    # Verify count increased
    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(Suggestion).where(Suggestion.value == "Coffee"))
        suggestion = result.scalar_one()
        assert suggestion.count == 2

@pytest.mark.asyncio
async def test_add_or_update_empty(suggestion_repo):
    success = await suggestion_repo.add_or_update("item_name", "   ")
    assert success is False
    results = await suggestion_repo.search("item_name")
    assert len(results) == 0

@pytest.mark.asyncio
async def test_bulk_add(suggestion_repo):
    added = await suggestion_repo.bulk_add("buyer_name", ["Alice", "Bob", "Alice"])
    assert added == 3 # Returns total add/update operations executed
    
    results = await suggestion_repo.search("buyer_name")
    assert len(results) == 2
    assert "Alice" in results
    assert "Bob" in results

@pytest.mark.asyncio
async def test_search_with_query_and_sorting(suggestion_repo):
    # Add multiple items
    await suggestion_repo.bulk_add("shop_name", ["Shop A", "Shop B", "Shop C"])
    time.sleep(0.01)
    # Shop A used again, should be first
    await suggestion_repo.add_or_update("shop_name", "Shop A")
    
    # Check default sorting (by last_used_at desc, count desc)
    results = await suggestion_repo.search("shop_name")
    assert results[0] == "Shop A"
    assert len(results) == 3
    
    # Search with query
    query_results = await suggestion_repo.search("shop_name", query="hop B")
    assert len(query_results) == 1
    assert query_results[0] == "Shop B"

@pytest.mark.asyncio
async def test_extract_from_manual_json(suggestion_repo):
    json_data = {
        "header": {
            "buyer": "Test Buyer",
            "supplier": "Test Supplier",
            "tax_id": "12345678"
        },
        "verification": {
            "stamp_shop_name": "Test Shop"
        },
        "items": [
            {"name": "Item 1"},
            {"name": "Item 2"}
        ]
    }
    
    added_count = await suggestion_repo.extract_from_manual_json(json_data)
    # 1 buyer + 1 supplier + 1 tax_id + 1 shop + 2 items = 6
    assert added_count == 6
    
    # Verify mapping
    assert await suggestion_repo.search("buyer_name") == ["Test Buyer"]
    assert await suggestion_repo.search("supplier_name") == ["Test Supplier"]
    assert await suggestion_repo.search("supplier_tax_id") == ["12345678"]
    assert await suggestion_repo.search("shop_name") == ["Test Shop"]
    
    items = await suggestion_repo.search("item_name")
    assert "Item 1" in items and "Item 2" in items

@pytest.mark.asyncio
async def test_build_rag_context_empty(suggestion_repo):
    context = await suggestion_repo.build_rag_context()
    assert context == ""

@pytest.mark.asyncio
async def test_build_rag_context_populated(suggestion_repo):
    await suggestion_repo.add_or_update("supplier_name", "Supplier X")
    await suggestion_repo.add_or_update("buyer_name", "Buyer Y")
    await suggestion_repo.add_or_update("item_name", "Item Z")
    await suggestion_repo.add_or_update("supplier_tax_id", "88888888")
    
    context = await suggestion_repo.build_rag_context()
    
    assert "【歷史常用詞彙參考清單】" in context
    assert "▸ 常見賣方/供應商：Supplier X" in context
    assert "▸ 常見買方/買受人：Buyer Y" in context
    assert "▸ 常見賣方統編：88888888" in context
    assert "▸ 常見品項名稱：Item Z" in context
    # verify shop name not in context since we didn't add any
    assert "常見店章名稱" not in context


@pytest.mark.asyncio
async def test_location_suggestion_lifecycle(suggestion_repo):
    # 1. Add location suggestions
    success1 = await suggestion_repo.add_or_update("location", "Room 401")
    success2 = await suggestion_repo.add_or_update("location", "Conference Hall")
    assert success1 is True
    assert success2 is True

    # 2. Search location suggestions
    results = await suggestion_repo.search("location")
    assert len(results) == 2
    assert "Room 401" in results
    assert "Conference Hall" in results

    # 3. Retrieve all suggestions under location category
    all_suggestions = await suggestion_repo.get_all("location")
    assert len(all_suggestions) == 2
    room_record = next(r for r in all_suggestions if r["value"] == "Room 401")
    
    # 4. Update location suggestion
    update_success = await suggestion_repo.update(room_record["id"], "location", "Room 402")
    assert update_success is True

    # Verify updated search
    results_updated = await suggestion_repo.search("location")
    assert "Room 402" in results_updated
    assert "Room 401" not in results_updated

    # 5. Delete location suggestion
    delete_success = await suggestion_repo.delete(room_record["id"])
    assert delete_success is True

    # Verify deleted
    results_after_delete = await suggestion_repo.search("location")
    assert len(results_after_delete) == 1
    assert "Room 402" not in results_after_delete
    assert "Conference Hall" in results_after_delete

