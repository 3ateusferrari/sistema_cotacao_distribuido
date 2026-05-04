import pytest
import httpx
import asyncio

# URLs for the services (assuming they are running via docker-compose)
# When running from host:
EXTERNAL_SERVICE_URL = "http://localhost:8001"
QUOTE_SERVICE_URL = "http://localhost:8002"
AGGREGATOR_SERVICE_URL = "http://localhost:8003"

@pytest.mark.asyncio
async def test_full_flow():
    """
    Verifies that prices from external service reach the aggregator.
    Note: This requires the docker-compose to be UP.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Check if external service is up
        try:
            resp = await client.get(f"{EXTERNAL_SERVICE_URL}/quote")
            assert resp.status_code in [200, 503] # 503 is expected sometimes
        except Exception:
            pytest.skip("External service not reachable. Is docker-compose up?")

        # 2. Check if quote service is up
        resp = await client.get(f"{QUOTE_SERVICE_URL}/cotacao_atual/bitcoin")
        assert resp.status_code == 200
        
        # 3. Wait a bit for background tasks to run and populate DB
        print("Waiting for data propagation...")
        await asyncio.sleep(12) # quote_service updates every 10s
        
        # 4. Check aggregator service
        resp = await client.get(f"{AGGREGATOR_SERVICE_URL}/report/full")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "media_precos" in data
        assert "ultimos_logs" in data
        assert data["media_precos"]["bitcoin"] != "Erro"
        assert len(data["ultimos_logs"]["bitcoin"]) > 0

@pytest.mark.asyncio
async def test_circuit_breaker_resilience():
    """
    Tests that the system remains functional even if external service is unstable.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # We make multiple requests to aggregator
        # It should return data (potentially from cache/last known) 
        # even if external service is failing.
        for _ in range(5):
            resp = await client.get(f"{AGGREGATOR_SERVICE_URL}/report/full")
            assert resp.status_code == 200
            data = resp.json()
            assert "media_precos" in data
