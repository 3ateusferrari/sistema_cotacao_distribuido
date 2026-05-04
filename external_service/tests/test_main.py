import pytest
from fastapi.testclient import TestClient
from main import app, current_prices
import time

client = TestClient(app)

def test_get_quote_success(monkeypatch):
    # Mock FAILURE_RATE to 0 to ensure success
    monkeypatch.setattr("main.FAILURE_RATE", 0.0)
    
    response = client.get("/quote")
    assert response.status_code == 200
    data = response.json()
    assert "bitcoin" in data
    assert "ethereum" in data
    assert data["bitcoin"] == current_prices["bitcoin"]
    assert data["ethereum"] == current_prices["ethereum"]

def test_get_quote_failure(monkeypatch):
    # Mock FAILURE_RATE to 1.0 to ensure failure
    monkeypatch.setattr("main.FAILURE_RATE", 1.0)
    
    response = client.get("/quote")
    assert response.status_code == 503
    assert response.json()["detail"] == "Serviço indisponível. Tente novamente mais tarde."

@pytest.mark.asyncio
async def test_update_prices(monkeypatch):
    from main import update_prices
    
    initial_prices = current_prices.copy()
    
    # We want to test that prices change. 
    # Since update_prices is a while True loop with a sleep, 
    # we can use a small trick: mock asyncio.sleep to raise an exception after one call
    
    sleep_count = 0
    original_sleep = asyncio.sleep
    
    async def mock_sleep(seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 1:
            raise InterruptedError("Test finished")
        await original_sleep(0.01) # Short sleep

    import asyncio
    monkeypatch.setattr(asyncio, "sleep", mock_sleep)
    
    try:
        await update_prices()
    except InterruptedError:
        pass
    
    assert current_prices["bitcoin"] != initial_prices["bitcoin"] or current_prices["ethereum"] != initial_prices["ethereum"]

# Note: The test_update_prices might be flaky due to random variation potentially being 0, 
# but with 5 seconds of variation it's unlikely to be exactly the same.
# Also, current_prices is global, so it might affect other tests if not careful.
# For unit tests, it's better to isolate state.
