from __future__ import division

import atexit
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from distutils.version import StrictVersion

import requests
import sys
from ethereum.keys import privtoaddr
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address, denoms
from web3 import Web3, IPCProvider
from web3.providers.ipc import get_default_ipc_path

from golem.core.common import is_windows
from golem.core.crypto import privtopub
from golem.environments.utils import find_program

log = logging.getLogger('golem.ethereum')


def ropsten_faucet_donate(addr):
    addr = normalize_address(addr)
    URL_TEMPLATE = "http://188.165.227.180:3000/donate/{}"
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
    MIN_GETH_VERSION = '1.6.1'
    MAX_GETH_VERSION = '1.6.999'
    BOOT_NODES = [
        "enode://c8109b20aaac3cf8a793c1d1de505ca8b0a7e112734ef62f169bb4f2408af10ba31efce9fdb2b5b16499111a04a6204c331ffb8a131e6d19c79481884d162e3e@188.165.227.180:30333",
        "enode://20c9ad97c081d63397d7b685a412227a40e23c8bdc6688c6f37e97cfbc22d2b4d1db1510d8f61e6a8866ad7f0e17c02b14182d37ea7c3c8b9c2683aeb6b733a1@52.169.14.227:30303",
        "enode://6ce05930c72abc632c58e2e4324f7c7ea478cec0ed4fa2528982cf34483094e9cbc9216e7aa349691242576d552a2a56aaeae426c5303ded677ce455ba1acd9d@13.84.180.240:30303"
    ]

    testnet = True

    def __init__(self, datadir):
        self.datadir = datadir
        log.info("Find geth node or start our own")
        self.__prog = find_program('geth')
        if not self.__prog:
            raise OSError("Ethereum client 'geth' not found")
        output, _ = subprocess.Popen([self.__prog, 'version'],
                                     stdout=subprocess.PIPE).communicate()
        ver = StrictVersion(re.search("Version: (\d+\.\d+\.\d+)", output).group(1))
        if ver < self.MIN_GETH_VERSION or ver > self.MAX_GETH_VERSION:
            raise OSError("Incompatible Ethereum client 'geth' version: {}".format(ver))
        log.info("geth version {}".format(ver))

        self.__ps = None  # child process
        self.system_geth = False  # some external geth, not a child process

    def is_running(self):
        return self.__ps is not None or self.system_geth

    def start(self):
        if self.__ps is not None:
            raise RuntimeError("Ethereum node already started by us")

        if is_geth_listening(self.testnet):
            the_chain = "mainnet"
            if self.testnet:
                the_chain = "ropsten"
            running_chain = identify_chain(self.testnet)
            if running_chain == the_chain:
                log.info("Using existing Ethereum node {}".format(running_chain))
                self.system_geth = True
                return
            else:
                log.error("Some other Ethereum instance is listening...")
                log.error("It seems to be running wrong chain!")
                log.error("Looking for {}; geth is running {}".format(the_chain, running_chain))
                msg = "Ethereum client runs wrong chain: {}".format(running_chain)
                raise OSError(msg)
        elif self.testnet:
            self.save_static_nodes(testnet=True)

        log.info("Will attempt to start new Ethereum node")

        args = [
            self.__prog,
            '--light',
            '--testnet',
            '--bootnodes', ','.join(self.BOOT_NODES),
            '--verbosity', '3',
        ]

        self.__ps = subprocess.Popen(args, close_fds=True)
        atexit.register(lambda: self.stop())
        WAIT_PERIOD = 0.1
        wait_time = 0
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
            duration = time.clock() - start_time
            log.info("Node terminated in {:.2f} s".format(duration))

    def save_static_nodes(self, testnet=False):
        datadir = get_default_geth_path(testnet=testnet)

        if not os.path.exists(datadir):
            os.makedirs(datadir)

        static_nodes_path = os.path.join(datadir, "static-nodes.json")

        log.debug("Saving boot nodes to {}".format(static_nodes_path))
        with open(static_nodes_path, 'w') as static_nodes_file:
            static_nodes_file.write(json.dumps(self.BOOT_NODES))


def identify_chain(testnet):
    """
    Check if chain which external Ethereum node is running
    is one we want to use.
    """
    web3 = Web3(IPCProvider(testnet=testnet))
    ropsten = u'0x41941023680923e0fe4d74a34bdac8141f2540e3ae90623718e47d66d1ca4a2d'
    mainnet = u'0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3'
    block = web3.eth.getBlock(0)
    if testnet and block['hash'] == ropsten:
        return "ropsten"
    if not testnet and block['hash'] == mainnet:
        return "mainnet"
    return None


def is_geth_listening(testnet):
    web3 = Web3(IPCProvider(testnet=testnet))
    return web3.isConnected()


def get_default_geth_path(testnet=False):
    if sys.platform == 'win32':
        return os.path.expanduser(os.path.join(
            "~",
            "AppData",
            "Roaming",
            "Ethereum",
            "testnet" if testnet else ""
        ))
    else:
        # if not using Named Pipes, remove "geth.ipc" from the returned path
        return os.path.dirname(get_default_ipc_path(testnet))
