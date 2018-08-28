import logging
from typing import List, Dict, Any

from twisted.internet import task, defer
from twisted.internet.defer import Deferred

from golem.core.common import each

logger = logging.getLogger(__name__)


class OfferPool:

    __instance = None

    def __new__(cls):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self):
        from twisted.internet import reactor

        self._reactor = reactor
        self._pools: Dict[str, List[Any]] = dict()

    def __contains__(self, key: str) -> bool:
        return key in self._pools

    def add(self, key: str, *items) -> None:
        pool = self._pool(key)
        each(pool.append, items)

    def get(self, key: str) -> List[Any]:
        if key in self:
            return self._pools[key][:]
        return []

    def drain(self, key: str) -> List[Any]:
        elements: List[Any] = self.get(key)
        if key in self:
            del self._pools[key]
        return elements

    def drain_after(self, key: str, timeout: float) -> Deferred:
        if key not in self._pools:
            return defer.fail(KeyError(key))
        return task.deferLater(self._reactor, timeout, self.drain, key)

    def _pool(self, key: str) -> List[Any]:
        if key not in self:
            self._pools[key] = list()
        return self._pools[key]
