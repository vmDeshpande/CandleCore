from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from candlecore.api.deps import application_from_request
from candlecore.storage.database import get_db

router = APIRouter()


def _parse_instant(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        # Fall back to Unix seconds.
        return datetime.fromtimestamp(float(value), tz=UTC)


@router.get("/market/status")
async def market_status(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    application = application_from_request(request)
    settings = application.settings
    ws = application.ws_client

    per_symbol = {}
    for symbol in settings.symbol_list:
        last = ws.symbol_health(symbol)
        per_symbol[symbol] = last.isoformat() if last is not None else None

    # Latest stored candle per symbol/timeframe.
    candle_repo = application.build_services(session)["candle"]
    latest_candle: dict[str, Any] = {}
    for symbol in settings.symbol_list:
        for timeframe in settings.timeframe_list:
            candles = await candle_repo.list_candles(
                exchange="delta",
                symbol=symbol,
                timeframe=timeframe,
                limit=1,
            )
            if candles:
                latest_candle[f"{symbol}:{timeframe}"] = candles[0].candle_open_time.isoformat()

    # Recovery status.
    gap_repo = application.build_services(session)["gap"]
    unfilled = await gap_repo.list_unfilled(exchange="delta")
    recovery = {
        "unfilled_gaps": len(unfilled),
        "gaps": [
            {
                "symbol": g.symbol,
                "timeframe": g.timeframe,
                "gap_start": g.gap_start.isoformat(),
                "gap_end": g.gap_end.isoformat(),
                "fill_status": g.fill_status,
            }
            for g in unfilled[:50]
        ],
    }

    return {
        "exchange": "delta",
        "symbols": settings.symbol_list,
        "collection_intervals": settings.timeframe_list,
        "connection_status": "connected" if ws.is_connected() else "disconnected",
        "connection_state": ws.connection_state,
        "per_symbol_last_message": per_symbol,
        "ingestion_progress": {},
        "latest_stored_candle": latest_candle,
        "recovery": recovery,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/market/candles")
async def get_candles(
    request: Request,
    symbol: str = Query(...),
    timeframe: str = Query(default="3m"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    application = application_from_request(request)
    settings = application.settings

    if symbol not in settings.symbol_list:
        return {"error": f"unsupported symbol: {symbol}", "candles": [], "count": 0}
    if timeframe not in settings.timeframe_list:
        return {
            "error": f"unsupported timeframe: {timeframe}",
            "candles": [],
            "count": 0,
        }

    start_dt = _parse_instant(start)
    end_dt = _parse_instant(end)

    candle_repo = application.build_services(session)["candle"]
    candles = await candle_repo.list_candles(
        exchange="delta",
        symbol=symbol,
        timeframe=timeframe,
        start=start_dt,
        end=end_dt,
        limit=limit,
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": [
            {
                "candle_open_time": c.candle_open_time.isoformat(),
                "open": str(c.open),
                "high": str(c.high),
                "low": str(c.low),
                "close": str(c.close),
                "volume": str(c.volume) if c.volume is not None else None,
                "state": c.state,
                "revision": c.revision,
            }
            for c in candles
        ],
        "count": len(candles),
    }


@router.get("/market/gaps")
async def get_gaps(
    request: Request,
    symbol: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
    fill_status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    application = application_from_request(request)
    gap_repo = application.build_services(session)["gap"]

    gaps = await gap_repo.list_unfilled(exchange="delta", symbol=symbol, timeframe=timeframe)

    if fill_status is not None:
        gaps = [g for g in gaps if g.fill_status == fill_status]

    return {
        "gaps": [
            {
                "symbol": g.symbol,
                "timeframe": g.timeframe,
                "gap_start": g.gap_start.isoformat(),
                "gap_end": g.gap_end.isoformat(),
                "detected_at": g.detected_at.isoformat(),
                "filled_at": g.filled_at.isoformat() if g.filled_at else None,
                "fill_status": g.fill_status,
            }
            for g in gaps
        ],
        "count": len(gaps),
    }
