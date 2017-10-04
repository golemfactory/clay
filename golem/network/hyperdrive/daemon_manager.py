import atexit
import copy
import logging
import os
import subprocess
import sys

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
        self._log_file = os.path.join(datadir, 'hyperg.log')

        self._command = [
            self._executable,
            '--db', self._dir,
            '--logfile', self._log_file,
            '--loglevel', 'debug'
        ]

        atexit.register(self.stop)
        logsdir = os.path.join(datadir, "logs")
        if not os.path.exists(logsdir):
            logger.warning("create HyperG logsdir: %s", logsdir)
            os.makedirs(logsdir)

        logpath = os.path.join(logsdir, "hyperg.log")
        self._command = [
            self._executable,
            '--db', self._dir,
            '--logfile', logpath,
        ]

    def addresses(self):
        try:
            if not self._addresses:
                self._addresses = HyperdriveClient(**self._config).addresses()
            return self._addresses
        except ConnectionError:
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
            logger.critical("Can't run hyperdrive executable %r. "
                            "Make sure path is correct and check "
                            "if it starts correctly.",
                            ' '.join(self._command))
            sys.exit(1)

        if process.poll() is None:
            self._monitor.add_child_processes(process)
        else:
            raise RuntimeError("Cannot start {}".format(self._executable))
