import logging
import time
from collections import deque
from threading import Thread, Lock

logger = logging.getLogger(__name__)


class QueueJob(object):

    def __init__(self, method, *args, **kwargs):

        self.method = method
        self.args = args
        self.kwargs = kwargs


class QueueExecutor(Thread):

    def __init__(self, queue_name=None):

        self.queue_name = queue_name
        self.max_size = None

        self.sleep_idle = 0.5
        self.sleep_job = 0.01

        self._working = False
        self._stop_if_empty = False

        self._queue = deque()
        self._lock = Lock()

        self.__was_started = False
        self.__reinitialize()

    def start(self):
        """ Starts the thread. May reinitialize
        current instance if the thread had been started."""

        if self.isAlive():
            return

        self._working = True
        self._stop_if_empty = False

        if self.__was_started:
            self.__reinitialize()
        self.__was_started = True

        super(QueueExecutor, self).start()

    def stop(self):
        self._working = False

    def finish(self):
        self._stop_if_empty = True
        self.join()

    def push(self, source, *args, **kwargs):
        job = self._to_job(source, *args, **kwargs)

        with self._lock:
            if self.max_size and len(self._queue) >= self.max_size:
                self._queue[-1] = job
            else:
                self._queue.append(job)

        if not self.isAlive():
            self.start()

    def _process_queue(self):
        while self._working:

            if self._queue:
                with self._lock:
                    job = self._queue.popleft()

                try:
                    self._execute(job)
                except Exception as e:
                    logger.debug("Queue executor [{}] error: {}"
                                 .format(self.getName(), e.message))
                else:
                    time.sleep(self.sleep_job)

            elif self._stop_if_empty:
                self.stop()
            else:
                time.sleep(self.sleep_idle)

    @classmethod
    def _to_job(cls, source, *args, **kwargs):
        return QueueJob(source, *args, **kwargs)

    @classmethod
    def _execute(cls, job):
        job.method(*job.args, **job.kwargs)

    def __reinitialize(self):
        super(QueueExecutor, self).__init__(target=self._process_queue,
                                            name=self.queue_name)
        self.setDaemon(True)


class ThreadQueueExecutor(QueueExecutor):

    def __init__(self, queue_name=None, max_size=2):

        super(ThreadQueueExecutor, self).__init__(queue_name=queue_name)
        self.max_size = max_size

    @classmethod
    def _to_job(cls, source, *args, **kwargs):
        if not isinstance(source, Thread):
            raise TypeError("Incorrect source type: {}. Should be Thread".format(type(source)))
        return source

    @classmethod
    def _execute(cls, job):
        if not job.isAlive():
            job.setDaemon(True)
            job.start()
        job.join()
