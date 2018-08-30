import logging
from typing import List, Dict, Any

from twisted.internet import task, defer
from twisted.internet.defer import Deferred

from golem.core.common import each

logger = logging.getLogger(__name__)


class OfferPool:

    _pools: Dict[str, List[Any]] = dict()

    @classmethod
    def contains(cls, key: str) -> bool:
        return key in cls._pools

    @classmethod
    def add(cls, key: str, *items) -> None:
        pool = cls._pool(key)
        each(pool.append, items)

    @classmethod
    def get(cls, key: str) -> List[Any]:
        if key in cls._pools:
            return cls._pools[key][:]
        return []

    @classmethod
    def drain(cls, key: str) -> List[Any]:
        elements: List[Any] = cls.get(key)
        if key in cls._pools:
            del cls._pools[key]
        return elements

    @classmethod
    def drain_after(cls, key: str, timeout: float) -> Deferred:
        from twisted.internet import reactor
        return task.deferLater(reactor, timeout, cls.drain, key)

    @classmethod
    def _pool(cls, key: str) -> List[Any]:
        if key not in cls._pools:
            cls._pools[key] = list()
        return cls._pools[key]
