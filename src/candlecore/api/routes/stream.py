import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[tuple[WebSocket, str, str]] = []

    async def connect(self, websocket: WebSocket, symbol: str, timeframe: str) -> None:
        await websocket.accept()
        self.active_connections.append((websocket, symbol, timeframe))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections = [
            (ws, s, t) for ws, s, t in self.active_connections if ws != websocket
        ]

    async def broadcast(self, message: dict[str, Any]) -> None:
        symbol = message.get("symbol")
        timeframe = message.get("timeframe")
        for connection in self.active_connections[:]:
            ws, s, t = connection
            if symbol and timeframe and (s != symbol or t != timeframe):
                continue
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/market")
async def market_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket, "BTCUSD", "3m")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "subscribe":
                    symbol = str(msg.get("symbol", "BTCUSD")).upper()
                    timeframe = str(msg.get("timeframe", "3m"))
                    manager.active_connections = [
                        (ws, symbol, timeframe) if ws == websocket else (ws, s, t)
                        for ws, s, t in manager.active_connections
                    ]
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
