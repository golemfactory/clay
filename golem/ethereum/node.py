import logging
import time

from typing import List

from web3 import Web3

from golem.ethereum.web3.providers import ProviderProxy
from golem.report import report_calls, Component

logger = logging.getLogger(__name__)


class NodeProcess(object):
    def __init__(self, addresses: List[str]) -> None:
        """
        :param addr: address of a geth instance to connect with
        """
        self.provider_proxy = ProviderProxy(addresses)
        self.web3 = Web3(self.provider_proxy)

    @report_calls(Component.ethereum, 'node.start')
    def start(self):
        started = time.time()
        self.web3.isConnected()
        logger.info("Connected to node in %ss", time.time() - started)
        return None
