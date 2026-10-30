from datetime import UTC, datetime
from typing import Literal

TimestampUnit = Literal["seconds", "milliseconds", "microseconds", "nanoseconds"]

DIVISORS: dict[TimestampUnit, int] = {
    "seconds": 1,
    "milliseconds": 1_000,
    "microseconds": 1_000_000,
    "nanoseconds": 1_000_000_000,
}


def timestamp_to_datetime(value: int | float, unit: TimestampUnit = "seconds") -> datetime:
    """Convert an exchange timestamp and its unit to a timezone-aware UTC datetime.

    The unit must be supplied explicitly; it is never inferred from magnitude.
    """
    divisor = DIVISORS[unit]
    return datetime.fromtimestamp(value / divisor, tz=UTC)
