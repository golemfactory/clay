import logging
from abc import abstractmethod, ABCMeta

from golem.core.async import AsyncRequest, async_run

log = logging.getLogger("golem")


class IService(metaclass=ABCMeta):
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
    services.

    The public interface is just start() and stop(). Internally it controls
    its state and decides when it must be waken up to perform pending tasks.

    This implementation uses LoopingCall from Twisted framework.
    """

    def __init__(self, interval_seconds: int = 1):
        from twisted.internet.task import LoopingCall

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

    @staticmethod
    def _exceptionHandler(failure):
        log.exception("Service Error: " + failure.getTraceback())
        return None  # Stop processing the failure.

    def _run_async(self):
        return async_run(AsyncRequest(self._run),
                         error=self._exceptionHandler)

    def _run(self):
        """ Implement this in the derived class."""


class ThreadedService(IService, metaclass=ABCMeta):
    """
    A prototype of Golem service -- an long running "thread" that performs
    some tasks in background and responds to request from users and other
    services.

    The public interface is just start() and stop(). Internally it controls
    its state and decides when it must be waken up to perform pending tasks.

    This implementation uses Threads from the threading module.
    """

    def __init__(self) -> None:
        from threading import Event, Thread

        self._thread = Thread(target=self._run, daemon=True)
        self._stopped = Event()

    def start(self) -> None:
        if self.running():
            raise RuntimeError('service already started')
        self._thread.start()

    def stop(self) -> None:
        if self._stopped.is_set():
            raise RuntimeError('service not started')
        self._stopped.set()

    def join(self, timeout=None):
        if not self._thread.is_alive():
            raise RuntimeError('service not started')
        self._thread.join(timeout)

    def running(self) -> bool:
        return not self._stopped.is_set() and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stopped.is_set():
            self._loop()

    @abstractmethod
    def _loop(self):
        pass
