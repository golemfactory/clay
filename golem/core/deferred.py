from queue import Queue, Empty
from typing import Any

from twisted.internet.defer import Deferred, TimeoutError, inlineCallbacks, \
    maybeDeferred
from twisted.internet.task import deferLater
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure


class DeferredSeq:
    def __init__(self, *fns) -> None:
        self._seq = list(fns)

    def execute(self) -> Deferred:
        # The executed function cannot return a Deferred, hence the bool cast
        return deferToThread(lambda *_: bool(self._execute()))

    @inlineCallbacks
    def _execute(self) -> Any:
        arg = None
        for fn in self._seq:
            arg = yield maybeDeferred(fn, arg)
        return arg


def chain_function(deferred, fn, *args, **kwargs):
    result = Deferred()

    def resolve(_):
        fn(*args, **kwargs).addCallbacks(result.callback,
                                         result.errback)
    deferred.addCallback(resolve)
    deferred.addErrback(result.errback)

    return result


def sync_wait(deferred, timeout=10):
    if not isinstance(deferred, Deferred):
        return deferred

    queue = Queue()
    deferred.addBoth(queue.put)

    try:
        result = queue.get(True, timeout)
    except Empty:
        raise TimeoutError("Command timed out")

    if isinstance(result, Failure):
        result.raiseException()
    return result


def call_later(delay: int, callable, *args, **kwargs) -> None:
    from twisted.internet import reactor
    deferLater(reactor, delay, callable, *args, **kwargs)
