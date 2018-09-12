import logging
import socket

from types import Any, Callable

from web3.exceptions import CannotHandleRequest

logger = logging.getLogger(__name__)

RETRIES = 3


class RemoteRPCErrorMiddlewareBuilder:
    """
    Not for use with multiple (incompatible) providers - hence the
    CannotHandleRequest exception in middleware function.
    """

    def __init__(self,
                 error_listener: Callable[[], Any],
                 retries: int = RETRIES) -> None:
        """
        :param error_listener: Function to execute when the maximum number of
        consecutive errors is reached
        """
        self._retries = retries
        self._cur_errors = 0
        self._err_listener = error_listener

    def build(self, make_request, _web3):
        """ Returns the middleware function """

        def middleware(method, params):
            while True:
                try:
                    result = make_request(method, params)
                except (ConnectionError, ValueError,
                        socket.error, CannotHandleRequest) as exc:
                    logger.warning(
                        'GETH: request failure, retrying: %s',
                        exc,
                    )
                    self._cur_errors += 1
                    if self._cur_errors % self._retries == 0:
                        self._err_listener()
                        raise
                else:
                    self.reset()
                    return result

        return middleware

    def reset(self):
        """ Resets the current error number counter """
        self._cur_errors = 0
