import socket

from types import MethodType

from web3.exceptions import CannotHandleRequest

MAX_ERRORS = 3


class RemoteRPCErrorMiddlewareBuilder:
    """
    Not for use with multiple (incompatible) providers - hence the
    CannotHandleRequest exception in middleware function.
    """

    def __init__(self,
                 error_listener: MethodType,
                 max_errors: int = MAX_ERRORS) -> None:
        """
        :param error_listener: Function to execute when the maximum number of
        consecutive errors is reached
        :param max_errors: Maximum number of consecutive unrecoverable errors
        """
        self._max_errors = max_errors
        self._cur_errors = 0
        self._err_listener = error_listener

    def build(self, make_request, _web3):
        """ Returns the middleware function """

        def middleware(method, params):
            try:
                result = make_request(method, params)
            except (ConnectionError, ValueError,
                    socket.error, CannotHandleRequest) as exc:

                self._cur_errors += 1
                if self._cur_errors >= self._max_errors:
                    self.reset()
                    self._err_listener(exc)
                raise

            else:
                self.reset()
                return result

        return middleware

    def reset(self):
        """ Resets the current error number counter """
        self._cur_errors = 0
