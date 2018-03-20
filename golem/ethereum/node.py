import logging
import os
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from web3 import Web3, IPCProvider, HTTPProvider

from golem.core.common import is_windows, DEVNULL, SUBPROCESS_STARTUP_INFO
from golem.ethereum.web3.middleware import RemoteRPCErrorMiddlewareBuilder
from golem.ethereum.web3.providers import ProviderProxy
from golem.report import report_calls, Component
from golem.utils import find_free_net_port
from golem.utils import tee_target

log = logging.getLogger('golem.ethereum')


NODE_LIST = [
    'https://rinkeby.golem.network:55555',
    'http://188.165.227.180:55555',
    'http://94.23.17.170:55555',
    'http://94.23.57.58:55555',
]


def get_public_nodes(mainnet: bool):
    """Returns public geth RPC addresses"""
    if mainnet:
        raise Exception('Mainnet not supported yet')
    addr_list = NODE_LIST[:]
    random.shuffle(addr_list)
    return addr_list


class NodeProcess(object):

    CONNECTION_TIMEOUT = 10

    SUBPROCESS_PIPES = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=DEVNULL
    )

    def __init__(self, datadir, mainnet=False, addr=None, start_node=False):
        """
        :param datadir: working directory
        :param addr: address of a geth instance to connect with
        :param start_node: start a new geth node
        """
        self.datadir = datadir
        self.start_node = start_node
        self._mainnet = mainnet
        self.web3 = None  # web3 client interface
        self.provider_proxy = ProviderProxy()  # web3 ipc / rpc provider
        self.addr_list = [addr] if addr else get_public_nodes(mainnet)

        self.__ps = None  # child process

    def is_running(self):
        return self.__ps is not None

    @report_calls(Component.ethereum, 'node.start')
    def start(self, start_port=None):
        if self.__ps is not None:
            raise RuntimeError("Ethereum node already started by us")

        if self.start_node:
            provider = self._create_local_ipc_provider(start_port)
        else:
            provider = self._create_remote_rpc_provider()

        self.provider_proxy.provider = provider
        self.web3 = Web3(self.provider_proxy)

        middleware_builder = RemoteRPCErrorMiddlewareBuilder(
            self._handle_remote_rpc_provider_failure)
        self.web3.middleware_stack.add(middleware_builder.build)

        started = time.time()
        deadline = started + self.CONNECTION_TIMEOUT

        while not self.is_connected():
            if time.time() > deadline:
                return self._start_timed_out(provider, start_port)
            time.sleep(0.1)

        log.info("Connected to node in %ss", time.time() - started)

        return None

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

    def is_connected(self):
        try:
            return self.web3.isConnected()
        except AssertionError:  # thrown if not all required APIs are available
            return False

    def _start_timed_out(self, provider, start_port):
        if not self.start_node:
            self.start_node = not self.addr_list
            return self.start(start_port)
        raise OSError("Cannot connect to geth: {}".format(provider))

    def _create_local_ipc_provider(self, start_port=None):  # noqa pylint: disable=too-many-locals
        chain = 'mainnet' if self._mainnet else 'rinkeby'
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
            ipc_path = r'\\.\pipe\{}'.format(self.start_node)

        args = [
            prog,
            '--datadir={}'.format(geth_datadir),
            '--cache=32',
            '--syncmode=light',
            '--port={}'.format(start_port),
            '--ipcpath={}'.format(ipc_path),
            '--nousb',
            '--verbosity', '3',
        ]
        if not self._mainnet:
            args.append('--rinkeby')

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

        return IPCProvider(ipc_path)

    def _create_remote_rpc_provider(self):
        addr = self.addr_list.pop()
        log.info('GETH: connecting to remote RPC interface at %s', addr)
        return ProviderProxy(HTTPProvider(addr))

    def _handle_remote_rpc_provider_failure(self, exc):
        from golem.core.async import async_run, AsyncRequest
        log.warning('GETH: reconnecting to another provider (%r)', exc)

        self.provider_proxy.provider = None

        request = AsyncRequest(self.start)
        async_run(request).addErrback(
            lambda err: self._handle_remote_rpc_provider_failure(err)
        )

    @staticmethod
    def _find_geth():
        geth = shutil.which('geth')
        if not geth:
            raise OSError("Ethereum client 'geth' not found")

        log.info("geth {}:".format(geth))
        return geth
