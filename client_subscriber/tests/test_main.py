import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from main import price_subscriber

@pytest.mark.asyncio
async def test_price_subscriber_receives_message(capsys):
    # Mock redis connection
    mock_redis = MagicMock()
    mock_pubsub = AsyncMock()
    mock_redis.pubsub.return_value = mock_pubsub
    
    # Mock messages
    messages = [
        {"type": "message", "data": json.dumps({"bitcoin": 50000.0, "ethereum": 3000.0})},
        None # To trigger timeout or next iteration
    ]
    
    async def mock_get_message(*args, **kwargs):
        if not messages:
            raise asyncio.CancelledError() # Terminate the loop
        return messages.pop(0)

    mock_pubsub.get_message.side_effect = mock_get_message
    
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        try:
            await price_subscriber()
        except asyncio.CancelledError:
            pass
            
    captured = capsys.readouterr()
    assert ">>> NOVA COTAÇÃO RECEBIDA! <<<" in captured.out
    assert "Bitcoin:  $ 50000.00" in captured.out
    assert "Ethereum: $ 3000.00" in captured.out
