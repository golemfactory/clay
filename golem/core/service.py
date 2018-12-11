import logging
from abc import ABC, abstractmethod

from golem.core import golem_async
from twisted.internet.task import LoopingCall

log = logging.getLogger("golem")


class IService(ABC):
    """
    An interface of a Golem service.
    """

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def running(self) -> bool:
        raise NotImplementedError


class LoopingCallService(IService):
    """
    A prototype of Golem service -- an long running "thread" that performs
    some tasks in background and responds to request from users and other
    serices.

    The public interface is just start() and stop(). Internally it controls
    its state and decides when it must be waken up to perform pending tasks.

    This implementation uses LoopingCall from Twisted framework.
    """

    def __init__(self, interval_seconds: int = 1, run_in_thread: bool = False) \
            -> None:
        self.__interval_seconds = interval_seconds
        self._loopingCall = LoopingCall(
            self._run_async if run_in_thread else self._run)

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

    @classmethod
    def _exceptionHandler(cls, failure):
        log.exception("Service Error: " + failure.getTraceback())
        return None  # Stop processing the failure.

    def _run_async(self):
        return golem_async.async_run(
            golem_async.AsyncRequest(self._run),
            error=self._exceptionHandler,
        )

    def _run(self):
        """ Implement this in the derived class."""
