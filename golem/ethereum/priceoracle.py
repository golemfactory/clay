import logging
import requests
from decimal import Decimal
from datetime import datetime, timedelta

from golem.transactions.service import Service

log = logging.getLogger("golem.srv.price")


class PriceOracle(Service):
    # FIXME: BRASS: don't update price too often, it's an unnecessary distraction.
    # Around once a day should be enough.
    UPDATE_PERIOD = timedelta(0, 15*60)

    def __init__(self):
        self.__gnt_usd = Decimal()
        self.__eth_usd = Decimal()
        self.__last_update = datetime.min
        super(PriceOracle, self).__init__(interval=60)

    @staticmethod
    def __fetch_price(token_name):
        url = 'https://api.coinmarketcap.com/v1/ticker/{}/'.format(token_name)
        r = requests.get(url)
        r.raise_for_status()
        return Decimal(r.json()[0]['price_usd'])

    @property
    def up_to_date(self):
        # We use double update period to give the service a chance to finish
        # the just-about update.
        limit = datetime.utcnow() - 2 * self.UPDATE_PERIOD
        return self.__last_update > limit

    @property
    def gnt_usd(self):
        if not self.up_to_date:
            log.error("GNT price is not up to date")
            return None
        return self.__gnt_usd

    @property
    def eth_usd(self):
        if not self.up_to_date:
            log.error("ETH price is not up to date")
            return None
        return self.__eth_usd

    def update_prices(self):
        try:
            self.__gnt_usd = self.__fetch_price('golem-network-tokens')
            self.__eth_usd = self.__fetch_price('ethereum')
            self.__last_update = datetime.utcnow()
        except requests.exceptions.ConnectionError:
            log.warning("Failed to retrieve crypto prices from api.coinmarketcap.com")
            pass

    def _run(self):
        deadline = self.__last_update + self.UPDATE_PERIOD
        if datetime.utcnow() > deadline:
            self.update_prices()
