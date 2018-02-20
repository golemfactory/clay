import copy
import logging
import os
import subprocess
import sys
import time
from typing import Optional

import requests
import semantic_version

from golem.core.common import DEVNULL, SUBPROCESS_STARTUP_INFO
from golem.core.processmonitor import ProcessMonitor
from golem.network.hyperdrive.client import HyperdriveClient
from golem.report import report_calls, Component

logger = logging.getLogger('golem.resources')


GOLEM_HYPERDRIVE_VERSION = '0.2.4'


class HyperdriveDaemonManager(object):

    _executable = 'hyperg'
    _min_version = semantic_version.Version(GOLEM_HYPERDRIVE_VERSION)

    def __init__(self, datadir, **hyperdrive_config):
        super(HyperdriveDaemonManager, self).__init__()

        self._addresses = None
        self._config = hyperdrive_config

        # monitor and restart if process dies
        self._monitor = ProcessMonitor()
        self._monitor.add_callbacks(self._start)

        self._dir = os.path.join(datadir, self._executable)
        self._client = HyperdriveClient(**self._config)

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
            return self._get_addresses()
        except requests.ConnectionError:
            logger.warning('Cannot connect to Hyperdrive daemon')
            return dict()

    def version(self) -> Optional[semantic_version.Version]:
        try:
            output = self._client.id()['version']
        except requests.ConnectionError:  # not running
            output = None
        except KeyError:  # API version too low - no version in response
            # FIXME: return None after upgrading to 0.2.5
            output = None

        if not output:
            try:
                command = [self._executable, '--version']
                output = subprocess.check_output(command)
                output = output.decode('utf-8')
            except (OSError, UnicodeDecodeError):
                self._critical_error()

        return semantic_version.Version(output.strip())

    def _get_addresses(self):
        if not self._addresses:
            self._addresses = self._client.addresses()
        return self._addresses

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

    @report_calls(Component.hyperdrive, 'instance.connect')
    def _start(self, *_):
        self._check_version()

        # do not supervise already running processes
        addresses = self.addresses()
        if addresses:
            return

        process = self._create_sub()

        if process.poll() is None:
            self._monitor.add_child_processes(process)
            self._wait()
        else:
            raise RuntimeError("Cannot start {}".format(self._executable))

    @report_calls(Component.hyperdrive, 'instance.version')
    def _check_version(self):
        version = self.version()
        if version < self._min_version:
            raise RuntimeError('HyperG version {} is required'
                               .format(self._min_version))

    @report_calls(Component.hyperdrive, 'instance.check')
    def _create_sub(self):
        try:
            os.makedirs(self._dir, exist_ok=True)
            return subprocess.Popen(self._command, stdin=DEVNULL,
                                    stdout=None, stderr=None,
                                    startupinfo=SUBPROCESS_STARTUP_INFO)
        except OSError:
            return self._critical_error()

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
