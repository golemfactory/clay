import logging
import time
from collections import deque
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class ThreadQueueExecutor(Thread):

    lock = Lock()

    def __init__(self, group=None, name=None,
                 args=(), kwargs=None, verbose=None):

        super(ThreadQueueExecutor, self).__init__(group, self._loop, name,
                                                  args, kwargs, verbose)
        self.working = True
        self.sleep_loop = 1.0
        self.sleep_short = 0.1
        self.max_size = 2
        self._queue = deque()

    def start(self):
        result = super(ThreadQueueExecutor, self).start()
        self._register_shutdown_handler()
        return result

    def push(self, thread):
        with self.lock:
            total = len(self._queue)
            if total >= self.max_size:
                self._queue[-1] = thread
            else:
                self._queue.append(thread)

    def shutdown(self):
        self.working = False

    def _loop(self):
        while self.working:
            sleep = self.sleep_loop
            try:
                if self._queue:
                    self._join_next()
                    sleep = self.sleep_short
            except Exception as e:
                logger.debug("Error executing thread [{}]: {}"
                             .format(self.getName(), e.message))
            time.sleep(sleep)

    def _join_next(self):
        with self.lock:
            t = self._queue.popleft()
        if not t.isAlive():
            t.start()
        t.join()

    def _register_shutdown_handler(self):
        try:
            from twisted.internet import reactor
            reactor.addSystemEventTrigger("before", "shutdown", self.shutdown)
        except Exception as e:
            logger.warn("Cannot add a shutdown handler [{}]: {}"
                        .format(self.getName(), e.message))
