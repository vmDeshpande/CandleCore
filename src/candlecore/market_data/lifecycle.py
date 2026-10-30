from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from candlecore.core.contracts import CandleState, NormalizedCandleUpdate
from candlecore.storage.repositories import (
    CandleRepository,
    CandleRevisionRepository,
)


class CandleUpdateAction(Enum):
    INSERTED = "inserted"
    UPDATED = "updated"
    REVISED = "revised"
    DUPLICATE_IGNORED = "duplicate_ignored"


@dataclass
class CandleUpdateResult:
    action: CandleUpdateAction
    candle_id: str | None
    exchange: str
    symbol: str
    timeframe: str
    candle_open_time: datetime
    revision: int
    state: CandleState
    meaningful_change: bool
    reason: str | None = None


class CandleLifecycleEngine:
    """Coordinates candle insert, update, duplicate handling and revisions.

    Keeps exchange communication separate from domain persistence. All
    timestamp handling is delegated to an injectable clock so behaviour is
    deterministic in tests.
    """

    def __init__(
        self,
        candle_repository: CandleRepository,
        revision_repository: CandleRevisionRepository,
        clock: Callable[..., Any] | None = None,
    ) -> None:
        self.candle_repository = candle_repository
        self.revision_repository = revision_repository
        self._clock = clock or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------ entry
    async def process_update(
        self,
        update: NormalizedCandleUpdate,
        *,
        source: str,
        received_at: datetime | None = None,
    ) -> CandleUpdateResult:
        """Validate and apply a normalized candle update.

        Transition rules (documented):
          * Candle absent            -> INSERT as PROVISIONAL, revision 0.
          * Candle present, identical OHLCV -> exact duplicate, ignored.
          * Candle present, changed  -> preserve previous version as a
                                        revision, increment revision, set
                                        state PROVISIONAL (or CORRECTED when
                                        the stored candle was FINALIZED).
        """
        received_at = received_at or self._clock()

        existing = await self.candle_repository.get_by_identity(
            exchange=update.exchange,
            symbol=update.symbol,
            timeframe=update.timeframe,
            candle_open_time=update.candle_open_time,
        )

        if existing is None:
            candle, _ = await self.candle_repository.upsert(
                exchange=update.exchange,
                symbol=update.symbol,
                timeframe=update.timeframe,
                source=source,
                candle_open_time=update.candle_open_time,
                open_price=update.open,
                high=update.high,
                low=update.low,
                close=update.close,
                volume=update.volume,
                state=CandleState.PROVISIONAL,
                received_at=received_at,
            )
            return CandleUpdateResult(
                action=CandleUpdateAction.INSERTED,
                candle_id=str(candle.id),
                exchange=update.exchange,
                symbol=update.symbol,
                timeframe=update.timeframe,
                candle_open_time=update.candle_open_time,
                revision=candle.revision,
                state=CandleState(candle.state),
                meaningful_change=True,
                reason="new candle",
            )

        # Existing candle: compare OHLCV for a meaningful change.
        if self._same_ohlcv(existing, update):
            await self.candle_repository.update_state(
                existing,
                state=CandleState(existing.state),
                revision=existing.revision,
            )
            return CandleUpdateResult(
                action=CandleUpdateAction.DUPLICATE_IGNORED,
                candle_id=str(existing.id),
                exchange=update.exchange,
                symbol=update.symbol,
                timeframe=update.timeframe,
                candle_open_time=update.candle_open_time,
                revision=existing.revision,
                state=CandleState(existing.state),
                meaningful_change=False,
                reason="exact duplicate",
            )

        # Meaningful change: preserve previous version as a revision.
        await self.revision_repository.add(
            candle_id=str(existing.id),
            revision_number=existing.revision,
            exchange=existing.exchange,
            symbol=existing.symbol,
            timeframe=existing.timeframe,
            candle_open_time=existing.candle_open_time,
            open_price=existing.open,
            high=existing.high,
            low=existing.low,
            close=existing.close,
            volume=existing.volume,
            reason="candle revised by new observation",
            revised_at=received_at,
            raw_payload=update.raw_payload,
        )

        new_revision = existing.revision + 1
        new_state = (
            CandleState.CORRECTED
            if CandleState(existing.state) == CandleState.FINALIZED
            else CandleState.PROVISIONAL
        )

        # Persist the new OHLCV, revision and state on the existing row.
        existing.open = update.open
        existing.high = update.high
        existing.low = update.low
        existing.close = update.close
        existing.volume = update.volume
        existing.state = new_state.value
        existing.revision = new_revision
        existing.last_received_at = received_at
        await self.session_add_and_flush(existing)

        return CandleUpdateResult(
            action=CandleUpdateAction.REVISED,
            candle_id=str(existing.id),
            exchange=update.exchange,
            symbol=update.symbol,
            timeframe=update.timeframe,
            candle_open_time=update.candle_open_time,
            revision=new_revision,
            state=new_state,
            meaningful_change=True,
            reason="ohlcv changed",
        )

    async def finalize(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        candle_open_time: datetime,
        finalized_at: datetime | None = None,
    ) -> CandleUpdateResult | None:
        """Mark a stored candle as FINALIZED."""
        finalized_at = finalized_at or self._clock()
        existing = await self.candle_repository.get_by_identity(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=candle_open_time,
        )
        if existing is None:
            return None
        await self.candle_repository.update_state(
            existing,
            state=CandleState.FINALIZED,
            finalized_at=finalized_at,
            revision=existing.revision,
        )
        return CandleUpdateResult(
            action=CandleUpdateAction.UPDATED,
            candle_id=str(existing.id),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=candle_open_time,
            revision=existing.revision,
            state=CandleState.FINALIZED,
            meaningful_change=False,
            reason="finalized",
        )

    async def reconcile(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        candle_open_time: datetime,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal | None,
        reconciled_at: datetime | None = None,
    ) -> CandleUpdateResult:
        """Reconcile a candle against REST history.

        Stale REST data must not overwrite a newer live observation. A
        REST reconciliation only updates when the stored candle is not
        FINALIZED, or when the REST values differ meaningfully from a
        PROVISIONAL candle.
        """
        reconciled_at = reconciled_at or self._clock()
        existing = await self.candle_repository.get_by_identity(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=candle_open_time,
        )

        if existing is None:
            candle, _ = await self.candle_repository.upsert(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                source="exchange_rest",
                candle_open_time=candle_open_time,
                open_price=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                state=CandleState.RECONCILED,
                received_at=reconciled_at,
                reconciled_at=reconciled_at,
            )
            return CandleUpdateResult(
                action=CandleUpdateAction.INSERTED,
                candle_id=str(candle.id),
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                candle_open_time=candle_open_time,
                revision=candle.revision,
                state=CandleState.RECONCILED,
                meaningful_change=True,
                reason="reconciled new candle",
            )

        existing_state = CandleState(existing.state)
        # Never let stale REST overwrite a FINALIZED candle.
        if existing_state == CandleState.FINALIZED:
            await self.candle_repository.update_state(
                existing,
                state=existing_state,
                reconciled_at=reconciled_at,
                revision=existing.revision,
            )
            return CandleUpdateResult(
                action=CandleUpdateAction.DUPLICATE_IGNORED,
                candle_id=str(existing.id),
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                candle_open_time=candle_open_time,
                revision=existing.revision,
                state=existing_state,
                meaningful_change=False,
                reason="rest cannot overwrite finalized",
            )

        # REST data for a provisional candle: update if meaningfully different.
        if self._same_ohlcv_decimal(existing, open_price, high, low, close, volume):
            await self.candle_repository.update_state(
                existing,
                state=CandleState.RECONCILED,
                reconciled_at=reconciled_at,
                revision=existing.revision,
            )
            return CandleUpdateResult(
                action=CandleUpdateAction.UPDATED,
                candle_id=str(existing.id),
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                candle_open_time=candle_open_time,
                revision=existing.revision,
                state=CandleState.RECONCILED,
                meaningful_change=False,
                reason="reconciled identical",
            )

        await self.revision_repository.add(
            candle_id=str(existing.id),
            revision_number=existing.revision,
            exchange=existing.exchange,
            symbol=existing.symbol,
            timeframe=existing.timeframe,
            candle_open_time=existing.candle_open_time,
            open_price=existing.open,
            high=existing.high,
            low=existing.low,
            close=existing.close,
            volume=existing.volume,
            reason="rest reconciliation changed candle",
            revised_at=reconciled_at,
            raw_payload=None,
        )
        new_revision = existing.revision + 1
        existing.open = open_price
        existing.high = high
        existing.low = low
        existing.close = close
        existing.volume = volume
        existing.state = CandleState.RECONCILED.value
        existing.revision = new_revision
        existing.last_received_at = reconciled_at
        existing.reconciled_at = reconciled_at
        await self.session_add_and_flush(existing)
        return CandleUpdateResult(
            action=CandleUpdateAction.REVISED,
            candle_id=str(existing.id),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            candle_open_time=candle_open_time,
            revision=new_revision,
            state=CandleState.RECONCILED,
            meaningful_change=True,
            reason="rest reconciliation changed",
        )

    # ------------------------------------------------------------------ helpers
    async def session_add_and_flush(self, instance: Any) -> None:
        self.candle_repository.session.add(instance)
        await self.candle_repository.session.flush()

    @staticmethod
    def _same_ohlcv(existing: Any, update: NormalizedCandleUpdate) -> bool:
        return CandleLifecycleEngine._same_ohlcv_decimal(
            existing,
            update.open,
            update.high,
            update.low,
            update.close,
            update.volume,
        )

    @staticmethod
    def _same_ohlcv_decimal(
        existing: Any,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal | None,
    ) -> bool:
        return bool(
            existing.open == open_price
            and existing.high == high
            and existing.low == low
            and existing.close == close
            and existing.volume == volume
        )
