import logging
import requests

from ethereum.utils import denoms

logger = logging.getLogger(__name__)


def tETH_faucet_donate(addr: str):
    request = "http://188.165.227.180:4000/donate/{}".format(addr)
    resp = requests.get(request)
    response = resp.json()
    if resp.status_code != 200:
        logger.warning(
            "tETH faucet error code %r: %r",
            resp.status_code,
            response,
        )
        return False
    amount = int(response['amount']) / denoms.ether
    logger.info("Faucet: %.6f ETH", amount)
    return True
