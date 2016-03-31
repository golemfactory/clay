import atexit
import json
import logging
import os
import time
from os import path
from subprocess import Popen

import appdirs
import psutil

from devp2p.crypto import privtopub
from ethereum.keys import privtoaddr
from ethereum.transactions import Transaction
from ethereum.utils import normalize_address

from golem.environments.utils import find_program
from golem.utils import find_free_net_port

log = logging.getLogger('golem.ethereum')


class Faucet(object):
    PRIVKEY = "{:32}".format("Golem Faucet")
    assert len(PRIVKEY) == 32
    PUBKEY = privtopub(PRIVKEY)
    ADDR = privtoaddr(PRIVKEY)

    @staticmethod
    def gimme_money(ethnode, addr, value):
        nonce = ethnode.get_transaction_count(Faucet.ADDR.encode('hex'))
        addr = normalize_address(addr)
        tx = Transaction(nonce, 1, 21000, addr, value, '')
        tx.sign(Faucet.PRIVKEY)
        h = ethnode.send(tx)
        log.info("Faucet --({} ETH)--> {} ({})".format(float(value) / 10**18,
                                                       addr.encode('hex'), h))
        h = h[2:].decode('hex')
        assert h == tx.hash
        return h

    @staticmethod
    def deploy_contract(ethnode, init_code):
        nonce = ethnode.get_transaction_count(Faucet.ADDR.encode('hex'))
        tx = Transaction(nonce, 0, 3141592, to='', value=0, data=init_code)
        tx.sign(Faucet.PRIVKEY)
        ethnode.send(tx)
        return tx.creates


class NodeProcess(object):

    DEFAULT_DATADIR = path.join(appdirs.user_data_dir('golem'), 'ethereum9')

    def __init__(self, nodes, datadir=DEFAULT_DATADIR):
        if not path.exists(datadir):
            os.makedirs(datadir)
        assert path.isdir(datadir)
        if nodes:
            nodes_file = path.join(datadir, 'static-nodes.json')
            if not path.exists(nodes_file):
                json.dump(nodes, open(nodes_file, 'w'))
        self.datadir = datadir
        self.__subprocess = None
        self.rpcport = None

    def is_running(self):
        return self.__subprocess is not None

    def start(self, rpc, mining=False, nodekey=None):
        if self.__subprocess:
            return

        assert not self.rpcport
        program = find_program('geth')
        assert program  # TODO: Replace with a nice exception
        # Data dir must be set the class user to allow multiple nodes running
        basedir = path.dirname(__file__)
        genesis_file = path.join(basedir, 'genesis_golem.json')
        self.port = find_free_net_port()
        args = [
            program,
            '--datadir', self.datadir,
            '--networkid', '9',
            '--port', str(self.port),
            '--genesis', genesis_file,
            '--nodiscover',
            '--gasprice', '0',
            '--verbosity', '6',
        ]

        if rpc:
            self.rpcport = find_free_net_port()
            args += [
                '--rpc',
                '--rpcport', str(self.rpcport)
            ]

        if nodekey:
            self.pubkey = privtopub(nodekey)
            args += [
                '--nodekeyhex', nodekey.encode('hex'),
            ]

        if mining:
            mining_script = path.join(basedir, 'mine_pending_transactions.js')
            args += [
                '--etherbase', Faucet.ADDR.encode('hex'),
                'js', mining_script,
            ]

        self.__subprocess = Popen(args)
        atexit.register(lambda: self.stop())
        # FIXME: We should check if the process was started.
        ps = psutil.Process(self.__subprocess.pid)
        WAIT_PERIOD = 0.01
        wait_time = 0
        while True:
            # FIXME: Add timeout limit, we don't want to loop here forever.
            time.sleep(WAIT_PERIOD)
            wait_time += WAIT_PERIOD
            if not self.rpcport:
                break
            if self.rpcport in set(c.laddr[1] for c in ps.connections('tcp')):
                break
        log.info("Node started in {} s: `{}`".format(wait_time, " ".join(args)))

    def stop(self):
        if self.__subprocess:
            start_time = time.clock()
            self.__subprocess.terminate()
            self.__subprocess.wait()
            self.__subprocess = None
            self.rpcport = None
            duration = time.clock() - start_time
            log.info("Node terminated in {:.2f} s".format(duration))


# TODO: Refactor, use inheritance FullNode(NodeProcess)
class FullNode(object):
    def __init__(self, datadir=None):
        if not datadir:
            datadir = path.join(NodeProcess.DEFAULT_DATADIR, 'full_node')
        self.proc = NodeProcess(nodes=[], datadir=datadir)
        self.proc.start(rpc=False, mining=True, nodekey=Faucet.PRIVKEY)

if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(level=logging.INFO)
    FullNode()

    # The best I have to make the node running untill interrupted.
    handler = lambda *unused: sys.exit()
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    while True:
        time.sleep(60 * 60 * 24)
