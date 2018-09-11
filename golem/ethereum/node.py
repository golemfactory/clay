import logging
import time

from typing import List

from web3 import Web3, HTTPProvider

from golem.ethereum.web3.middleware import RemoteRPCErrorMiddlewareBuilder
from golem.ethereum.web3.providers import ProviderProxy
from golem.report import report_calls, Component

log = logging.getLogger(__name__)


class NodeProcess(object):

    CONNECTION_TIMEOUT = 10

    def __init__(self, addresses: List[str]) -> None:
        """
        :param addr: address of a geth instance to connect with
        """
        self.provider_proxy = ProviderProxy()  # web3 ipc / rpc provider
        self.web3 = Web3(self.provider_proxy)
        middleware_builder = RemoteRPCErrorMiddlewareBuilder(
            self._handle_remote_rpc_provider_failure)
        self.web3.middleware_stack.add(middleware_builder.build)

        self.initial_addr_list = addresses
        self.addr_list = None

    @report_calls(Component.ethereum, 'node.start')
    def start(self):
        if not self.addr_list:
            self.addr_list = self.initial_addr_list.copy()

        self.provider_proxy.provider = self._create_remote_rpc_provider()

        started = time.time()
        deadline = started + self.CONNECTION_TIMEOUT

        while not self.is_connected():
            if time.time() > deadline:
                return self.start()
            time.sleep(0.1)

        log.info("Connected to node in %ss", time.time() - started)
        return None

    def is_connected(self):
        try:
            return self.web3.isConnected()
        except AssertionError:  # thrown if not all required APIs are available
            return False

    def _create_remote_rpc_provider(self):
        addr = self.addr_list.pop()
        log.info('GETH: connecting to remote RPC interface at %s', addr)
        return ProviderProxy(HTTPProvider(addr))

    def _handle_remote_rpc_provider_failure(self):
        from golem.core.async import async_run, AsyncRequest
        log.warning('GETH: reconnecting to another provider')
        self.provider_proxy.provider = None

        request = AsyncRequest(self.start)
        async_run(request).addErrback(
            lambda err: self._handle_remote_rpc_provider_failure()
        )
