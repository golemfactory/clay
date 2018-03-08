import socket

from types import MethodType

MAX_ERRORS = 3


class RemoteRPCErrorMiddlewareBuilder:

    def __init__(self, hook: MethodType, max_errors: int = MAX_ERRORS):
        self._max_errors = max_errors
        self._cur_errors = 0
        self._err_hook = hook

    def build(self, make_request, _web3):

        def middleware(method, params):
            self._assert_error_count()

            try:
                result = make_request(method, params)
            except (ConnectionError, ValueError, socket.error) as exc:
                self._cur_errors += 1
                if self._cur_errors >= self._max_errors:
                    self._err_hook(exc)
                raise
            else:
                self.reset()
                return result

        return middleware

    def _assert_error_count(self):
        if self._cur_errors >= self._max_errors:
            raise ConnectionError('Reached the maximum number of subsequent'
                                  'failures ({})'.format(self._max_errors))

    def reset(self):
        self._cur_errors = 0
