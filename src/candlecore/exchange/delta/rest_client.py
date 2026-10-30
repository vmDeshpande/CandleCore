from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from candlecore.exchange.delta.schemas import DeltaRestResponse

logger = structlog.get_logger()

SECONDS_PER_RESOLUTION = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "1d": 86400,
    "1w": 604800,
}

MAX_CANDLES_PER_REQUEST = 2000


class RateLimitedError(Exception):
    """Raised when the exchange responds with HTTP 429.

    Carries the Retry-After duration (seconds) when supplied by the server.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class DeltaRestClient:
    SUPPORTED_RESOLUTIONS = frozenset(SECONDS_PER_RESOLUTION.keys())

    def __init__(
        self,
        base_url: str = "https://api.india.delta.exchange",
        timeout: float = 30.0,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    def _interval_seconds(self, resolution: str) -> int:
        if resolution not in self.SUPPORTED_RESOLUTIONS:
            raise ValueError(f"unsupported resolution: {resolution}")
        return SECONDS_PER_RESOLUTION[resolution]

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float | None:
        header = response.headers.get("Retry-After") or response.headers.get("retry-after")
        if header is None:
            return None
        try:
            return float(header)
        except ValueError:
            return None

    async def get_candles(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int,
    ) -> DeltaRestResponse:
        if not symbol:
            raise ValueError("symbol is required")
        if start >= end:
            raise ValueError("start must be before end")
        self._interval_seconds(resolution)

        url = f"{self.base_url}/v2/history/candles"
        params = {
            "resolution": resolution,
            "symbol": symbol,
            "start": str(start),
            "end": str(end),
        }
        logger.info(
            "fetching_candles",
            symbol=symbol,
            resolution=resolution,
            start=start,
            end=end,
        )

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(
                (
                    RateLimitedError,
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.HTTPStatusError,
                )
            ),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=self.base_delay, max=self.max_delay),
        ):
            with attempt:
                response = await self._client.get(url, params=params)

                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    logger.warning("rate_limited", retry_after=retry_after)
                    raise RateLimitedError("rate limited by exchange", retry_after=retry_after)

                if response.status_code >= 500:
                    logger.error(
                        "exchange_server_error",
                        status_code=response.status_code,
                        symbol=symbol,
                        resolution=resolution,
                    )
                    raise httpx.HTTPStatusError(
                        "exchange server error", request=response.request, response=response
                    )

                response.raise_for_status()

                try:
                    data = response.json()
                except Exception as exc:
                    logger.error("invalid_json_response", symbol=symbol, resolution=resolution)
                    raise ValueError(f"invalid JSON response from exchange: {exc}") from exc

                try:
                    return DeltaRestResponse.model_validate(data)
                except Exception as exc:
                    logger.error(
                        "invalid_response_envelope",
                        symbol=symbol,
                        resolution=resolution,
                        error=str(exc),
                    )
                    raise ValueError(f"invalid response envelope: {exc}") from exc

        # Unreachable: AsyncRetrying either returns or raises.
        raise RuntimeError("retry loop exited without result")

    async def get_candles_chunked(
        self,
        symbol: str,
        resolution: str,
        start: int,
        end: int,
        max_candles: int = MAX_CANDLES_PER_REQUEST,
    ) -> list[dict[str, Any]]:
        """Fetch candles across [start, end) in bounded chunks.

        Returns candles deduplicated by candle time and sorted ascending.
        Never assumes a short response means the full interval is complete.
        """
        if not symbol:
            raise ValueError("symbol is required")
        if start >= end:
            raise ValueError("start must be before end")
        interval_seconds = self._interval_seconds(resolution)
        if max_candles <= 0:
            raise ValueError("max_candles must be positive")

        all_candles: list[dict[str, Any]] = []
        current_start = start

        while current_start < end:
            current_end = min(current_start + max_candles * interval_seconds, end)
            try:
                response = await self.get_candles(symbol, resolution, current_start, current_end)
            except Exception:
                logger.error(
                    "chunk_fetch_failed",
                    symbol=symbol,
                    resolution=resolution,
                    start=current_start,
                    end=current_end,
                )
                raise

            candles = [c.model_dump() for c in response.result] if response.result else []
            if not candles:
                current_start = current_end
                continue

            all_candles.extend(candles)
            last_time = candles[-1].get("time")
            if last_time is None:
                current_start = current_end
                continue

            last_time = int(last_time)
            if len(candles) < max_candles:
                current_start = current_end
            else:
                current_start = last_time + interval_seconds

        seen: set[int] = set()
        unique_candles: list[dict[str, Any]] = []
        for candle in all_candles:
            candle_time = candle.get("time")
            if candle_time is None or candle_time in seen:
                continue
            seen.add(candle_time)
            unique_candles.append(candle)
        unique_candles.sort(key=lambda c: c["time"])
        return unique_candles
