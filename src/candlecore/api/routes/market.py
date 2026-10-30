from datetime import UTC, datetime

from fastapi import APIRouter, Query

router = APIRouter()

@router.get("/market/status")
async def market_status():
    return {
        "status": "ok",
        "exchange": "delta",
        "symbols": ["BTCUSD", "ETHUSD", "SOLUSD"],
        "timeframes": ["3m"],
        "timestamp": datetime.now(UTC).isoformat()
    }

@router.get("/market/candles")
async def get_candles(
    symbol: str = Query(...),
    timeframe: str = Query(default="3m"),
    limit: int = Query(default=100, le=1000)
):
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": [],
        "count": 0
    }

@router.get("/market/gaps")
async def get_gaps(
    symbol: str | None = None,
    timeframe: str = "3m"
):
    return {
        "gaps": [],
        "count": 0
    }
