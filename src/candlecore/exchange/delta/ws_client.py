import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
import websockets

logger = structlog.get_logger()

class DeltaWebSocketClient:
    def __init__(
        self,
        ws_url: str = "wss://public-socket.india.delta.exchange",
        symbols: list[str] | None = None,
        channel: str = "candlestick_3m",
        on_message: Callable[[dict[str, Any]], None] | None = None
    ):
        self.ws_url = ws_url
        self.symbols = symbols or ["BTCUSD", "ETHUSD", "SOLUSD"]
        self.channel = channel
        self.on_message = on_message
        self.ws = None
        self.running = False
        self.last_message_time = {}
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60
        
    async def connect(self):
        self.ws = await websockets.connect(self.ws_url)
        await self.subscribe()
        logger.info("websocket_connected", url=self.ws_url)
        
    async def subscribe(self):
        if not self.ws:
            return
        subscribe_msg = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": self.channel,
                        "symbols": self.symbols
                    }
                ]
            }
        }
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info("subscribed", channel=self.channel, symbols=self.symbols)
        
    async def start(self):
        self.running = True
        while self.running:
            try:
                if not self.ws:
                    await self.connect()
                async for message in self.ws:
                    try:
                        data = json.loads(message)
                        for symbol in self.symbols:
                            self.last_message_time[symbol] = datetime.now(UTC)
                        if self.on_message:
                            if asyncio.iscoroutinefunction(self.on_message):
                                await self.on_message(data)
                            else:
                                self.on_message(data)
                        self.reconnect_delay = 1
                    except json.JSONDecodeError:
                        logger.warning("invalid_json_message", message=message[:100])
                    except Exception as e:
                        logger.error("message_processing_error", error=str(e))
            except Exception as e:
                logger.error("websocket_error", error=str(e))
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                    self.ws = None
    
    async def stop(self):
        self.running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
