from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DeltaRestCandle(BaseModel):
    time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None

    @field_validator("open", "high", "low", "close", mode="before")
    @classmethod
    def parse_decimal(cls, v: Any) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("volume", mode="before")
    @classmethod
    def parse_volume(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class DeltaRestResponse(BaseModel):
    success: bool
    result: list[DeltaRestCandle]


class DeltaWsCandleMessage(BaseModel):
    type: str | None = None
    symbol: str | None = Field(default=None, alias="sy")
    resolution: str | None = Field(default=None, alias="res")
    open: Decimal | None = Field(default=None, alias="o")
    high: Decimal | None = Field(default=None, alias="h")
    low: Decimal | None = Field(default=None, alias="l")
    close: Decimal | None = Field(default=None, alias="c")
    volume: Decimal | None = Field(default=None, alias="v")
    timestamp: int | None = Field(default=None, alias="ts")
    candle_start_time: int | None = Field(default=None, alias="cst")

    class Config:
        populate_by_name = True

    @field_validator("open", "high", "low", "close", "volume", mode="before")
    @classmethod
    def parse_decimal_optional(cls, v: Any) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))
