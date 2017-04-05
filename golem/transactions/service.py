import logging

from golem.resource.client import AsyncRequest, async_run
from twisted.internet.task import LoopingCall

log = logging.getLogger("golem")


class Service(object):
    """ A prototype of Golem service -- an long running "thread" that performs
        some tasks in background and responds to request from users and other
        serices.

        The public interface is just start() and stop(). Internally it controls
        its state and decides when it must be waken up to perform pending tasks.

        This implementation uses LoopingCall from Twisted framework.
    """

    def __init__(self, interval=1):
        self.__interval = interval
        self._loopingCall = LoopingCall(self._run_async)

    @property
    def running(self):
        """ Informs if the service has been started. It is controlled by start()
            and stop() methods, do not change it directly.
        """
        return self._loopingCall.running

    def start(self):
        if self.running:
            raise RuntimeError("service already started")
        deferred = self._loopingCall.start(self.__interval)
        deferred.addErrback(self._exceptionHandler)

    def stop(self):
        if not self.running:
            raise RuntimeError("service not started")
        self._loopingCall.stop()

    def _exceptionHandler(self, failure):
        log.exception("Service Error: " + failure.getTraceback())
        return None  # Stop processing the failure.

    def _run_async(self):
        return async_run(AsyncRequest(self._run),
                         error=self._exceptionHandler)

    def _run(self):
        """ Implement this in the derived class."""
