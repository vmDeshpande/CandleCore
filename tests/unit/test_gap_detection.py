from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from candlecore.application.gap_recovery import GapRecoveryService


def _make_gap_recovery(clock=None):
    rest_client = AsyncMock()
    candle_repo = AsyncMock()
    gap_repo = AsyncMock()
    checkpoint_repo = AsyncMock()
    return (
        GapRecoveryService(
            rest_client=rest_client,
            candle_repository=candle_repo,
            gap_repository=gap_repo,
            checkpoint_repository=checkpoint_repo,
            clock=clock,
        ),
        rest_client,
        candle_repo,
        gap_repo,
        checkpoint_repo,
    )


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def test_detect_gaps_finds_missing_intervals():
    now = datetime(2023, 11, 14, 22, 10, 0, tzinfo=UTC)
    start = datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
    end = datetime(2023, 11, 14, 22, 10, 0, tzinfo=UTC)
    svc, *_ = _make_gap_recovery(clock=lambda: now)

    # Existing candles at 22:00 and 22:09; missing 22:03 and 22:06.
    existing = [
        {"time": _ts(start)},
        {"time": _ts(start + timedelta(minutes=9))},
    ]
    gaps = svc.detect_gaps(
        symbol="BTCUSD",
        timeframe="3m",
        start=start,
        end=end,
        existing_candles=existing,
    )
    expected = [
        (start + timedelta(minutes=3), start + timedelta(minutes=6)),
        (start + timedelta(minutes=6), start + timedelta(minutes=9)),
    ]
    assert gaps == expected


def test_detect_gaps_excludes_incomplete_current_interval():
    now = datetime(2023, 11, 14, 22, 5, 0, tzinfo=UTC)
    start = datetime(2023, 11, 14, 22, 0, 0, tzinfo=UTC)
    end = datetime(2023, 11, 14, 23, 0, 0, tzinfo=UTC)
    svc, *_ = _make_gap_recovery(clock=lambda: now)

    existing = [{"time": _ts(start)}]
    gaps = svc.detect_gaps(
        symbol="BTCUSD",
        timeframe="3m",
        start=start,
        end=end,
        existing_candles=existing,
    )
    # The 22:03 interval is not complete (ends 22:06 > now 22:05), so not a gap.
    assert gaps == []


def test_detect_gaps_unsupported_timeframe_raises():
    svc, *_ = _make_gap_recovery()
    with pytest.raises(ValueError):
        svc._interval_seconds("99m")
