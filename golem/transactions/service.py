import logging
from threading import Thread
from time import sleep

log = logging.getLogger("golem")


class Service(object):
    """ A prototype of Golem service -- an long running thread that performs
        some tasks in background and responds to request from users and other
        services.

        The public interface is just start() and stop(). Internally it controls
        its state and decides when it must be waken up to perform pending tasks.
    """

    def __init__(self, interval=1, permissive=True):
        """
        :param interval: Interval to run the service method with
        :param permissive: Ignore errors in service method
        """
        self.__interval = interval
        self._permissive = permissive
        self._running = False
        self._thread = Thread(target=self._loop)
        self._thread.daemon = True

    @property
    def running(self):
        """ Informs if the service has been started. It is controlled by start()
            and stop() methods, do not change it directly.
        """
        return self._running

    def start(self):
        if self.running:
            raise RuntimeError("service already started")
        self._running = True
        self._thread.start()

    def stop(self):
        if not self.running:
            raise RuntimeError("service not started")
        self._running = False

    def _loop(self):
        while self._running:

            try:
                self._run()
            except Exception as e:
                log.exception("Service error ({})".format(e))
                if not self._permissive:
                    raise

            sleep(self.__interval)

    def _run(self):
        """ Implement this in the derived class."""
