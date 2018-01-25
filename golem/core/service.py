import logging
from abc import ABC, abstractmethod

from golem.core.async import AsyncRequest, async_run
from twisted.internet.task import LoopingCall

log = logging.getLogger("golem")


class IService(ABC):
    """
    An interface of a Golem service.
    """

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def running(self) -> bool:
        pass


class LoopingCallService(IService):
    """
    A prototype of Golem service -- an long running "thread" that performs
    some tasks in background and responds to request from users and other
    serices.

    The public interface is just start() and stop(). Internally it controls
    its state and decides when it must be waken up to perform pending tasks.

    This implementation uses LoopingCall from Twisted framework.
    """
    __interval_seconds = 0  # type: int
    _loopingCall = None  # type: LoopingCall

    def __init__(self, interval_seconds: int = 1):
        self.__interval_seconds = interval_seconds
        self._loopingCall = LoopingCall(self._run_async)

    @property
    def running(self) -> bool:
        """
        Informs if the service has been started. It is controlled by start()
        and stop() methods, do not change it directly.
        """
        return self._loopingCall.running

    def start(self, now: bool = True):
        if self.running:
            raise RuntimeError("service already started")
        deferred = self._loopingCall.start(self.__interval_seconds, now)
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
