import subprocess
import time
from multiprocessing import Process
from threading import Thread

import psutil


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
                if not self.is_process_alive(process):
                    print("Subprocess {} exited with code {}. Terminating"
                          .format(process.pid, self.exit_code(process)))
                    self.exit()
            time.sleep(1)

    def stop(self):
        self.working = False

    def exit(self):
        for callback in self.shutdown_callbacks:
            callback()

    def add_shutdown_callback(self, callback):
        self.shutdown_callbacks.append(callback)

    def kill_processes(self):
        for process in self.child_processes:
            self.kill_process(process)

    @classmethod
    def kill_process(cls, process):
        if cls.is_process_alive(process):
            try:
                process.terminate()
            except Exception as exc:
                print("Error terminating process {}: {}".format(process, exc))

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
            return process.exitcode is None
        return False
