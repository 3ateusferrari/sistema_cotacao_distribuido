import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from main import app, fetch_quote_from_external_service, store_log

client = TestClient(app)

@pytest.mark.asyncio
async def test_fetch_quote_from_external_service_success():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"bitcoin": 50000.0, "ethereum": 3000.0}
        
        result = await fetch_quote_from_external_service()
        
        assert result["bitcoin"] == 50000.0
        assert result["ethereum"] == 3000.0

@pytest.mark.asyncio
async def test_fetch_quote_from_external_service_retry_and_cache():
    # Test that it retries and eventually returns cache if it fails
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = Exception("Connection error")
        
        # Set a last_known_quote
        with patch("main.last_known_quote", {"bitcoin": 100.0, "ethereum": 10.0}):
            result = await fetch_quote_from_external_service()
            assert result["bitcoin"] == 100.0

@pytest.mark.asyncio
async def test_store_log_bitcoin():
    with patch("main.shard1_db.execute", new_callable=AsyncMock) as mock_execute:
        await store_log("bitcoin", 50000.0)
        mock_execute.assert_called_once()
        args, kwargs = mock_execute.call_args
        assert kwargs["values"]["coin"] == "bitcoin"
        assert kwargs["values"]["price"] == 50000.0

@pytest.mark.asyncio
async def test_store_log_ethereum():
    with patch("main.shard2_db.execute", new_callable=AsyncMock) as mock_execute:
        await store_log("ethereum", 3000.0)
        mock_execute.assert_called_once()
        args, kwargs = mock_execute.call_args
        assert kwargs["values"]["coin"] == "ethereum"
        assert kwargs["values"]["price"] == 3000.0

def test_get_current_quote_success():
    with patch("main.last_known_quote", {"bitcoin": 50000.0, "ethereum": 3000.0}):
        response = client.get("/cotacao_atual/bitcoin")
        assert response.status_code == 200
        assert response.json() == {"coin": "bitcoin", "price": 50000.0}

def test_get_current_quote_not_found():
    response = client.get("/cotacao_atual/dogecoin")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_average_last_10_success():
    mock_results = [{"price": 100.0}, {"price": 200.0}]
    with patch("main.shard1_db.fetch_all", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_results
        response = client.get("/media_ultimos_10_logs/bitcoin")
        assert response.status_code == 200
        assert response.json()["average_price"] == 150.0
        assert response.json()["log_count"] == 2
