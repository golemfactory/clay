import atexit
import copy
import logging
import os
import subprocess
import sys

import time
from requests import ConnectionError

from golem.core.common import DEVNULL, is_frozen
from golem.core.processmonitor import ProcessMonitor
from golem.network.hyperdrive.client import HyperdriveClient

logger = logging.getLogger('golem.resources')


class HyperdriveDaemonManager(object):

    _executable = 'hyperg'

    def __init__(self, datadir, **hyperdrive_config):
        super(HyperdriveDaemonManager, self).__init__()

        self._addresses = None
        self._config = hyperdrive_config

        # monitor and restart if process dies
        self._monitor = ProcessMonitor()
        self._monitor.add_callbacks(self._start)

        self._dir = os.path.join(datadir, self._executable)

        atexit.register(self.stop)

        logsdir = os.path.join(datadir, "logs")
        if not os.path.exists(logsdir):
            logger.warning("Creating HyperG logsdir: %s", logsdir)
            os.makedirs(logsdir)

        self._command = [
            self._executable,
            '--db', self._dir,
            '--logfile', os.path.join(logsdir, "hyperg.log"),
        ]

    def addresses(self):
        try:
            if not self._addresses:
                self._addresses = HyperdriveClient(**self._config).addresses()
            return self._addresses
        except ConnectionError:
            logger.warning('Cannot connect to Hyperdrive daemon')
            return dict()

    def public_addresses(self, ip, addresses=None):
        if addresses is None:
            addresses = copy.deepcopy(self.addresses())

        for protocol, entry in addresses.items():
            addresses[protocol] = (ip, entry[1])

        return addresses

    def ports(self, addresses=None):
        if addresses is None:
            addresses = self.addresses()

        return set(value[1] for key, value in addresses.items())

    def start(self):
        self._addresses = None
        self._monitor.start()
        return self._start()

    def stop(self, *_):
        self._monitor.exit()

    def _start(self, *_):
        # do not supervise already running processes
        addresses = self.addresses()
        if addresses:
            return

        try:
            os.makedirs(self._dir, exist_ok=True)

            pipe = subprocess.PIPE if is_frozen() else None
            process = subprocess.Popen(self._command, stdin=DEVNULL,
                                       stdout=pipe, stderr=pipe)
        except OSError:
            return self._critical_error()

        if process.poll() is None:
            self._monitor.add_child_processes(process)
            self._wait()
        else:
            raise RuntimeError("Cannot start {}".format(self._executable))

    def _wait(self, timeout: int = 10):
        deadline = time.time() + timeout

        while time.time() < deadline:
            addresses = self.addresses()
            if addresses:
                return
            time.sleep(1.)

        self._critical_error()

    def _critical_error(self):
        logger.critical("Can't run hyperdrive executable %r. "
                        "Make sure path is correct and check "
                        "if it starts correctly.",
                        ' '.join(self._command))
        sys.exit(1)
