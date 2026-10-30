from decimal import Decimal
from typing import Any


def decimal_from_number(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, (int, float)):
        # Use string representation to avoid float precision issues
        return Decimal(str(value))
    raise ValueError(f"Cannot convert {type(value)} to Decimal")
