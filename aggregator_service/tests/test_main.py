import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from main import app, fetch_current_average_price, fetch_last_logs_from_shard
from datetime import datetime

client = TestClient(app)

@pytest.mark.asyncio
async def test_fetch_current_average_price_success():
    mock_client = AsyncMock()
    mock_client.get.return_value.status_code = 200
    mock_client.get.return_value.json.return_value = {"average_price": 50000.0}
    
    result = await fetch_current_average_price(mock_client, "bitcoin")
    assert result["average_price"] == 50000.0

@pytest.mark.asyncio
async def test_fetch_last_logs_from_shard_success():
    mock_db = AsyncMock()
    mock_db.fetch_all.return_value = [
        {"coin": "bitcoin", "price": 50000.0, "timestamp": datetime.now()}
    ]
    
    result = await fetch_last_logs_from_shard(mock_db, "bitcoin")
    assert len(result) == 1
    assert result[0]["coin"] == "bitcoin"

def test_get_full_report_success():
    with patch("main.fetch_current_average_price", new_callable=AsyncMock) as mock_fetch_avg, \
         patch("main.fetch_last_logs_from_shard", new_callable=AsyncMock) as mock_fetch_logs:
        
        mock_fetch_avg.side_effect = [
            {"average_price": 50000.0}, # btc
            {"average_price": 3000.0}   # eth
        ]
        mock_fetch_logs.side_effect = [
            [{"coin": "bitcoin", "price": 50000.0, "timestamp": "2023-01-01T00:00:00"}], # btc logs
            [{"coin": "ethereum", "price": 3000.0, "timestamp": "2023-01-01T00:00:00"}]  # eth logs
        ]
        
        response = client.get("/report/full")
        assert response.status_code == 200
        data = response.json()
        assert data["media_precos"]["bitcoin"] == 50000.0
        assert data["ultimos_logs"]["bitcoin"][0]["coin"] == "bitcoin"
