from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class CandleState(StrEnum):
    OPEN = "OPEN"
    PROVISIONAL = "PROVISIONAL"
    FINALIZED = "FINALIZED"
    RECONCILED = "RECONCILED"
    CORRECTED = "CORRECTED"
    INVALID = "INVALID"


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _validate_ohlcv(
    *,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: Decimal | None,
) -> None:
    prices = (open_price, high, low, close)
    if not all(price.is_finite() for price in prices):
        raise ValueError("prices must be finite")
    if low > high:
        raise ValueError("candle low cannot exceed candle high")
    if low > min(open_price, close) or high < max(open_price, close):
        raise ValueError("candle low/high must contain both open and close")
    if volume is not None and (not volume.is_finite() or volume < 0):
        raise ValueError("candle volume must be a finite, non-negative decimal")


class RawMarketEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    exchange: str = "delta"
    symbol: str
    event_type: str
    source: str
    event_time: datetime
    received_at: datetime
    processed_at: datetime | None = None
    original_timestamp: int | None = None
    original_timestamp_unit: str | None = None
    sequence: int | None = None
    schema_version: int = 1
    payload: dict[str, Any]

    @field_validator("event_time", "received_at", "processed_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _normalize_utc(value)


class NormalizedCandleUpdate(BaseModel):
    exchange: str = "delta"
    symbol: str
    timeframe: str
    source: str
    candle_open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    original_timestamp: int | None = None
    original_timestamp_unit: str | None = None
    raw_payload: dict[str, Any]

    @field_validator("candle_open_time")
    @classmethod
    def normalize_candle_open_time(cls, value: datetime) -> datetime:
        return _normalize_utc(value)  # type: ignore[return-value]

    @model_validator(mode="after")
    def validate_ohlcv(self) -> "NormalizedCandleUpdate":
        _validate_ohlcv(
            open_price=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )
        return self


class CandleObservation(BaseModel):
    exchange: str = "delta"
    symbol: str
    timeframe: str
    source: str
    candle_open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    state: CandleState = CandleState.PROVISIONAL
    revision: int = 0
    first_received_at: datetime
    last_received_at: datetime
    finalized_at: datetime | None = None
    reconciled_at: datetime | None = None

    @field_validator(
        "candle_open_time",
        "first_received_at",
        "last_received_at",
        "finalized_at",
        "reconciled_at",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _normalize_utc(value)

    @model_validator(mode="after")
    def validate_observation(self) -> "CandleObservation":
        _validate_ohlcv(
            open_price=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )
        if self.revision < 0:
            raise ValueError("candle revision cannot be negative")
        if self.last_received_at < self.first_received_at:
            raise ValueError("last_received_at cannot precede first_received_at")
        return self


class DataGap(BaseModel):
    gap_id: UUID = Field(default_factory=uuid4)
    exchange: str = "delta"
    symbol: str
    timeframe: str
    gap_start: datetime
    gap_end: datetime
    detected_at: datetime
    filled_at: datetime | None = None
    fill_status: str = "detected"

    @field_validator("gap_start", "gap_end", "detected_at", "filled_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _normalize_utc(value)

    @model_validator(mode="after")
    def validate_gap(self) -> "DataGap":
        if self.gap_end <= self.gap_start:
            raise ValueError("gap_end must be later than gap_start")
        if self.filled_at is not None and self.filled_at < self.detected_at:
            raise ValueError("filled_at cannot precede detected_at")
        return self


class IngestionCheckpoint(BaseModel):
    checkpoint_id: UUID = Field(default_factory=uuid4)
    exchange: str = "delta"
    symbol: str
    timeframe: str
    last_processed_time: datetime
    watermark: datetime
    updated_at: datetime

    @field_validator("last_processed_time", "watermark", "updated_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_utc(value)  # type: ignore[return-value]


class RecoveryResult(BaseModel):
    success: bool
    symbols_recovered: list[str]
    gaps_filled: int
    candles_restored: int
    errors: list[str] = Field(default_factory=list)
