import asyncio
import contextlib
import json
import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
import websockets

logger = structlog.get_logger()

ConnectionState = str


class DeltaWebSocketClient:
    def __init__(
        self,
        ws_url: str = "wss://public-socket.india.delta.exchange",
        symbols: list[str] | None = None,
        channel: str = "candlestick_3m",
        on_message: Callable[[dict[str, Any]], None] | None = None,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 60.0,
    ) -> None:
        self.ws_url = ws_url
        self.symbols = list(symbols or ["BTCUSD", "ETHUSD", "SOLUSD"])
        self.channel = channel
        self.on_message = on_message
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout

        self.ws: Any = None
        self.running = False
        self.connection_state: ConnectionState = "disconnected"
        self.last_message_time: dict[str, datetime | None] = dict.fromkeys(self.symbols)
        self.last_successful_connection_time: datetime | None = None
        self.last_message_received_at: datetime | None = None
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0
        self.reconnect_attempts = 0
        self._connection_lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ health
    def is_connected(self) -> bool:
        return self.connection_state == "connected" and self.ws is not None

    def symbol_health(self, symbol: str) -> datetime | None:
        return self.last_message_time.get(symbol)

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self.running = True
        while self.running:
            async with self._connection_lock:
                if self.ws is None:
                    await self._connect()
            try:
                await self._run()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("websocket_error", error=str(exc))
            # The read loop ended (normal or abnormal closure). Reconnect if running.
            if self.running:
                await self._reconnect()

    async def _connect(self) -> None:
        self.connection_state = "connecting"
        self.ws = await websockets.connect(self.ws_url)
        self.connection_state = "connected"
        self.last_successful_connection_time = datetime.now(UTC)
        self.last_message_received_at = datetime.now(UTC)
        self.reconnect_attempts = 0
        self.reconnect_delay = 1.0
        await self._subscribe()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        logger.info("websocket_connected", url=self.ws_url)

    async def _subscribe(self) -> None:
        if self.ws is None:
            return
        subscribe_msg = {
            "type": "subscribe",
            "payload": {
                "channels": [{"name": self.channel, "symbols": self.symbols}],
            },
        }
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info("subscribed", channel=self.channel, symbols=self.symbols)

    async def _run(self) -> None:
        assert self.ws is not None
        async for message in self.ws:
            self.last_message_received_at = datetime.now(UTC)
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                logger.warning("invalid_json_message", message=str(message)[:100])
                continue
            except Exception as exc:
                logger.error("message_parse_error", error=str(exc))
                continue

            self._handle_message(data)

            if self.on_message is not None:
                if asyncio.iscoroutinefunction(self.on_message):
                    await self.on_message(data)
                else:
                    self.on_message(data)

    def _handle_message(self, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("unexpected_message", message=str(data)[:100])
            return

        message_type = data.get("type")
        if message_type in {"pong", "subscribed", "subscription", "ack", "heartbeat"}:
            if message_type == "heartbeat":
                logger.debug("heartbeat_received")
            return

        symbol = self._extract_symbol(data)
        if symbol is not None and symbol in self.symbols:
            # Only the identified symbol's last-message time is updated.
            self.last_message_time[symbol] = datetime.now(UTC)
            logger.debug(
                "market_message",
                symbol=symbol,
                channel=message_type or self.channel,
            )
        else:
            logger.warning("unknown_or_unidentified_symbol", message=str(data)[:200])

    def _extract_symbol(self, data: dict[str, Any]) -> str | None:
        for key in ("symbol", "sy", "product_symbol", "instrument"):
            value = data.get(key)
            if isinstance(value, str) and value:
                symbol = value.upper()
                if symbol in self.symbols:
                    return symbol
        payload = data.get("payload")
        if isinstance(payload, dict):
            for key in ("symbol", "sy"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    symbol = value.upper()
                    if symbol in self.symbols:
                        return symbol
        return None

    async def _heartbeat_monitor(self) -> None:
        while self.running and self.is_connected():
            await asyncio.sleep(self.heartbeat_interval)
            if self.last_message_received_at is None:
                continue
            idle = (datetime.now(UTC) - self.last_message_received_at).total_seconds()
            if idle > self.heartbeat_timeout:
                logger.warning(
                    "heartbeat_timeout",
                    idle_seconds=idle,
                    timeout=self.heartbeat_timeout,
                )
                await self._force_reconnect()
                return

    async def _reconnect(self) -> None:
        await self._close_websocket()
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay, self.max_reconnect_delay)
        # Bounded exponential backoff with jitter (50%-100% of delay).
        sleep_for = delay * (0.5 + 0.5 * random.random())
        logger.warning(
            "reconnecting",
            attempt=self.reconnect_attempts,
            delay_seconds=sleep_for,
        )
        await asyncio.sleep(sleep_for)
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _force_reconnect(self) -> None:
        await self._close_websocket()
        # The outer start() loop will detect ws is None and reconnect.

    async def _close_websocket(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self.ws is not None:
            with contextlib.suppress(Exception):
                await self.ws.close()
            self.ws = None
        self.connection_state = "disconnected"

    async def stop(self) -> None:
        self.running = False
        await self._close_websocket()
