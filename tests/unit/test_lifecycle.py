from datetime import UTC, datetime
from decimal import Decimal

import pytest

from candlecore.core.contracts import CandleState, NormalizedCandleUpdate
from candlecore.market_data.lifecycle import CandleLifecycleEngine, CandleUpdateAction


class FakeCandle:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.id = kwargs.get("id", "candle-1")
        self.candle_open_time = kwargs.get(
            "candle_open_time", datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
        )


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, instance):
        self.added.append(instance)

    async def flush(self):
        pass


class FakeCandleRepository:
    def __init__(self, existing=None):
        self.existing = existing
        self.upserted = []
        self.updated = []
        self.session = FakeSession()

    async def get_by_identity(self, *, exchange, symbol, timeframe, candle_open_time):
        return self.existing

    async def upsert(
        self,
        *,
        exchange,
        symbol,
        timeframe,
        source,
        candle_open_time,
        open_price,
        high,
        low,
        close,
        volume,
        state,
        received_at,
        finalized_at=None,
        reconciled_at=None,
    ):
        candle = FakeCandle(
            id="candle-new",
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            state=state,
            revision=0,
            first_received_at=received_at,
            last_received_at=received_at,
        )
        self.upserted.append(
            {
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "state": state,
                "received_at": received_at,
            }
        )
        return candle, True

    async def update_state(
        self, candle, *, state, finalized_at=None, reconciled_at=None, revision=None
    ):
        candle.state = state
        if finalized_at is not None:
            candle.finalized_at = finalized_at
        if reconciled_at is not None:
            candle.reconciled_at = reconciled_at
        if revision is not None:
            candle.revision = revision
        candle.last_received_at = datetime.now(UTC)
        self.updated.append(candle)
        return candle


class FakeRevisionRepository:
    def __init__(self):
        self.revisions = []

    async def add(
        self,
        *,
        candle_id,
        revision_number,
        exchange,
        symbol,
        timeframe,
        candle_open_time,
        open_price,
        high,
        low,
        close,
        volume,
        reason,
        revised_at,
        raw_payload=None,
    ):
        self.revisions.append(
            {
                "candle_id": candle_id,
                "revision_number": revision_number,
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "reason": reason,
                "revised_at": revised_at,
            }
        )


def _make_update(
    *,
    open_price="100",
    high="110",
    low="90",
    close="105",
    volume="1000",
    symbol="BTCUSD",
    timeframe="3m",
    candle_open_time=None,
):
    if candle_open_time is None:
        candle_open_time = datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
    return NormalizedCandleUpdate(
        exchange="delta",
        symbol=symbol,
        timeframe=timeframe,
        source="exchange_rest",
        candle_open_time=candle_open_time,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        raw_payload={"time": 1700000000},
    )


@pytest.mark.asyncio
async def test_lifecycle_inserts_new_candle():
    candle_repo = FakeCandleRepository(existing=None)
    revision_repo = FakeRevisionRepository()
    engine = CandleLifecycleEngine(candle_repo, revision_repo)

    result = await engine.process_update(_make_update(), source="exchange_rest")

    assert result.action == CandleUpdateAction.INSERTED
    assert result.revision == 0
    assert result.state == CandleState.PROVISIONAL
    assert result.meaningful_change is True
    assert len(revision_repo.revisions) == 0


@pytest.mark.asyncio
async def test_lifecycle_ignores_exact_duplicate():
    existing = FakeCandle(
        id="candle-1",
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("1000"),
        state=CandleState.PROVISIONAL,
        revision=0,
    )
    candle_repo = FakeCandleRepository(existing=existing)
    revision_repo = FakeRevisionRepository()
    engine = CandleLifecycleEngine(candle_repo, revision_repo)

    result = await engine.process_update(_make_update(), source="exchange_rest")

    assert result.action == CandleUpdateAction.DUPLICATE_IGNORED
    assert result.meaningful_change is False
    assert result.reason == "exact duplicate"
    assert len(revision_repo.revisions) == 0


@pytest.mark.asyncio
async def test_lifecycle_revises_changed_candle():
    existing = FakeCandle(
        id="candle-1",
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("1000"),
        state=CandleState.PROVISIONAL,
        revision=0,
    )
    candle_repo = FakeCandleRepository(existing=existing)
    revision_repo = FakeRevisionRepository()
    engine = CandleLifecycleEngine(candle_repo, revision_repo)

    result = await engine.process_update(
        _make_update(open_price="101", close="106"), source="exchange_rest"
    )

    assert result.action == CandleUpdateAction.REVISED
    assert result.revision == 1
    assert result.state == CandleState.PROVISIONAL
    assert result.meaningful_change is True
    assert len(revision_repo.revisions) == 1
    assert revision_repo.revisions[0]["revision_number"] == 0


@pytest.mark.asyncio
async def test_lifecycle_revised_finalized_becomes_corrected():
    existing = FakeCandle(
        id="candle-1",
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("1000"),
        state=CandleState.FINALIZED,
        revision=2,
    )
    candle_repo = FakeCandleRepository(existing=existing)
    revision_repo = FakeRevisionRepository()
    engine = CandleLifecycleEngine(candle_repo, revision_repo)

    result = await engine.process_update(_make_update(open_price="101"), source="exchange_rest")

    assert result.action == CandleUpdateAction.REVISED
    assert result.revision == 3
    assert result.state == CandleState.CORRECTED
    assert len(revision_repo.revisions) == 1
    assert revision_repo.revisions[0]["revision_number"] == 2


@pytest.mark.asyncio
async def test_lifecycle_finalize():
    existing = FakeCandle(
        id="candle-1",
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("1000"),
        state=CandleState.PROVISIONAL,
        revision=0,
    )
    candle_repo = FakeCandleRepository(existing=existing)
    revision_repo = FakeRevisionRepository()
    engine = CandleLifecycleEngine(candle_repo, revision_repo)

    result = await engine.finalize(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        candle_open_time=datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC),
    )

    assert result is not None
    assert result.state == CandleState.FINALIZED
    assert result.reason == "finalized"


@pytest.mark.asyncio
async def test_lifecycle_finalize_missing_returns_none():
    candle_repo = FakeCandleRepository(existing=None)
    revision_repo = FakeRevisionRepository()
    engine = CandleLifecycleEngine(candle_repo, revision_repo)

    result = await engine.finalize(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        candle_open_time=datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC),
    )

    assert result is None
