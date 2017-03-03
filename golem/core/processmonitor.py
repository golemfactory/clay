import atexit
import subprocess
import time
from multiprocessing import Process
from threading import Thread, Lock

import psutil


class ProcessMonitor(Thread):

    def __init__(self, *child_processes, **params):
        super(ProcessMonitor, self).__init__(target=self._start)

        self._child_processes = []
        self._callbacks = params.pop('callbacks', [])
        self._lock = Lock()

        self.daemon = True
        self.working = False

        atexit.register(self.exit)
        self.add_child_processes(*child_processes)

    def _start(self):
        self.working = True

        while self.working:
            for i in xrange(len(self._child_processes) - 1, -1, -1):
                process = self._child_processes[i]

                if not self.is_process_alive(process):
                    print "Subprocess {} exited with code {}".format(process.pid,
                                                                     self.exit_code(process))
                    if self.working:
                        self.run_callbacks(process)
                    self._child_processes.pop(i)

            time.sleep(0.5)

    def stop(self, *_):
        self.working = False

    def exit(self, *_):
        self.stop()
        self.kill_processes()

    def add_child_processes(self, *processes):
        assert all([self.is_supported(p) for p in processes])
        self._child_processes.extend(processes)

    def add_callbacks(self, *callbacks):
        self._callbacks.extend(callbacks)

    def remove_callbacks(self, *callbacks):
        for handler in callbacks:
            idx = self._callbacks.index(handler)
            if idx != -1:
                self._callbacks.pop(idx)

    def run_callbacks(self, process=None):
        for callback in self._callbacks:
            if self.working:
                callback(process)

    def kill_processes(self, *_):
        for process in self._child_processes:
            self.kill_process(process)

    @classmethod
    def kill_process(cls, process):
        if cls.is_process_alive(process):
            try:
                process.terminate()

                if isinstance(process, (psutil.Popen, subprocess.Popen)):
                    process.communicate()
                elif isinstance(process, Process):
                    process.join()

            except Exception as exc:
                print("Error terminating process {}: {}".format(process, exc))
            else:
                print "Subprocess {} terminated".format(cls._pid(process))

    @staticmethod
    def _pid(process):
        if process:
            return process.pid

    @staticmethod
    def is_supported(process):
        return isinstance(process, (psutil.Popen, subprocess.Popen, Process))

    @staticmethod
    def exit_code(process):
        if isinstance(process, (psutil.Popen, subprocess.Popen)):
            process.poll()
            return process.returncode
        elif isinstance(process, Process):
            return process.exitcode

    @staticmethod
    def is_process_alive(process):
        if isinstance(process, (psutil.Popen, subprocess.Popen)):
            process.poll()
            return process.returncode is None
        elif isinstance(process, Process):
            return process.is_alive()
        return False
