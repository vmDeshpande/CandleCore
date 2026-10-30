from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CandleState(StrEnum):
    OPEN = "OPEN"
    PROVISIONAL = "PROVISIONAL"
    FINALIZED = "FINALIZED"
    RECONCILED = "RECONCILED"
    CORRECTED = "CORRECTED"
    INVALID = "INVALID"

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

class IngestionCheckpoint(BaseModel):
    checkpoint_id: UUID = Field(default_factory=uuid4)
    exchange: str = "delta"
    symbol: str
    timeframe: str
    last_processed_time: datetime
    watermark: datetime
    updated_at: datetime

class RecoveryResult(BaseModel):
    success: bool
    symbols_recovered: list[str]
    gaps_filled: int
    candles_restored: int
    errors: list[str] = []
