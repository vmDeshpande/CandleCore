import asyncio
import json
from unittest.mock import MagicMock

from candlecore.exchange.delta.ws_client import DeltaWebSocketClient


def _make_ws_client(symbols=None):
    return DeltaWebSocketClient(symbols=symbols or ["BTCUSD", "ETHUSD", "SOLUSD"])


class FakeWebSocket:
    def __init__(self, messages=None, close_code=None):
        self.messages = list(messages or [])
        self.sent = []
        self.closed = False
        self.close_code = close_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.messages:
            return self.messages.pop(0)
        if self.closed:
            raise StopAsyncIteration
        # Wait a bit then stop to avoid blocking tests
        await asyncio.sleep(0.05)
        raise StopAsyncIteration

    async def send(self, message):
        self.sent.append(message)

    async def close(self):
        self.closed = True


def test_ws_per_symbol_health_only_updates_identified_symbol():
    client = _make_ws_client()
    assert client.symbol_health("BTCUSD") is None
    assert client.symbol_health("ETHUSD") is None

    msg = json.loads(
        json.dumps(
            {"sy": "BTCUSD", "ts": 1700000000, "o": "100", "h": "110", "l": "90", "c": "105"}
        )
    )
    client._handle_message(msg)

    assert client.symbol_health("BTCUSD") is not None
    assert client.symbol_health("ETHUSD") is None
    assert client.symbol_health("SOLUSD") is None


def test_ws_unknown_symbol_does_not_update_health():
    client = _make_ws_client()
    msg = json.loads(json.dumps({"sy": "UNKNOWN", "ts": 1700000000}))
    client._handle_message(msg)
    for sym in client.symbols:
        assert client.symbol_health(sym) is None


def test_ws_unexpected_message_handled_without_crash():
    client = _make_ws_client()
    # Non-dict message
    client._handle_message("not-a-json-dict")
    assert client.is_connected() is False


def test_ws_subscribe_message_sent():
    client = _make_ws_client()
    ws = FakeWebSocket()
    client.ws = ws
    asyncio.run(client._subscribe())
    assert len(ws.sent) == 1
    assert "subscribe" in ws.sent[0]
    assert "BTCUSD" in ws.sent[0]


def test_ws_is_connected_states():
    client = _make_ws_client()
    assert client.is_connected() is False
    client.connection_state = "connected"
    client.ws = MagicMock()
    assert client.is_connected() is True
    client.connection_state = "disconnected"
    assert client.is_connected() is False


def test_ws_connection_state_transitions():
    client = _make_ws_client()
    assert client.connection_state == "disconnected"
    client.connection_state = "connecting"
    assert client.connection_state == "connecting"
    client.connection_state = "connected"
    assert client.is_connected() is False  # ws is None


def test_ws_extract_symbol_from_top_level():
    client = _make_ws_client()
    assert client._extract_symbol({"symbol": "BTCUSD"}) == "BTCUSD"
    assert client._extract_symbol({"sy": "ETHUSD"}) == "ETHUSD"


def test_ws_extract_symbol_from_payload():
    client = _make_ws_client()
    assert client._extract_symbol({"payload": {"sy": "SOLUSD"}}) == "SOLUSD"


def test_ws_extract_symbol_unknown_returns_none():
    client = _make_ws_client()
    assert client._extract_symbol({"symbol": "UNKNOWN"}) is None
    assert client._extract_symbol({}) is None


def test_ws_stop_sets_running_false():
    client = _make_ws_client()
    client.running = True
    asyncio.run(client.stop())
    assert client.running is False
