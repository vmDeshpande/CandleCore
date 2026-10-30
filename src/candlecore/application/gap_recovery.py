from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from candlecore.core.timestamp import timestamp_to_datetime
from candlecore.exchange.delta.rest_client import DeltaRestClient
from candlecore.storage.repositories import (
    CandleRepository,
    DataGapRepository,
    IngestionCheckpointRepository,
)

ProcessCandle = Callable[[dict[str, Any], str, str], Awaitable[None]]


class GapRecoveryService:
    """Detects missing candle intervals and recovers them via REST backfill.

    Time-dependent behaviour uses an injectable clock so it is deterministic
    in tests. The current incomplete candle is never treated as a gap.
    """

    def __init__(
        self,
        *,
        rest_client: DeltaRestClient,
        candle_repository: CandleRepository,
        gap_repository: DataGapRepository,
        checkpoint_repository: IngestionCheckpointRepository | None = None,
        process_candle: ProcessCandle | None = None,
        exchange: str = "delta",
        clock: Callable[..., Any] | None = None,
    ) -> None:
        self.rest_client = rest_client
        self.candle_repository = candle_repository
        self.gap_repository = gap_repository
        self.checkpoint_repository = checkpoint_repository
        self.process_candle = process_candle
        self.exchange = exchange
        self._clock = clock or (lambda: datetime.now(UTC))
        self._recovery_locks: dict[str, bool] = {}

    # --------------------------------------------------------------- detection
    def _interval_seconds(self, timeframe: str) -> int:
        mapping = {
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
        if timeframe not in mapping:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        return mapping[timeframe]

    def detect_gaps(
        self,
        *,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        existing_candles: list[dict[str, Any]],
    ) -> list[tuple[datetime, datetime]]:
        """Return missing (gap_start, gap_end) intervals within [start, end).

        The interval ending at `now` (the current incomplete candle) is not
        reported as a gap.
        """
        interval_seconds = self._interval_seconds(timeframe)
        now = self._clock()

        existing: set[datetime] = set()
        for candle in existing_candles:
            t = candle.get("time")
            if t is None:
                continue
            existing.add(timestamp_to_datetime(int(t), "seconds"))

        gaps: list[tuple[datetime, datetime]] = []
        cursor = start
        while cursor < end:
            interval_end = cursor + timedelta(seconds=interval_seconds)
            if interval_end > now:
                break
            if cursor not in existing:
                gaps.append((cursor, interval_end))
            cursor = interval_end
        return gaps

    # --------------------------------------------------------------- recovery
    async def persist_gaps(
        self,
        *,
        symbol: str,
        timeframe: str,
        gaps: list[tuple[datetime, datetime]],
    ) -> list[Any]:
        detected_at = self._clock()
        saved: list[Any] = []
        for gap_start, gap_end in gaps:
            gap = await self.gap_repository.add(
                exchange=self.exchange,
                symbol=symbol,
                timeframe=timeframe,
                gap_start=gap_start,
                gap_end=gap_end,
                detected_at=detected_at,
                fill_status="detected",
            )
            saved.append(gap)
        return saved

    async def recover_gap(
        self,
        *,
        symbol: str,
        timeframe: str,
        gap_start: datetime,
        gap_end: datetime,
    ) -> dict[str, Any]:
        """Recover a single gap via REST, normalize and persist candles.

        Checkpoint is updated only after successful processing.
        """
        lock_key = f"{symbol}:{timeframe}:{gap_start.isoformat()}"
        if self._recovery_locks.get(lock_key):
            return {
                "status": "skipped",
                "reason": "concurrent recovery already in progress",
                "symbol": symbol,
                "timeframe": timeframe,
            }
        self._recovery_locks[lock_key] = True

        try:
            start_ts = int(gap_start.timestamp())
            end_ts = int(gap_end.timestamp())
            candles = await self.rest_client.get_candles_chunked(
                symbol=symbol,
                resolution=timeframe,
                start=start_ts,
                end=end_ts,
            )

            restored = 0
            if self.process_candle is not None:
                for candle in candles:
                    await self.process_candle(candle, symbol, timeframe)
                    restored += 1

            # Mark gap filled only after successful verification.
            gaps = await self.gap_repository.list_unfilled(
                exchange=self.exchange, symbol=symbol, timeframe=timeframe
            )
            for gap in gaps:
                if gap.gap_start == gap_start and gap.gap_end == gap_end:
                    await self.gap_repository.mark_filled(gap)
                    break

            # Update checkpoint after successful processing.
            if self.checkpoint_repository is not None and restored > 0:
                await self.checkpoint_repository.upsert(
                    exchange=self.exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    last_processed_time=gap_end,
                    watermark=gap_end,
                    updated_at=self._clock(),
                )

            status = "filled" if restored > 0 else ("partial" if candles else "empty")
            return {
                "status": status,
                "symbol": symbol,
                "timeframe": timeframe,
                "candles_restored": restored,
            }
        finally:
            self._recovery_locks.pop(lock_key, None)
