from candlecore.core.contracts import CandleObservation, CandleState
from datetime import datetime, timezone
from decimal import Decimal

def test_candle_observation():
    obs = CandleObservation(
        exchange='delta',
        symbol='BTCUSD',
        timeframe='3m',
        source='exchange_rest',
        candle_open_time=datetime.now(timezone.utc),
        open=Decimal('100'),
        high=Decimal('110'),
        low=Decimal('90'),
        close=Decimal('105'),
        volume=Decimal('1000'),
        first_received_at=datetime.now(timezone.utc),
        last_received_at=datetime.now(timezone.utc)
    )
    assert obs.state == CandleState.PROVISIONAL
