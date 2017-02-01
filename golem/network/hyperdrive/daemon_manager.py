import atexit
import os
import subprocess

import psutil

from golem.core.processmonitor import ProcessMonitor


class HyperdriveDaemonManager(object):

    _executable = 'hyperg'

    def __init__(self, datadir):
        super(HyperdriveDaemonManager, self).__init__()

        self._manage = False
        self._monitor = ProcessMonitor()
        self._monitor.add_callbacks(self._start)

        self._dir = os.path.join(datadir, 'hyperdrive')
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)

        atexit.register(self.stop)

    def start(self):
        self._manage = not self._daemon_running()
        self._monitor.start()
        self._start()

    def stop(self):
        self._manage = False
        self._monitor.exit()

    def _daemon_running(self):
        for process in psutil.process_iter():
            if process.name() == self._executable:
                return True

            cmdline = process.cmdline()
            if self._executable in cmdline or self._executable + '.js' in cmdline:
                return True

        return False

    def _start(self, *_):
        if self._manage:
            process = subprocess.Popen([self._executable, '"{}"'.format(self._dir)])
            self._monitor.add_child_processes(process)
