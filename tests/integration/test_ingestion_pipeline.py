from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from candlecore.application.ingestion import IngestionService
from candlecore.core.contracts import NormalizedCandleUpdate
from candlecore.market_data.lifecycle import CandleLifecycleEngine
from candlecore.storage.models import Candle, CandleRevision, RawMarketEvent
from candlecore.storage.repositories import (
    CandleRepository,
    CandleRevisionRepository,
    IngestionCheckpointRepository,
    RawMarketEventRepository,
)


def _update(open_price="100", high="110", low="90", close="105", volume="1000", t=None):
    if t is None:
        t = datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
    return NormalizedCandleUpdate(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle_open_time=t,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        raw_payload={"time": int(t.timestamp())},
    )


@pytest.mark.asyncio
async def test_rest_backfill_persists_raw_event_and_candle(pg_session):
    raw_repo = RawMarketEventRepository(pg_session)
    candle_repo = CandleRepository(pg_session)
    revision_repo = CandleRevisionRepository(pg_session)
    checkpoint_repo = IngestionCheckpointRepository(pg_session)
    engine = CandleLifecycleEngine(candle_repo, revision_repo)
    service = IngestionService(
        candle_repository=candle_repo,
        revision_repository=revision_repo,
        raw_event_repository=raw_repo,
        checkpoint_repository=checkpoint_repo,
        lifecycle_engine=engine,
    )

    await service.ingest_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle={
            "time": 1700000000,
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "1000",
        },
        timestamp_unit="seconds",
    )
    await pg_session.commit()

    # Raw event persisted
    result = await pg_session.execute(select(RawMarketEvent))
    raw_events = result.scalars().all()
    assert len(raw_events) == 1
    assert raw_events[0].symbol == "BTCUSD"

    # Candle persisted
    result = await pg_session.execute(select(Candle))
    candles = result.scalars().all()
    assert len(candles) == 1
    assert candles[0].symbol == "BTCUSD"
    assert candles[0].state == "PROVISIONAL"
    assert candles[0].revision == 0


@pytest.mark.asyncio
async def test_duplicate_ingestion_ignored(pg_session):
    raw_repo = RawMarketEventRepository(pg_session)
    candle_repo = CandleRepository(pg_session)
    revision_repo = CandleRevisionRepository(pg_session)
    checkpoint_repo = IngestionCheckpointRepository(pg_session)
    engine = CandleLifecycleEngine(candle_repo, revision_repo)
    service = IngestionService(
        candle_repository=candle_repo,
        revision_repository=revision_repo,
        raw_event_repository=raw_repo,
        checkpoint_repository=checkpoint_repo,
        lifecycle_engine=engine,
    )

    t = datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
    await service.ingest_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle={
            "time": int(t.timestamp()),
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "1000",
        },
        timestamp_unit="seconds",
    )
    await service.ingest_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle={
            "time": int(t.timestamp()),
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "1000",
        },
        timestamp_unit="seconds",
    )
    await pg_session.commit()

    result = await pg_session.execute(select(Candle))
    candles = result.scalars().all()
    assert len(candles) == 1  # duplicate ignored, not doubled


@pytest.mark.asyncio
async def test_revision_preserved_on_change(pg_session):
    raw_repo = RawMarketEventRepository(pg_session)
    candle_repo = CandleRepository(pg_session)
    revision_repo = CandleRevisionRepository(pg_session)
    checkpoint_repo = IngestionCheckpointRepository(pg_session)
    engine = CandleLifecycleEngine(candle_repo, revision_repo)
    service = IngestionService(
        candle_repository=candle_repo,
        revision_repository=revision_repo,
        raw_event_repository=raw_repo,
        checkpoint_repository=checkpoint_repo,
        lifecycle_engine=engine,
    )

    t = datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
    await service.ingest_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle={
            "time": int(t.timestamp()),
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "1000",
        },
        timestamp_unit="seconds",
    )
    await service.ingest_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle={
            "time": int(t.timestamp()),
            "open": "101",
            "high": "111",
            "low": "91",
            "close": "106",
            "volume": "1100",
        },
        timestamp_unit="seconds",
    )
    await pg_session.commit()

    result = await pg_session.execute(select(Candle))
    candle = result.scalars().one()
    assert candle.open == Decimal("101")
    assert candle.revision == 1

    result = await pg_session.execute(
        select(CandleRevision).where(CandleRevision.candle_id == candle.id)
    )
    revisions = result.scalars().all()
    assert len(revisions) == 1
    assert revisions[0].revision_number == 0
    assert revisions[0].open == Decimal("100")
