import logging
import socket

from typing import Optional

from web3.exceptions import CannotHandleRequest
from web3.providers.rpc import HTTPProvider

logger = logging.getLogger(__name__)

RETRIES = 3

class ProviderProxy(HTTPProvider):

    def __init__(self, initial_addr_list) -> None:
        super().__init__()
        self.initial_addr_list = initial_addr_list
        self.addr_list = initial_addr_list
        self.provider = self._create_remote_rpc_provider()

        self._retries = RETRIES
        self._cur_errors = 0

    def make_request(self, method, params):
        logger.debug('ProviderProxy.make_request(%r, %r)', method, params)

        response = None
        while response is None:
            try:
                response = self.provider.make_request(method, params)
                logger.debug('ProviderProxy.make_request(..) -- result = %r',
                             response)
            except (ConnectionError, ValueError,
                    socket.error, CannotHandleRequest) as exc:
                logger.warning(
                    'GETH: request failure, retrying: %s',
                    exc,
                )
                self._cur_errors += 1
                if self._cur_errors % self._retries == 0:
                    self._handle_remote_rpc_provider_failure()
                    self.reset()
            except Exception as exc:
                logger.error("Unknown exception %r", exc)
                raise
            else:
                self.reset()
                self.addr_list = self.initial_addr_list

        return response

    def _create_remote_rpc_provider(self):
        addr = self.addr_list.pop(0)
        logger.info('GETH: connecting to remote RPC interface at %s', addr)
        return HTTPProvider(addr)

    def _handle_remote_rpc_provider_failure(self):
        if not self.addr_list:
            raise Exception("GETH: No more addresses to try, failed to connect")
        logger.warning('GETH: reconnecting to another provider')
        self.provider = self._create_remote_rpc_provider()

    def reset(self):
        """ Resets the current error number counter """
        self._cur_errors = 0
