from candlecore.exchange.delta.rest_client import DeltaRestClient, RateLimitedError


def test_rest_client_imports():
    assert DeltaRestClient is not None
    assert RateLimitedError is not None
