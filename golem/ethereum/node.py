from __future__ import division

import atexit
import logging
import re
import requests
import socket
import subprocess
import time
from datetime import datetime
from distutils.version import StrictVersion

from devp2p.crypto import privtopub
from ethereum.keys import privtoaddr
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from web3.providers.ipc import get_default_ipc_path

from golem.environments.utils import find_program
from golem.utils import find_free_net_port

log = logging.getLogger('golem.ethereum')


def ropsten_faucet_donate(addr):
    addr = normalize_address(addr)
    URL_TEMPLATE = "http://faucet.ropsten.be:3001/donate/{}"
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
    log.info("Ropsten Faucet: {:.6f} ETH on {}".format(amount, paydate))
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
    MIN_GETH_VERSION = '1.5.0'
    MAX_GETH_VERSION = '1.5.999'

    def __init__(self):
        self.port = None
        self.__prog = find_program('geth')
        if not self.__prog:
            raise OSError("Ethereum client 'geth' not found")
        output, _ = subprocess.Popen([self.__prog, 'version'],
                                     stdout=subprocess.PIPE).communicate()
        ver = StrictVersion(re.search("Version: (\d+\.\d+\.\d+)", output).group(1))
        if ver < self.MIN_GETH_VERSION or ver > self.MAX_GETH_VERSION:
            raise OSError("Incompatible Ethereum client 'geth' version: {}".format(ver))
        log.info("geth version {}".format(ver))

        self.__ps = None

    def is_running(self):
        return self.__ps is not None

    def start(self, port=None):
        if self.is_running():
            raise RuntimeError("Ethereum node already started")

        if not port:
            port = find_free_net_port()

        self.port = port
        args = [
            self.__prog,
            '--testnet',
            '--port', str(self.port),
            '--verbosity', '3',
        ]
        self.testnet = True

        self.__ps = subprocess.Popen(args, close_fds=True)
        atexit.register(lambda: self.stop())
        WAIT_PERIOD = 0.1
        wait_time = 0
        from web3 import Web3, IPCProvider
        web3 = Web3(IPCProvider(testnet=self.testnet))
        while not web3.isConnected():
            # FIXME: Add timeout limit, we don't want to loop here forever.
            time.sleep(WAIT_PERIOD)
            wait_time += WAIT_PERIOD
        log.info("Node started in {} s: `{}`".format(wait_time, " ".join(args)))

    def stop(self):
        if self.__ps:
            start_time = time.clock()

            try:
                self.__ps.terminate()
                self.__ps.wait()
            except subprocess.NoSuchProcess:
                log.warn("Cannot terminate node: process {} no longer exists".format(self.__ps.pid))

            self.__ps = None
            self.rpcport = None
            duration = time.clock() - start_time
            log.info("Node terminated in {:.2f} s".format(duration))
