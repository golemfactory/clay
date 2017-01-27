import time
from multiprocessing import Process
from threading import Thread

from subprocess import Popen


class ProcessMonitor(Thread):

    def __init__(self, callbacks=None, *child_processes):
        super(ProcessMonitor, self).__init__(target=self._start)

        if not all([self.is_supported(p) for p in child_processes]):
            raise ValueError('Child processes class is not supported')

        self.child_processes = child_processes
        self.callbacks = callbacks or []
        self.working = False

    def _start(self):
        self.working = True

        while self.working:
            for process in self.child_processes:
                if not self.is_process_alive(process):
                    print "Subprocess {} exited with code {}".format(process.pid, process.exitcode)
                    self.run_callbacks(process)
            time.sleep(1)

    def stop(self):
        self.working = False

    def exit(self):
        self.kill_processes()
        self.stop()

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def set_callbacks(self, *callbacks):
        self.callbacks = callbacks or []

    def kill_processes(self):
        for process in self.child_processes:
            self.kill_process(process)

    def run_callbacks(self, process=None):
        for callback in self.callbacks:
            callback(process)

    @classmethod
    def kill_process(cls, process):
        if cls.is_process_alive(process):
            try:
                process.terminate()
            except Exception as exc:
                print "Error terminating subprocess {}: {}".format(process, exc)
            else:
                print "Subprocess {} terminated".format(process)

    @staticmethod
    def is_supported(process):
        return isinstance(process, (Popen, Process))

    @staticmethod
    def is_process_alive(process):
        if isinstance(process, Popen):
            process.poll()
            return process.returncode is None
        elif isinstance(process, Process):
            return process.is_alive()
        else:
            return False
