from queue import Queue, Empty
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from twisted.internet import defer
from twisted.internet.task import deferLater
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure


class DeferredSeq:
    def __init__(self) -> None:
        self._seq: List[Tuple[Callable, Tuple, Dict]] = []

    def push(self, fn: Callable, *args, **kwargs) -> 'DeferredSeq':
        self._seq.append((fn, args, kwargs))
        return self

    def execute(self) -> defer.Deferred:
        return deferToThread(lambda: sync_wait(self._execute(), timeout=None))

    @defer.inlineCallbacks
    def _execute(self) -> Any:
        result = None
        for entry in self._seq:
            fn, args, kwargs = entry
            result = yield defer.maybeDeferred(fn, *args, **kwargs)
        return result


def chain_function(deferred, fn, *args, **kwargs):
    result = defer.Deferred()

    def resolve(_):
        fn(*args, **kwargs).addCallbacks(result.callback,
                                         result.errback)
    deferred.addCallback(resolve)
    deferred.addErrback(result.errback)

    return result


def sync_wait(deferred: defer.Deferred,
              timeout: Optional[Union[int, float]] = 10.) -> Any:

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
