from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from candlecore.core.contracts import CandleObservation, CandleState, DataGap, RecoveryResult


def make_candle(**overrides: object) -> CandleObservation:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "exchange": "delta",
        "symbol": "BTCUSD",
        "timeframe": "3m",
        "source": "exchange_rest",
        "candle_open_time": now,
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "volume": Decimal("1000"),
        "first_received_at": now,
        "last_received_at": now,
    }
    values.update(overrides)
    return CandleObservation(**values)


def test_candle_observation_defaults_to_provisional() -> None:
    assert make_candle().state == CandleState.PROVISIONAL


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"low": Decimal("106")}, "low/high must contain"),
        ({"high": Decimal("104")}, "low/high must contain"),
        ({"low": Decimal("111"), "high": Decimal("110")}, "low cannot exceed"),
        ({"volume": Decimal("-1")}, "volume must be"),
        ({"open": Decimal("NaN")}, "prices must be finite"),
    ],
)
def test_candle_observation_rejects_invalid_ohlcv(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_candle(**overrides)


def test_candle_observation_normalizes_aware_timestamps_to_utc() -> None:
    timestamp = datetime(2026, 10, 30, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    candle = make_candle(candle_open_time=timestamp)
    assert candle.candle_open_time.tzinfo == UTC


def test_candle_observation_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_candle(candle_open_time=datetime(2026, 10, 30, 12, 0))


def test_data_gap_requires_positive_interval() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="gap_end must be later"):
        DataGap(
            symbol="BTCUSD",
            timeframe="3m",
            gap_start=now,
            gap_end=now,
            detected_at=now,
        )


def test_recovery_result_errors_are_not_shared_between_instances() -> None:
    first = RecoveryResult(
        success=False, symbols_recovered=[], gaps_filled=0, candles_restored=0
    )
    second = RecoveryResult(
        success=False, symbols_recovered=[], gaps_filled=0, candles_restored=0
    )

    first.errors.append("REST unavailable")

    assert second.errors == []


def test_candle_observation_rejects_negative_revision() -> None:
    with pytest.raises(ValidationError, match="revision cannot be negative"):
        make_candle(revision=-1)
