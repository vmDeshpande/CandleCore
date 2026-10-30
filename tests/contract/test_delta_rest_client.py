from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import tenacity

from candlecore.exchange.delta.rest_client import (
    DeltaRestClient,
)


def _make_response(status_code=200, json_data=None, headers=None):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.headers = headers or {}
    response.request = MagicMock(spec=httpx.Request)
    if json_data is not None:
        response.json.return_value = json_data
    else:
        response.json.return_value = {"success": True, "result": []}
    return response


def _candle(t, open_="100", high="110", low="90", close="105", volume="1000"):
    return {
        "time": t,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _make_client(max_retries=1):
    return DeltaRestClient(
        base_url="https://api.india.delta.exchange", timeout=5.0, max_retries=max_retries
    )


@pytest.mark.asyncio
async def test_rest_valid_response():
    client = _make_client()
    data = {"success": True, "result": [_candle(1700000000), _candle(1700000180)]}
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, data)
        result = await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)
    assert result.success is True
    assert len(result.result) == 2


@pytest.mark.asyncio
async def test_rest_empty_response():
    client = _make_client()
    data = {"success": True, "result": []}
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, data)
        result = await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)
    assert result.result == []


@pytest.mark.asyncio
async def test_rest_invalid_envelope():
    client = _make_client()
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, {"not": "an envelope"})
        with pytest.raises(ValueError, match="invalid response envelope"):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_invalid_candle():
    client = _make_client()
    data = {"success": True, "result": [{"time": "not-an-int", "open": "x"}]}
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, data)
        with pytest.raises(ValueError):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_descending_and_ascending_dedup():
    client = _make_client()
    candles = [
        _candle(1700000360),
        _candle(1700000180),
        _candle(1700000180),
        _candle(1700000000),
    ]
    data = {"success": True, "result": candles}
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, data)
        result = await client.get_candles_chunked("BTCUSD", "3m", 1700000000, 1700000400)
    times = [c["time"] for c in result]
    assert times == sorted(times)
    assert len(times) == len(set(times))


@pytest.mark.asyncio
async def test_rest_exactly_2000_candles():
    client = _make_client()
    candles = [_candle(1700000000 + i * 180) for i in range(2000)]
    data = {"success": True, "result": candles}
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, data)
        result = await client.get_candles_chunked(
            "BTCUSD", "3m", 1700000000, 1700000000 + 2000 * 180
        )
    assert len(result) == 2000


@pytest.mark.asyncio
async def test_rest_pagination_multiple_requests():
    client = _make_client()
    calls = []

    async def fake_get(url, params):
        calls.append(dict(params))
        start = int(params["start"])
        if start == 1700000000:
            candles = [_candle(1700000000 + i * 180) for i in range(2000)]
        else:
            candles = [_candle(1700000000 + 2000 * 180 + i * 180) for i in range(5)]
        return _make_response(200, {"success": True, "result": candles})

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = fake_get
        result = await client.get_candles_chunked(
            "BTCUSD", "3m", 1700000000, 1700000000 + 2005 * 180
        )
    assert len(result) == 2005
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_rest_sparse_response():
    client = _make_client()
    data = {"success": True, "result": []}
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_response(200, data)
        result = await client.get_candles_chunked("BTCUSD", "3m", 1700000000, 1700000200)
    assert result == []


@pytest.mark.asyncio
async def test_rest_overlapping_chunk_boundaries_deduped():
    client = _make_client()
    chunk1 = [_candle(1700000000), _candle(1700000180), _candle(1700000360)]
    chunk2 = [_candle(1700000360), _candle(1700000540)]
    calls = {"n": 0}

    async def fake_get(url, params):
        calls["n"] += 1
        if calls["n"] == 1:
            return _make_response(200, {"success": True, "result": chunk1})
        return _make_response(200, {"success": True, "result": chunk2})

    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = fake_get
        result = await client.get_candles_chunked("BTCUSD", "3m", 1700000000, 1700000600)
    times = [c["time"] for c in result]
    assert times == sorted(times)
    assert len(times) == len(set(times))
    assert 1700000360 in times


@pytest.mark.asyncio
async def test_rest_http_429():
    client = _make_client()
    response = _make_response(429, {"error": "rate limited"}, headers={"Retry-After": "5"})
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        with pytest.raises(tenacity.RetryError):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_parse_retry_after():
    client = _make_client()
    response = _make_response(429, {}, headers={"Retry-After": "7.5"})
    assert client._parse_retry_after(response) == 7.5

    response = _make_response(200, {}, headers={})
    assert client._parse_retry_after(response) is None


@pytest.mark.asyncio
async def test_rest_http_5xx():
    client = _make_client()
    response = _make_response(500, {"error": "server error"})
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        with pytest.raises(tenacity.RetryError):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_timeout():
    client = _make_client()
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("timeout")
        with pytest.raises(tenacity.RetryError):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_network_failure():
    client = _make_client()
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.NetworkError("network down")
        with pytest.raises(tenacity.RetryError):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_retry_exhaustion():
    client = _make_client(max_retries=5)
    response = _make_response(500, {"error": "server error"})
    with patch.object(client._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        with pytest.raises(tenacity.RetryError):
            await client.get_candles("BTCUSD", "3m", 1700000000, 1700000200)
    assert mock_get.call_count == 5


@pytest.mark.asyncio
async def test_rest_unsupported_resolution():
    client = _make_client()
    with pytest.raises(ValueError, match="unsupported resolution"):
        await client.get_candles("BTCUSD", "99m", 1700000000, 1700000200)


@pytest.mark.asyncio
async def test_rest_invalid_start_end():
    client = _make_client()
    with pytest.raises(ValueError, match="start must be before end"):
        await client.get_candles("BTCUSD", "3m", 1700000200, 1700000000)


@pytest.mark.asyncio
async def test_rest_incorrect_symbol_empty():
    client = _make_client()
    with pytest.raises(ValueError, match="symbol is required"):
        await client.get_candles("", "3m", 1700000000, 1700000200)
