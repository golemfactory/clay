import atexit
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time

from golem.core.common import is_windows, DEVNULL, SUBPROCESS_STARTUP_INFO
from golem.environments.utils import find_program
from golem.report import report_calls, Component
from golem.utils import find_free_net_port
from golem.utils import tee_target

log = logging.getLogger('golem.ethereum')


class NodeProcess(object):

    CONNECTION_TIMEOUT = 10
    CHAIN = 'rinkeby'

    SUBPROCESS_PIPES = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=DEVNULL
    )

    def __init__(self, datadir):
        """
        :param datadir: working directory
        """
        self.datadir = datadir

        self.__ps = None  # child process

    def is_running(self):
        return self.__ps is not None

    @report_calls(Component.ethereum, 'node.start')
    def start(self, start_port=None):
        if self.__ps is not None:
            raise RuntimeError("Ethereum node already started by us")

        ipc_path = self._create_local_geth(self.CHAIN, start_port)
        atexit.register(lambda: self.stop())
        return ipc_path

    @report_calls(Component.ethereum, 'node.stop')
    def stop(self):
        if self.__ps:
            start_time = time.clock()

            try:
                self.__ps.terminate()
                self.__ps.wait()
            except subprocess.NoSuchProcess:
                log.warn("Cannot terminate node: process {} no longer exists"
                         .format(self.__ps.pid))

            self.__ps = None
            duration = time.clock() - start_time
            log.info("Node terminated in {:.2f} s".format(duration))

    def _create_local_geth(self, chain, start_port=None):  # noqa pylint: disable=too-many-locals
        prog = self._find_geth()

        # Init geth datadir
        geth_log_dir = os.path.join(self.datadir, "logs")
        geth_log_path = os.path.join(geth_log_dir, "geth.log")
        geth_datadir = os.path.join(self.datadir, 'ethereum', chain)

        os.makedirs(geth_log_dir, exist_ok=True)

        if start_port is None:
            start_port = find_free_net_port()

        # Build unique IPC/socket path. We have to use system temp dir to
        # make sure the path has length shorter that ~100 chars.
        tempdir = tempfile.gettempdir()
        ipc_file = '{}-{}'.format(chain, start_port)
        ipc_path = os.path.join(tempdir, ipc_file)

        if is_windows():
            # On Windows expand to full named pipe path.
            ipc_path = r'\\.\pipe\{}'.format(True)

        args = [
            prog,
            '--datadir={}'.format(geth_datadir),
            '--cache=32',
            '--syncmode=light',
            '--rinkeby',
            '--port={}'.format(start_port),
            '--ipcpath={}'.format(ipc_path),
            '--nousb',
            '--verbosity', '3',
        ]

        log.info("Starting Ethereum node: `{}`".format(" ".join(args)))
        self.__ps = subprocess.Popen(args, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     stdin=DEVNULL,
                                     startupinfo=SUBPROCESS_STARTUP_INFO)

        tee_kwargs = {
            'proc': self.__ps,
            'path': geth_log_path,
        }
        channels = (
            ('GETH', self.__ps.stderr, sys.stderr),
            ('GETHO', self.__ps.stdout, sys.stdout),
        )
        for prefix, in_, out in channels:
            tee_kwargs['prefix'] = prefix + ': '
            tee_kwargs['input_stream'] = in_
            tee_kwargs['stream'] = out
            thread_name = 'tee-' + prefix
            tee_thread = threading.Thread(name=thread_name, target=tee_target,
                                          kwargs=tee_kwargs)
            tee_thread.start()

        started = time.time()
        deadline = started + self.CONNECTION_TIMEOUT

        while not os.path.exists(ipc_path) and time.time() < deadline:
            time.sleep(0.2)
        if not os.path.exists(ipc_path):
            raise Exception(
                'Local Geth error: {} does not exist'.format(ipc_path))

        log.info('Connected to local Geth in %ss', time.time() - started)

        return ipc_path

    def _find_geth(self):
        geth = find_program('geth')
        if not geth:
            raise OSError("Ethereum client 'geth' not found")

        log.info("geth {}:".format(geth))
        return geth
