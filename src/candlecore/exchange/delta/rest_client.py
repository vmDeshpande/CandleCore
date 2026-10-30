from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

class DeltaRestClient:
    def __init__(self, base_url: str = "https://api.india.delta.exchange", timeout: float = 30.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def close(self):
        await self._client.aclose()
    
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_candles(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int
    ) -> dict[str, Any]:
        url = f"{self.base_url}/v2/history/candles"
        params = {
            "resolution": resolution,
            "symbol": symbol,
            "start": start,
            "end": end
        }
        logger.info("fetching_candles", symbol=symbol, resolution=resolution, start=start, end=end)
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    
    async def get_candles_chunked(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int,
        max_candles: int = 2000
    ) -> list[dict[str, Any]]:
        all_candles = []
        current_start = start
        
        # Calculate interval in seconds
        interval_map = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600}
        interval_seconds = interval_map.get(resolution, 180)
        
        while current_start < end:
            current_end = min(current_start + (max_candles * interval_seconds), end)
            data = await self.get_candles(symbol, resolution, current_start, current_end)
            if data.get("success") and data.get("result"):
                candles = data["result"]
                all_candles.extend(candles)
                if len(candles) < max_candles:
                    break
                current_start = candles[-1]["time"] + interval_seconds  # Move past last candle
            else:
                break
        
        # Deduplicate and sort ascending
        seen = set()
        unique_candles = []
        for c in all_candles:
            key = c["time"]
            if key not in seen:
                seen.add(key)
                unique_candles.append(c)
        unique_candles.sort(key=lambda x: x["time"])
        return unique_candles
