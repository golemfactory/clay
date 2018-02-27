from queue import Queue, Empty

from twisted.internet.defer import DebugInfo, Deferred, TimeoutError
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


def install_unhandled_error_logger():
    import logging
    logger = logging.getLogger('golem')

    def delete(self):
        if self.failResult is not None:
            logger.error("Unhandled error in Deferred:\n{}"
                         .format(self.failResult))

    setattr(DebugInfo, '__del__', delete)
