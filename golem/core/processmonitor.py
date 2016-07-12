import os
import signal
import time
from threading import Thread


class ProcessMonitor(Thread):

    def __init__(self, *child_processes):
        super(ProcessMonitor, self).__init__(target=self._start)
        self.shutdown_callbacks = [self.kill_processes, self.stop]
        self.child_processes = child_processes
        self.working = False

    def _start(self):
        self.working = True

        while self.working:
            for process in self.child_processes:
                if not process.is_alive():
                    self.exit()
            time.sleep(1)

    def stop(self):
        self.working = False

    def exit(self):
        for callback in self.shutdown_callbacks:
            callback()

    def add_shutdown_callback(self, callback):
        self.shutdown_callbacks.append(callback)

    def kill_processes(self, sig=signal.SIGTERM):
        for process in self.child_processes:
            self.kill_process(process, sig)

    @staticmethod
    def kill_process(process, sig=signal.SIGTERM):
        if process.is_alive():
            try:
                os.kill(process.pid, sig)
            except Exception as exc:
                print "Error terminating process {}: {}".format(
                    process, exc)
