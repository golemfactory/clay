from threading import Thread, Event
import psutil
import time


class MemoryChecker(Thread):
    def __init__(self):
        super(MemoryChecker, self).__init__()
        self.start_mem = psutil.virtual_memory().used
        self.max_mem = 0
        self.min_mem = self.start_mem
        self.pid = 0
        self._stop = Event()

    def stop(self):
        self._stop.set()
        if self.max_mem - self.start_mem > 0:
            return self.max_mem - self.start_mem
        else:
            return max(0, self.max_mem - self.min_mem)

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        while not self.stopped():
            mem = psutil.virtual_memory().used
            if mem > self.max_mem:
                self.max_mem = mem
            if mem < self.min_mem:
                self.min_mem = mem
            time.sleep(0.5)
