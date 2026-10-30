from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from candlecore.core.timestamp import timestamp_to_datetime
from candlecore.market_data.lifecycle import CandleLifecycleEngine
from candlecore.market_data.normalization import (
    normalize_rest_candle,
    normalize_ws_message,
)
from candlecore.storage.repositories import (
    CandleRepository,
    CandleRevisionRepository,
    DataGapRepository,
    IngestionCheckpointRepository,
    RawMarketEventRepository,
)


class IngestionService:
    """Orchestrates the market-data ingestion pipeline.

    Pipeline: raw event -> persist -> validate/normalize -> candle lifecycle
    -> persistence -> checkpoint update.
    """

    def __init__(
        self,
        *,
        candle_repository: CandleRepository,
        revision_repository: CandleRevisionRepository,
        raw_event_repository: RawMarketEventRepository,
        checkpoint_repository: IngestionCheckpointRepository,
        gap_repository: DataGapRepository | None = None,
        lifecycle_engine: CandleLifecycleEngine | None = None,
        clock: Callable[..., Any] | None = None,
    ) -> None:
        self.candle_repository = candle_repository
        self.revision_repository = revision_repository
        self.raw_event_repository = raw_event_repository
        self.checkpoint_repository = checkpoint_repository
        self.gap_repository = gap_repository
        self.lifecycle_engine = lifecycle_engine or CandleLifecycleEngine(
            candle_repository, revision_repository, clock=clock
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    # --------------------------------------------------------------- REST events
    async def ingest_rest_candle(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        source: str,
        candle: dict[str, Any],
        timestamp_unit: str = "seconds",
        checkpoint: bool = True,
    ) -> Any:
        received_at = self._clock()
        event_time = timestamp_to_datetime(int(candle["time"]), timestamp_unit)  # type: ignore[arg-type]

        # 1. Persist the raw event first (never discard raw data).
        await self.raw_event_repository.add(
            exchange=exchange,
            symbol=symbol,
            event_type="candle",
            source=source,
            event_time=event_time,
            received_at=received_at,
            processed_at=None,
            original_timestamp=int(candle["time"]),
            original_timestamp_unit=timestamp_unit,
            sequence=None,
            schema_version=1,
            payload=dict(candle),
        )

        # 2. Normalize.
        update = normalize_rest_candle(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            candle=candle,
            timestamp_unit=timestamp_unit,
        )

        # 3. Candle lifecycle.
        result = await self.lifecycle_engine.process_update(
            update, source=source, received_at=received_at
        )

        # 4. Checkpoint.
        if checkpoint and self.checkpoint_repository is not None:
            await self.checkpoint_repository.upsert(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                last_processed_time=received_at,
                watermark=event_time,
                updated_at=received_at,
            )

        return result

    # ------------------------------------------------------------- WebSocket events
    async def ingest_ws_message(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        source: str,
        message: dict[str, Any],
        timestamp_unit: str = "seconds",
        checkpoint: bool = True,
    ) -> Any:
        received_at = self._clock()
        raw_timestamp = message.get("cst")
        if raw_timestamp is None:
            raw_timestamp = message.get("ts")
        event_time = (
            timestamp_to_datetime(int(raw_timestamp), timestamp_unit)  # type: ignore[arg-type]
            if raw_timestamp is not None
            else received_at
        )

        # 1. Persist the raw event first.
        await self.raw_event_repository.add(
            exchange=exchange,
            symbol=symbol,
            event_type="candle",
            source=source,
            event_time=event_time,
            received_at=received_at,
            processed_at=None,
            original_timestamp=(int(raw_timestamp) if raw_timestamp is not None else None),
            original_timestamp_unit=timestamp_unit,
            sequence=None,
            schema_version=1,
            payload=dict(message),
        )

        # 2. Normalize.
        update = normalize_ws_message(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            message=message,
            timestamp_unit=timestamp_unit,
        )

        # 3. Candle lifecycle (handles duplicates, out-of-order, revisions).
        result = await self.lifecycle_engine.process_update(
            update, source=source, received_at=received_at
        )

        # 4. Checkpoint.
        if checkpoint and self.checkpoint_repository is not None:
            await self.checkpoint_repository.upsert(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                last_processed_time=received_at,
                watermark=event_time,
                updated_at=received_at,
            )

        return result
