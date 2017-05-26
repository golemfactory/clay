import atexit
import logging
import signal
import subprocess
import sys

import os
from requests import ConnectionError

from golem.core.processmonitor import ProcessMonitor
from golem.network.hyperdrive.client import HyperdriveClient

logger = logging.getLogger('golem.resources')


class HyperdriveDaemonManager(object):

    _executable = 'hyperg'

    def __init__(self, datadir, **hyperdrive_config):
        super(HyperdriveDaemonManager, self).__init__()

        self._config = hyperdrive_config

        # monitor and restart if process dies
        self._monitor = ProcessMonitor()
        self._monitor.add_callbacks(self._start)

        self._dir = os.path.join(datadir, self._executable)
        self._command = [self._executable, '--db', self._dir]

    def addresses(self):
        try:
            return HyperdriveClient(**self._config).addresses()
        except ConnectionError:
            return dict()

    def ports(self, addresses=None):
        if addresses is None:
            addresses = self.addresses() or dict()

        return set(value['port'] for key, value
                   in addresses.iteritems()
                   if value and value.get('port'))

    def start(self):
        atexit.register(self.stop)

        signal.signal(signal.SIGABRT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        self._monitor.start()
        return self._start()

    def stop(self, *_):
        self._monitor.exit()

    def _start(self, *_):
        # do not supervise already running processes
        addresses = self.addresses()
        if addresses:
            return self.ports(addresses)

        try:
            if not os.path.exists(self._dir):
                os.makedirs(self._dir)
            process = subprocess.Popen(self._command)
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

        return self.ports()
