import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from backend.main import app

@pytest.fixture
def test_client():
    return TestClient(app)

def test_get_suggestions(test_client):
    with patch("backend.routers.suggestions.SuggestionRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo.search.return_value = ["Seller A", "Seller B"]
        mock_repo_class.return_value = mock_repo
        
        response = test_client.get("/api/suggestions?category=supplier_name&q=Sel&limit=10")
        
        assert response.status_code == 200
        assert response.json() == ["Seller A", "Seller B"]
        mock_repo.search.assert_called_once_with("supplier_name", "Sel", 10)

def test_add_suggestion_success(test_client):
    with patch("backend.routers.suggestions.SuggestionRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo.add_or_update.return_value = True
        mock_repo_class.return_value = mock_repo
        
        response = test_client.post("/api/suggestions", json={"category": "buyer_name", "value": "New Buyer"})
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_repo.add_or_update.assert_called_once_with("buyer_name", "New Buyer")

def test_add_suggestion_failure(test_client):
    with patch("backend.routers.suggestions.SuggestionRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo.add_or_update.return_value = False
        mock_repo_class.return_value = mock_repo
        
        response = test_client.post("/api/suggestions", json={"category": "item_name", "value": "  "})
        
        assert response.status_code == 200
        assert response.json() == {"status": "failed"}

def test_bulk_add_suggestions(test_client):
    with patch("backend.routers.suggestions.SuggestionRepository") as mock_repo_class:
        mock_repo = AsyncMock()
        mock_repo.bulk_add.return_value = 2
        mock_repo_class.return_value = mock_repo
        
        response = test_client.post(
            "/api/suggestions/bulk", 
            json={"category": "shop_name", "values": ["Shop 1", "Shop 2"]}
        )
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "added": 2}
        mock_repo.bulk_add.assert_called_once_with("shop_name", ["Shop 1", "Shop 2"])
