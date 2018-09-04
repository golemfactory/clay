# modified from
# http://peter-hoffmann.com/2012/python-simple-queue-redis-queue.html
from typing import Any, Tuple

import redis

from apps.runf.task.runf_helpers import QueueID


class _RedisQueue:
    """Simple Queue with Redis Backend"""
    def __init__(self, name, host="localhost", port=6379):
        self.__db = redis.Redis(host=host, port=port)
        self.key = f"{name}"

    def queue_size(self):
        """Return the approximate size of the queue."""
        return self.__db.llen(self.key)

    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return self.queue_size() == 0

    def pop(self, block, timeout=None):
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available."""
        if block:
            item = self.__db.blpop(self.key, timeout=timeout)
        else:
            item = self.__db.lpop(self.key)

        if item:
            item = item[1]
        return item

class Queue(_RedisQueue):

    def pop(self, block=True, timeout=None) -> Tuple[QueueID, Any]:
        key = super().pop(block, timeout)
        return key, self.get(key)

    def get_nowait(self):
        super().pop(False)

    def set(self, key, item):
        self.__db.set(key, item)

    def get(self, key):
        self.__db.get(key)
