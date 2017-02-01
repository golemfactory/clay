import pytest
from mock import patch
from decimal import Decimal
from datetime import timedelta
from time import sleep
from golem.ethereum.priceoracle import PriceOracle


@pytest.fixture
def po():
    from twisted.internet.task import Clock
    srv = PriceOracle()
    clock = Clock()
    srv._loopingCall.clock = clock
    srv.clock = clock
    yield srv
    if srv.running:
        srv.stop()


class FakeResponse(object):
    GNT_USD = "0.0271178"
    ETH_USD = "10.737"

    def __init__(self, url):
        if url == 'https://api.coinmarketcap.com/v1/ticker/golem-network-tokens/':
            self.d = [{"price_usd": self.GNT_USD}]
        elif url == 'https://api.coinmarketcap.com/v1/ticker/ethereum/':
            self.d = [{"price_usd": self.ETH_USD}]
        else:
            raise IOError("bad request: {}".format(url))

    def raise_for_status(self):
        return None

    def json(self):
        return self.d


@patch('requests.get')
def test_price_oracle_update(requests_get, po):
    requests_get.side_effect = lambda url: FakeResponse(url)
    assert not po.up_to_date
    po.update_prices()
    assert po.up_to_date
    assert po.gnt_usd == Decimal('0.0271178')
    assert po.eth_usd == Decimal('10.737')


def test_price_oracle_up_to_date(po):
    assert not po.up_to_date
    with pytest.raises(IOError):
        po.gnt_usd
    with pytest.raises(IOError):
        po.eth_usd


@patch('requests.get')
def test_price_oracle_service(requests_get, po):
    requests_get.side_effect = lambda url: FakeResponse(url)
    po.start()
    assert po.gnt_usd == Decimal('0.0271178')
    assert po.eth_usd == Decimal('10.737')

    po.clock.advance(1)  # Allow the service to do nothing.

    FakeResponse.GNT_USD = "1.11111111"
    FakeResponse.ETH_USD = "0.00000000001"
    orig_update_period = po.UPDATE_PERIOD
    po.UPDATE_PERIOD = timedelta.resolution  # Temporary set minimal period.
    sleep(0.001)
    po.clock.advance(1)
    po.UPDATE_PERIOD = orig_update_period
    assert po.gnt_usd == Decimal(FakeResponse.GNT_USD)


def test_price_oracle_service_live(po):
    # In this test we actually request live data.
    po.start()
    assert po.gnt_usd > 0.001
    assert po.eth_usd > 0.01
    po.stop()
