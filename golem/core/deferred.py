from queue import Queue, Empty
from typing import Any

from twisted.internet import defer
from twisted.internet.task import deferLater
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure


class DeferredSeq:
    def __init__(self, *fns) -> None:
        self._seq = list(fns)

    def execute(self) -> defer.Deferred:
        # The executed function cannot return a Deferred object
        def wrapper():
            self._execute()
        return deferToThread(wrapper)

    @defer.inlineCallbacks
    def _execute(self) -> Any:
        arg = None
        for fn in self._seq:
            arg = yield defer.maybeDeferred(fn, arg)
        return arg


def chain_function(deferred, fn, *args, **kwargs):
    result = defer.Deferred()

    def resolve(_):
        fn(*args, **kwargs).addCallbacks(result.callback,
                                         result.errback)
    deferred.addCallback(resolve)
    deferred.addErrback(result.errback)

    return result


def sync_wait(deferred, timeout=10):
    if not isinstance(deferred, defer.Deferred):
        return deferred

    queue = Queue()
    deferred.addBoth(queue.put)

    try:
        result = queue.get(True, timeout)
    except Empty:
        raise defer.TimeoutError("Command timed out")

    if isinstance(result, Failure):
        result.raiseException()
    return result


def call_later(delay: int, fn, *args, **kwargs) -> None:
    from twisted.internet import reactor
    deferLater(reactor, delay, fn, *args, **kwargs)
