from decimal import Decimal

from candlecore.exchange.delta.schemas import DeltaRestCandle


def test_delta_rest_candle_parsing():
    candle = DeltaRestCandle(time=1700000000, open=100, high=110, low=90, close=105, volume=1000)
    assert candle.open == Decimal("100")
    assert candle.time == 1700000000
