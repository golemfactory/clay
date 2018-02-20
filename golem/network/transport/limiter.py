import logging

from token_bucket import Limiter, MemoryStorage

logger = logging.getLogger(__name__)


class ConnectionRateLimiter:

    KEY = b'connect'

    def __init__(self, rate=5., capacity_factor=1.5):
        self._limiter = Limiter(rate,
                                capacity=int(capacity_factor * rate),
                                storage=MemoryStorage())

    def run(self, fn, *args, __key__: bytes = KEY, **kwargs):
        if self._limiter.consume(__key__):
            return fn(*args, **kwargs)

        logger.debug('Dropping new connection request to %r', args[:2])
        return None
