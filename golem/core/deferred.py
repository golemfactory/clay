from queue import Queue, Empty

from twisted.internet.defer import Deferred, TimeoutError
from twisted.internet.task import deferLater
from twisted.python.failure import Failure


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
