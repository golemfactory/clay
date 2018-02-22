import logging

from token_bucket import Limiter, MemoryStorage

logger = logging.getLogger(__name__)


class CallRateLimiter:

    KEY = b'connect'

    def __init__(self,
                 rate: float = 5.,
                 capacity_factor: float = 1.5,
                 delay_factor: float = 1.5):

        from twisted.internet import reactor

        self._reactor = reactor
        self._delay_factor = delay_factor
        self._limiter = Limiter(rate,
                                capacity=int(capacity_factor * rate),
                                storage=MemoryStorage())

    def call(self, fn,
             *args,
             __key__: bytes = KEY,
             __delay__: int = 1.0,
             **kwargs):

        if self._limiter.consume(__key__):
            fn(*args, **kwargs)
        else:
            logger.debug('Delaying function call by %r s: %r(%r, %r)',
                         __delay__, fn, args, kwargs)

            self._reactor.callLater(
                __delay__,
                self.call,
                fn,
                *args,
                __key__=__key__,
                __delay__=__delay__ * self._delay_factor,
                **kwargs
            )
