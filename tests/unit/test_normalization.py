from datetime import UTC, datetime
from decimal import Decimal

import pytest

from candlecore.core.timestamp import timestamp_to_datetime
from candlecore.market_data.normalization import (
    normalize_rest_candle,
    normalize_ws_message,
)


def test_timestamp_seconds() -> None:
    dt = timestamp_to_datetime(1700000000, "seconds")
    assert dt.tzinfo is UTC
    assert dt == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_timestamp_milliseconds() -> None:
    dt = timestamp_to_datetime(1700000000000, "milliseconds")
    assert dt == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_timestamp_microseconds() -> None:
    dt = timestamp_to_datetime(1700000000000000, "microseconds")
    assert dt == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_normalize_rest_candle() -> None:
    candle = {
        "time": 1700000000,
        "open": "100.5",
        "high": "110.0",
        "low": "90.0",
        "close": "105.0",
        "volume": "1000.0",
    }
    update = normalize_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle=candle,
        timestamp_unit="seconds",
    )
    assert update.symbol == "BTCUSD"
    assert update.timeframe == "3m"
    assert update.open == Decimal("100.5")
    assert update.high == Decimal("110.0")
    assert update.low == Decimal("90.0")
    assert update.close == Decimal("105.0")
    assert update.volume == Decimal("1000.0")
    assert update.original_timestamp == 1700000000
    assert update.original_timestamp_unit == "seconds"
    assert update.raw_payload == candle


def test_normalize_rest_candle_volume_none() -> None:
    candle = {
        "time": 1700000000,
        "open": "100",
        "high": "110",
        "low": "90",
        "close": "105",
        "volume": None,
    }
    update = normalize_rest_candle(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_rest",
        candle=candle,
        timestamp_unit="seconds",
    )
    assert update.volume is None


def test_normalize_ws_message_uses_cst() -> None:
    message = {
        "sy": "BTCUSD",
        "res": "3m",
        "cst": 1700000000,
        "ts": 1700000005,
        "o": "100",
        "h": "110",
        "l": "90",
        "c": "105",
        "v": "1000",
    }
    update = normalize_ws_message(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_websocket",
        message=message,
        timestamp_unit="seconds",
    )
    # candle_open_time prefers cst
    assert update.candle_open_time == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert update.original_timestamp == 1700000000


def test_normalize_ws_message_falls_back_to_ts() -> None:
    message = {
        "sy": "BTCUSD",
        "res": "3m",
        "ts": 1700000000,
        "o": "100",
        "h": "110",
        "l": "90",
        "c": "105",
    }
    update = normalize_ws_message(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_websocket",
        message=message,
        timestamp_unit="seconds",
    )
    assert update.candle_open_time == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert update.original_timestamp == 1700000000


def test_normalize_ws_message_preserves_raw_payload() -> None:
    message = {"sy": "BTCUSD", "ts": 1700000000, "o": "100", "h": "110", "l": "90", "c": "105"}
    update = normalize_ws_message(
        exchange="delta",
        symbol="BTCUSD",
        timeframe="3m",
        source="exchange_websocket",
        message=message,
        timestamp_unit="seconds",
    )
    assert update.raw_payload == message


def test_normalize_rejects_invalid_ohlcv() -> None:
    candle = {
        "time": 1700000000,
        "open": "105",
        "high": "110",
        "low": "111",  # low > high and > close
        "close": "100",
        "volume": "1000",
    }
    with pytest.raises(ValueError):
        normalize_rest_candle(
            exchange="delta",
            symbol="BTCUSD",
            timeframe="3m",
            source="exchange_rest",
            candle=candle,
            timestamp_unit="seconds",
        )
