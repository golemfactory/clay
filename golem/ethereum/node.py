import atexit
import json
import logging
import os
import time
from os import path
from subprocess import Popen

import appdirs
import psutil

from golem.environments.utils import find_program
from golem.utils import find_free_net_port

log = logging.getLogger('golem.ethereum')


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
        self.__datadir = datadir
        self.__subprocess = None
        self.rpcport = None

    def is_running(self):
        return self.__subprocess is not None

    def start(self, rpc, extra_args=None):
        if self.__subprocess:
            return

        assert not self.rpcport
        program = find_program('geth')
        assert program  # TODO: Replace with a nice exception
        # Data dir must be set the class user to allow multiple nodes running
        basedir = path.dirname(__file__)
        genesis_file = path.join(basedir, 'genesis_golem.json')
        args = [
            program,
            '--datadir', self.__datadir,
            '--networkid', '9',
            '--genesis', genesis_file,
            '--nodiscover',
            '--gasprice', '0',
            '--verbosity', '0',
        ]

        if rpc:
            self.rpcport = find_free_net_port(9001)
            args += [
                '--rpc',
                '--rpcport', str(self.rpcport)
            ]

        if extra_args:
            args += extra_args

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


class FullNode(object):
    def __init__(self):
        datadir = path.join(NodeProcess.DEFAULT_DATADIR, 'full_node')
        basedir = path.dirname(__file__)
        mining_script = path.join(basedir, 'mine_pending_transactions.json')
        args = [
            '--nodekeyhex', '476f6c656d204661756365742020202020202020202020202020202020202020',
            '--etherbase', 'cfdc7367e9ece2588afe4f530a9adaa69d5eaedb',
            'js', mining_script,
        ]
        self.proc = NodeProcess(nodes=[], datadir=datadir)
        self.proc.start(rpc=False, extra_args=args)

if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(level=logging.INFO)
    FullNode()

    # The best I have to make the node running untill interrupted.
    signal.signal(signal.SIGINT, lambda *unused: sys.exit())
    while True:
        time.sleep(60 * 60 * 24)
