from __future__ import division

import atexit
import logging
import re
import subprocess
import time
import tempfile
from datetime import datetime
from distutils.version import StrictVersion
from os import path

import requests
from ethereum.keys import privtoaddr
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from web3 import Web3, IPCProvider

from golem.core.common import is_windows
from golem.core.crypto import privtopub
from golem.environments.utils import find_program
from golem.utils import find_free_net_port

log = logging.getLogger('golem.ethereum')


def ropsten_faucet_donate(addr):
    addr = normalize_address(addr)
    URL_TEMPLATE = "http://188.165.227.180:4000/donate/{}"
    request = URL_TEMPLATE.format(addr.encode('hex'))
    response = requests.get(request)
    if response.status_code != 200:
        log.error("Ropsten Faucet error code {}".format(response.status_code))
        return False
    response = response.json()
    if response['paydate'] == 0:
        log.warning("Ropsten Faucet warning {}".format(response['message']))
        return False
    # The paydate is not actually very reliable, usually some day in the past.
    paydate = datetime.fromtimestamp(response['paydate'])
    amount = int(response['amount']) / denoms.ether
    log.info("Faucet: {:.6f} ETH on {}".format(amount, paydate))
    return True


class Faucet(object):
    PRIVKEY = "{:32}".format("Golem Faucet")
    PUBKEY = privtopub(PRIVKEY)
    ADDR = privtoaddr(PRIVKEY)

    @staticmethod
    def gimme_money(ethnode, addr, value):
        nonce = ethnode.get_transaction_count('0x' + Faucet.ADDR.encode('hex'))
        addr = normalize_address(addr)
        tx = Transaction(nonce, 1, 21000, addr, value, '')
        tx.sign(Faucet.PRIVKEY)
        h = ethnode.send(tx)
        log.info("Faucet --({} ETH)--> {} ({})".format(value / denoms.ether,
                 '0x' + addr.encode('hex'), h))
        h = h[2:].decode('hex')
        return h


class NodeProcess(object):
    MIN_GETH_VERSION = '1.6.1'
    MAX_GETH_VERSION = '1.6.999'
    IPC_CONNECTION_TIMEOUT = 10

    def __init__(self, datadir):
        self.datadir = datadir
        self.__prog = find_program('geth')
        if not self.__prog:
            raise OSError("Ethereum client 'geth' not found")
        output, _ = subprocess.Popen([self.__prog, 'version'],
                                     stdout=subprocess.PIPE).communicate()
        match = re.search("Version: (\d+\.\d+\.\d+)", output).group(1)
        ver = StrictVersion(match)
        if ver < self.MIN_GETH_VERSION or ver > self.MAX_GETH_VERSION:
            e_description = "Incompatible geth version: {}."\
                " Expected >= {} and <= {}".format(
                    ver,
                    self.MIN_GETH_VERSION,
                    self.MAX_GETH_VERSION
                )
            raise OSError(e_description)
        log.info("geth {}: {}".format(ver, self.__prog))

        self.__ps = None  # child process

    def is_running(self):
        return self.__ps is not None

    def start(self):
        if self.__ps is not None:
            raise RuntimeError("Ethereum node already started by us")

        # Init geth datadir
        chain = 'rinkeby'
        geth_datadir = path.join(self.datadir, 'ethereum', chain)
        datadir_arg = '--datadir={}'.format(geth_datadir)
        this_dir = path.dirname(__file__)
        init_file = path.join(this_dir, chain + '.json')
        log.info("init file: {}".format(init_file))

        init_subp = subprocess.Popen([
            self.__prog,
            datadir_arg,
            'init', init_file
        ])
        init_subp.wait()
        if init_subp.returncode != 0:
            raise OSError(
                "geth init failed with code {}".format(init_subp.returncode))

        port = find_free_net_port()

        # Build unique IPC/socket path. We have to use system temp dir to
        # make sure the path has length shorter that ~100 chars.
        tempdir = tempfile.gettempdir()
        ipc_file = '{}-{}'.format(chain, port)
        ipc_path = path.join(tempdir, ipc_file)

        args = [
            self.__prog,
            datadir_arg,
            '--cache=32',
            '--syncmode=light',
            '--rinkeby',
            '--port={}'.format(port),
            '--ipcpath={}'.format(ipc_path),
            '--nousb',
            '--verbosity', '3',
        ]

        log.info("Starting Ethereum node: `{}`".format(" ".join(args)))

        self.__ps = subprocess.Popen(args, close_fds=True)
        atexit.register(lambda: self.stop())

        if is_windows():
            # On Windows expand to full named pipe path.
            ipc_path = r'\\.\pipe\{}'.format(ipc_path)

        self.web3 = Web3(IPCProvider(ipc_path))
        CHECK_PERIOD = 0.1
        wait_time = 0
        while not self.web3.isConnected():
            if wait_time > self.IPC_CONNECTION_TIMEOUT:
                raise OSError("Cannot connect to geth at {}".format(ipc_path))
            time.sleep(CHECK_PERIOD)
            wait_time += CHECK_PERIOD

        identified_chain = self.identify_chain()
        if identified_chain != chain:
            raise OSError("Wrong '{}' Ethereum chain".format(identified_chain))

        log.info("Node started in {} s".format(wait_time))

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

    def identify_chain(self):
        """Check what chain the Ethereum node is running."""
        GENESES = {
            u'0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3': 'mainnet',  # noqa
            u'0x41941023680923e0fe4d74a34bdac8141f2540e3ae90623718e47d66d1ca4a2d': 'ropsten',  # noqa
            u'0x6341fd3daf94b748c72ced5a5b26028f2474f5f00d824504e4fa37a75767e177': 'rinkeby',  # noqa
        }
        genesis = self.web3.eth.getBlock(0)['hash']
        chain = GENESES.get(genesis, 'unknown')
        log.info("{} chain ({})".format(chain, genesis))
        return chain
