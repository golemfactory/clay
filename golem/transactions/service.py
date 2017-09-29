import logging

from golem.core.async import run_threaded, LoopingCall

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
        future = self._loopingCall.start(self.__interval)
        future.add_done_callback(self._exceptionHandler)

    def stop(self):
        if not self.running:
            raise RuntimeError("service not started")
        self._loopingCall.stop()

    def _exceptionHandler(self, future):
        try:
            future.result()
        except Exception as failure:
            log.exception("Service Error: %r", failure)

    def _run_async(self):
        return run_threaded(self._run,
                            error=self._exceptionHandler)

    def _run(self):
        """ Implement this in the derived class."""
