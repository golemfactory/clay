from asyncio import Future
from queue import Queue, Empty

from twisted.internet.defer import DebugInfo
from twisted.python.failure import Failure

from golem.core.async import handle_future


def sync_wait(future, timeout=10):
    if not isinstance(future, Future):
        return future

    queue = Queue()
    handle_future(future, queue.put, queue.put)

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
