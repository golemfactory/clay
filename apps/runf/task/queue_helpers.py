# modified from
# http://peter-hoffmann.com/2012/python-simple-queue-redis-queue.html
from typing import Any, Tuple

import redis

from apps.runf.task.runf_helpers import QueueID, Host, Port


class _RedisQueue:
    """Simple Queue with Redis Backend"""
    def __init__(self, name, host: Host="localhost", port: Port=6379):
        self._db = redis.Redis(host=host, port=port, encoding='utf-8')
        self.key = f"{name}"

    def queue_size(self):
        """Return the approximate size of the queue."""
        return self._db.llen(self.key)

    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return self.queue_size() == 0

    def pop(self, block, timeout=None):
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available."""
        if block:
            item = self._db.blpop(self.key, timeout=timeout)
        else:
            item = self._db.lpop(self.key)

        if item:
            item = item.decode("utf-8")
        return item

    def push(self, item):
        """Put item into the queue."""
        self._db.rpush(self.key, item)


class Queue(_RedisQueue):

    def pop(self, block=True, timeout=None) -> Tuple[QueueID, Any]:
        key = super().pop(block, timeout)
        return key, self.get(key)

    def pop_nowait(self):
        return self.pop(False)

    def set(self, key, item):
        print(f"Setting {key} to {item}")
        self._db.set(key, item)

    def get(self, key):
        print(f"Getting {key}")
        val = self._db.get(key)
        if val is None:
            return val
        return val.decode("utf-8")