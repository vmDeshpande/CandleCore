from datetime import datetime
from decimal import Decimal
from typing import Any

from candlecore.core.contracts import NormalizedCandleUpdate
from candlecore.core.decimal_utils import decimal_from_number
from candlecore.core.timestamp import timestamp_to_datetime


def _json_safe(value: Any) -> Any:
    """Return a JSONB-compatible copy while preserving Decimal precision."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported JSON payload type: {type(value).__name__}")


def _validate_ohlcv(
    *,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: Decimal | None,
) -> None:
    values = [open_price, high, low, close]
    if volume is not None:
        values.append(volume)
    for value in values:
        if not value.is_finite():
            raise ValueError(f"non-finite OHLCV value: {value}")
    if high < low:
        raise ValueError(f"high ({high}) < low ({low})")
    if high < open_price or high < close:
        raise ValueError(f"high ({high}) does not contain open/close")
    if low > open_price or low > close:
        raise ValueError(f"low ({low}) does not contain open/close")
    if volume is not None and volume < 0:
        raise ValueError(f"negative volume: {volume}")


def normalize_rest_candle(
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
    source: str,
    candle: dict[str, Any],
    timestamp_unit: str = "seconds",
) -> NormalizedCandleUpdate:
    """Normalize a Delta REST history candle into a domain update.

    The REST `time` field is the candle-open timestamp in the supplied unit.
    """
    candle_time = int(candle["time"])
    update = NormalizedCandleUpdate(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        candle_open_time=timestamp_to_datetime(candle_time, timestamp_unit),  # type: ignore[arg-type]
        open=decimal_from_number(candle["open"]),
        high=decimal_from_number(candle["high"]),
        low=decimal_from_number(candle["low"]),
        close=decimal_from_number(candle["close"]),
        volume=(
            decimal_from_number(candle["volume"]) if candle.get("volume") is not None else None
        ),
        original_timestamp=candle_time,
        original_timestamp_unit=timestamp_unit,
        raw_payload=_json_safe(dict(candle)),
    )
    _validate_ohlcv(
        open_price=update.open,
        high=update.high,
        low=update.low,
        close=update.close,
        volume=update.volume,
    )
    return update


def normalize_ws_message(
    *,
    exchange: str,
    symbol: str,
    timeframe: str,
    source: str,
    message: dict[str, Any],
    timestamp_unit: str = "seconds",
) -> NormalizedCandleUpdate:
    """Normalize a Delta candlestick WebSocket message into a domain update.

    Prefers `cst` (candle start time) for the candle-open time when present,
    falling back to `ts`. The raw value and unit are preserved on the update
    for audit.
    """
    raw_timestamp = message.get("cst") if message.get("cst") is not None else message.get("ts")
    open_price = decimal_from_number(message["o"]) if message.get("o") is not None else Decimal("0")
    high = decimal_from_number(message["h"]) if message.get("h") is not None else Decimal("0")
    low = decimal_from_number(message["l"]) if message.get("l") is not None else Decimal("0")
    close = decimal_from_number(message["c"]) if message.get("c") is not None else Decimal("0")
    volume = decimal_from_number(message["v"]) if message.get("v") is not None else None

    update = NormalizedCandleUpdate(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        candle_open_time=timestamp_to_datetime(int(raw_timestamp), timestamp_unit),  # type: ignore[arg-type]
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        original_timestamp=int(raw_timestamp) if raw_timestamp is not None else None,
        original_timestamp_unit=timestamp_unit,
        raw_payload=_json_safe(dict(message)),
    )
    _validate_ohlcv(
        open_price=update.open,
        high=update.high,
        low=update.low,
        close=update.close,
        volume=update.volume,
    )
    return update
