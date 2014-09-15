from threading import Thread, Event
import psutil
import time

class MemoryChecker( Thread ):
    def __init__( self ):
        super(MemoryChecker, self).__init__()
        self.startMem = psutil.virtual_memory().used
        self.maxMem = 0
        self.pid = 0
        self._stop = Event()

    def stop( self ):
        self._stop.set()
        return self.maxMem - self.startMem

    def stopped( self ):
        return self._stop.isSet()

    def run( self ):
        while not self.stopped():
            mem = psutil.virtual_memory().used
            if mem > self.maxMem:
                self.maxMem = mem
            time.sleep( 0.5 )