import atexit
import logging
import os
import subprocess
import time

from requests import ConnectionError

from golem.core.processmonitor import ProcessMonitor
from golem.network.hyperdrive.client import HyperdriveClient

logger = logging.getLogger(__name__)


class HyperdriveDaemonManager(object):

    _executable = 'hyperg'

    def __init__(self, datadir, **hyperdrive_config):
        super(HyperdriveDaemonManager, self).__init__()

        self._config = hyperdrive_config

        # monitor and restart if process dies
        self._monitor = ProcessMonitor()
        self._monitor.add_callbacks(self._start)

        # hyperdrive data directory
        self._dir = os.path.join(datadir, self._executable)
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)

        atexit.register(self.stop)

    def start(self):
        self._monitor.start()
        self._start()

    def stop(self):
        self._monitor.exit()

    def _command(self):
        return [self._executable, '--db', self._dir]

    def _daemon_running(self):
        try:
            return HyperdriveClient(**self._config).id()
        except ConnectionError:
            return False

    def _start(self, *_):
        # do not supervise already running processes
        if self._daemon_running():
            return

        try:
            process = subprocess.Popen(self._command())
        except OSError as e:
            logger.critical('Can\'t run hyperdrive executable %r. Make sure path is correct and check if it starts correctly.', ' '.join(self._command()))
            import sys
            sys.exit(1)
        while not self._daemon_running():
            time.sleep(0.1)

        if process.poll() is None:
            self._monitor.add_child_processes(process)
        else:
            raise RuntimeError("Cannot start {}".format(self._executable))
