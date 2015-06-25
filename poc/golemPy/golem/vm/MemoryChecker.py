from threading import Thread, Event
import psutil
import time

class MemoryChecker(Thread):
    def __init__(self):
        super(MemoryChecker, self).__init__()
        self.startMem = psutil.virtual_memory().used
        self.maxMem = 0
        self.minMem = self.startMem
        self.pid = 0
        self._stop = Event()

    def stop(self):
        self._stop.set()
        if self.maxMem - self.startMem > 0:
            return self.maxMem - self.startMem
        else:
            return max(0, self.maxMem - self.minMem)

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        while not self.stopped():
            mem = psutil.virtual_memory().used
            if mem > self.maxMem:
                self.maxMem = mem
            if mem < self.minMem:
                self.minMem = mem
            time.sleep(0.5)