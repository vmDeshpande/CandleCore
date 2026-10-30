from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from candlecore.core.contracts import CandleState
from candlecore.storage.models import (
    Candle,
    CandleRevision,
    DataGap,
    IngestionCheckpoint,
    RawMarketEvent,
)


class RawMarketEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        exchange: str,
        symbol: str | None,
        event_type: str,
        source: str,
        event_time: datetime,
        received_at: datetime,
        processed_at: datetime | None,
        original_timestamp: int | None,
        original_timestamp_unit: str | None,
        sequence: int | None,
        schema_version: int,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> RawMarketEvent:

        event = RawMarketEvent(
            event_id=event_id,
            exchange=exchange,
            symbol=symbol,
            event_type=event_type,
            source=source,
            event_time=event_time,
            received_at=received_at,
            processed_at=processed_at,
            original_timestamp=original_timestamp,
            original_timestamp_unit=original_timestamp_unit,
            sequence=sequence,
            schema_version=schema_version,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        return event


class CandleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_identity(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        candle_open_time: datetime,
    ) -> Candle | None:
        result = await self.session.execute(
            select(Candle).where(
                Candle.exchange == exchange,
                Candle.symbol == symbol,
                Candle.timeframe == timeframe,
                Candle.candle_open_time == candle_open_time,
            )
        )
        return result.scalar_one_or_none()

    async def list_candles(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[Candle]:
        stmt = select(Candle).where(
            Candle.exchange == exchange,
            Candle.symbol == symbol,
            Candle.timeframe == timeframe,
        )
        if start is not None:
            stmt = stmt.where(Candle.candle_open_time >= start)
        if end is not None:
            stmt = stmt.where(Candle.candle_open_time < end)
        stmt = stmt.order_by(Candle.candle_open_time.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        source: str,
        candle_open_time: datetime,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal | None,
        state: CandleState | str,
        received_at: datetime,
        finalized_at: datetime | None = None,
        reconciled_at: datetime | None = None,
    ) -> tuple[Candle, bool]:
        """Insert or update a candle by identity.

        Returns (candle, created). When an existing candle is updated, the
        caller is responsible for recording a revision via
        :meth:`CandleLifecycleEngine.revise_candle` (or equivalent) before
        calling this, so history is preserved.
        """
        state_value = state.value if isinstance(state, CandleState) else str(state)

        stmt = (
            insert(Candle)
            .values(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                source=source,
                candle_open_time=candle_open_time,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                state=state_value,
                revision=0,
                first_received_at=received_at,
                last_received_at=received_at,
                finalized_at=finalized_at,
                reconciled_at=reconciled_at,
            )
            .on_conflict_do_update(
                constraint="uq_candle_identity",
                set_={
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "state": state_value,
                    "last_received_at": received_at,
                    "finalized_at": finalized_at,
                    "reconciled_at": reconciled_at,
                },
            )
            .returning(Candle)
        )
        result = await self.session.execute(stmt)
        candle = result.scalar_one()
        # Determine whether this was a create by checking revision/first_received.
        created = candle.first_received_at == candle.last_received_at
        return candle, created

    async def update_state(
        self,
        candle: Candle,
        *,
        state: CandleState | str,
        finalized_at: datetime | None = None,
        reconciled_at: datetime | None = None,
        revision: int | None = None,
    ) -> Candle:
        state_value = state.value if isinstance(state, CandleState) else str(state)
        candle.state = state_value
        if finalized_at is not None:
            candle.finalized_at = finalized_at
        if reconciled_at is not None:
            candle.reconciled_at = reconciled_at
        if revision is not None:
            candle.revision = revision
        candle.last_received_at = datetime.now(UTC)
        self.session.add(candle)
        await self.session.flush()
        return candle


class CandleRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        candle_id: str,
        revision_number: int,
        exchange: str,
        symbol: str,
        timeframe: str,
        candle_open_time: datetime,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal | None,
        reason: str | None,
        revised_at: datetime,
        raw_payload: dict[str, Any] | None = None,
    ) -> CandleRevision:
        from uuid import UUID

        revision = CandleRevision(
            candle_id=UUID(candle_id) if isinstance(candle_id, str) else candle_id,
            revision_number=revision_number,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=candle_open_time,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            reason=reason,
            revised_at=revised_at,
            raw_payload=raw_payload,
        )
        self.session.add(revision)
        await self.session.flush()
        return revision


class DataGapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        gap_start: datetime,
        gap_end: datetime,
        detected_at: datetime,
        fill_status: str = "detected",
    ) -> DataGap:
        gap = DataGap(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            gap_start=gap_start,
            gap_end=gap_end,
            detected_at=detected_at,
            fill_status=fill_status,
        )
        self.session.add(gap)
        await self.session.flush()
        return gap

    async def list_unfilled(
        self,
        *,
        exchange: str,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> list[DataGap]:
        stmt = select(DataGap).where(
            DataGap.exchange == exchange,
            DataGap.fill_status != "filled",
        )
        if symbol is not None:
            stmt = stmt.where(DataGap.symbol == symbol)
        if timeframe is not None:
            stmt = stmt.where(DataGap.timeframe == timeframe)
        stmt = stmt.order_by(DataGap.gap_start.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_filled(
        self,
        gap: DataGap,
        *,
        filled_at: datetime | None = None,
    ) -> DataGap:
        gap.fill_status = "filled"
        gap.filled_at = filled_at or datetime.now(UTC)
        self.session.add(gap)
        await self.session.flush()
        return gap


class IngestionCheckpointRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> IngestionCheckpoint | None:
        result = await self.session.execute(
            select(IngestionCheckpoint).where(
                IngestionCheckpoint.exchange == exchange,
                IngestionCheckpoint.symbol == symbol,
                IngestionCheckpoint.timeframe == timeframe,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        last_processed_time: datetime,
        watermark: datetime,
        updated_at: datetime | None = None,
    ) -> IngestionCheckpoint:
        now = updated_at or datetime.now(UTC)
        stmt = (
            insert(IngestionCheckpoint)
            .values(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                last_processed_time=last_processed_time,
                watermark=watermark,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_ingestion_checkpoint_identity",
                set_={
                    "last_processed_time": last_processed_time,
                    "watermark": watermark,
                    "updated_at": now,
                },
            )
            .returning(IngestionCheckpoint)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
