from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from candlecore.api.deps import application_from_request
from candlecore.storage.database import get_db

router = APIRouter()


@router.get("/health")
async def health(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    application = application_from_request(request)

    # Database health.
    db_ok = False
    db_error: str | None = None
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    # Collector health.
    ws = application.ws_client

    def _last_message(symbol: str) -> str | None:
        last = ws.symbol_health(symbol)
        return last.isoformat() if last is not None else None

    per_symbol = {symbol: _last_message(symbol) for symbol in application.settings.symbol_list}

    healthy = db_ok and ws.connection_state == "connected"

    return {
        "status": "healthy" if healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "database": {
            "healthy": db_ok,
            "error": db_error,
        },
        "collector": {
            "connected": ws.is_connected(),
            "connection_state": ws.connection_state,
            "reconnect_attempts": ws.reconnect_attempts,
            "last_successful_connection": (
                ws.last_successful_connection_time.isoformat()
                if ws.last_successful_connection_time is not None
                else None
            ),
            "per_symbol_last_message": per_symbol,
        },
    }
