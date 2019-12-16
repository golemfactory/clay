import itertools
import logging
import socket
import time
import typing

from web3.exceptions import CannotHandleRequest
from web3.providers.rpc import HTTPProvider

logger = logging.getLogger(__name__)

RETRY_COUNT_LIMIT = 10
RETRY_COUNT_INTERVAL = 1800  # seconds
SINGLE_QUERY_RETRY_LIMIT = 3
SINGLE_QUERY_NODE_LIMIT = 2


class ProviderProxy(HTTPProvider):

    def __init__(self, initial_addr_list) -> None:
        super().__init__()
        self._node_addresses = itertools.cycle(initial_addr_list)
        self.provider = self._create_remote_rpc_provider()

        self._single_query_node_limit = min(
            SINGLE_QUERY_NODE_LIMIT, len(initial_addr_list)
        )
        self._init_retries_count()

    def _init_retries_count(self, ts: typing.Optional[float] = None):
        self._retries = 0
        self._first_retry_time = ts

    def _register_retry(self):
        now = time.time()
        if not self._first_retry_time \
                or self._first_retry_time + RETRY_COUNT_INTERVAL < now:
            self._init_retries_count(now)

        self._retries += 1

    def make_request(self, method, params):
        logger.debug('ProviderProxy.make_request(%r, %r)', method, params)

        nodes_tried = 0
        retries = 0
        response = None

        while response is None:
            try:
                response = self.provider.make_request(method, params)
                logger.debug(
                    'GETH: request successful %s (%r, %r) -- result = %r',
                    self.provider.endpoint_uri, method, params, response
                )
            except (ConnectionError,
                    socket.error, CannotHandleRequest) as exc:
                retries += 1
                self._register_retry()

                retry = retries < SINGLE_QUERY_RETRY_LIMIT \
                    and self._retries < RETRY_COUNT_LIMIT

                logger.debug(
                    "GETH: request failure%s"
                    ". %s (%r, %r), error='%s', "
                    'single query retries=%s, node retries=%s',
                    ', retrying' if retry else '',
                    self.provider.endpoint_uri, method, params, exc,
                    retries, self._retries,
                )

                if not retry:
                    nodes_tried += 1
                    retries = 0
                    self._handle_remote_rpc_provider_failure(
                        method,
                        nodes_tried >= self._single_query_node_limit
                    )
            except Exception as exc:
                logger.error("Unknown exception %r", exc)
                raise

        return response

    def _create_remote_rpc_provider(self):
        addr = next(self._node_addresses)
        logger.info('GETH: connecting to remote RPC interface at %s', addr)
        return HTTPProvider(addr)

    def _handle_remote_rpc_provider_failure(self, method: str, final: bool):
        if final:
            raise Exception(
                "GETH: Node limit exhausted, request failed."
                f" method='{method}'",
            )
        logger.warning(
            "GETH: '%s' request failed on '%s', "
            "reconnecting to another provider.",
            method, self.provider.endpoint_uri,
        )
        self.provider = self._create_remote_rpc_provider()
        self._init_retries_count()
