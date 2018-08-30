import logging
import time
from typing import List, Dict, Any, Union

from twisted.internet import task
from twisted.internet.defer import Deferred

from golem.core.common import each

logger = logging.getLogger(__name__)


PoolType = List[Any]


class OfferPool:

    _TAKE_INTERVAL: float = 1.0  # s
    _pools: Dict[str, PoolType] = dict()

    @classmethod
    def contains(cls, key: str) -> bool:
        return key in cls._pools

    @classmethod
    def size(cls, key: str) -> int:
        if not cls.contains(key):
            return 0
        return len(cls._pools[key])

    @classmethod
    def add(cls, key: str, *items) -> None:
        pool = cls._pool(key)
        each(pool.append, items)

    @classmethod
    def peek(cls, key: str, count: int = 0) -> PoolType:
        if not cls.contains(key):
            return []

        pool = cls._pools[key]
        idx = cls._rev_index(pool, count)
        return pool[:idx]

    @classmethod
    def drain(cls, key: str) -> PoolType:
        elements = cls.peek(key)
        if cls.contains(key):
            del cls._pools[key]
        return elements

    @classmethod
    def drain_after(cls, key: str, timeout: Union[int, float]) -> Deferred:
        from twisted.internet import reactor
        return task.deferLater(reactor, timeout, cls.drain, key)

    @classmethod
    def take_when(cls,
                  key: str,
                  count: int,
                  timeout: Union[int, float]) -> Deferred:

        result = Deferred()
        cls._take(result, key, count, deadline=time.time() + timeout)
        return result

    @classmethod
    def _take(cls,
              result: Deferred,
              key: str,
              count: int,
              deadline: Union[int, float] = 0) -> None:

        if deadline and time.time() >= deadline:
            result.errback(TimeoutError('OfferPool._take timed out'))
        elif cls.size(key) >= count:
            offers = cls._shift(key, count)
            result.callback(offers)
        else:
            from twisted.internet import reactor
            reactor.callLater(cls._TAKE_INTERVAL, cls._take,
                              result, key, count, deadline)

    @classmethod
    def _pool(cls, key: str) -> PoolType:
        if not cls.contains(key):
            cls._pools[key] = list()
        return cls._pools[key]

    @classmethod
    def _shift(cls, key: str, count: int) -> PoolType:
        pool = cls._pools[key]
        idx = cls._rev_index(pool, count)
        elements, cls._pools[key] = pool[:idx], pool[idx:]
        return elements

    @classmethod
    def _rev_index(cls, pool: PoolType, count: int) -> int:
        size = len(pool)
        if count in (0, size):
            return size
        return min(0, count - size) or size
