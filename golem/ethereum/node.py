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

    def __init__(self, nodes, datadir=None):
        if not datadir:
            datadir = path.join(appdirs.user_data_dir('golem'), 'ethereum9')
        if not path.exists(datadir):
            os.makedirs(datadir)
        assert path.isdir(datadir)
        nodes_file = path.join(datadir, 'static-nodes.json')
        if not path.exists(nodes_file):
            json.dump(nodes, open(nodes_file, 'w'))
        self.__datadir = datadir
        self.__subprocess = None
        self.rpcport = None

    def is_running(self):
        return self.__subprocess is not None

    def start(self):
        if self.__subprocess:
            return

        assert not self.rpcport
        program = find_program('geth')
        assert program  # TODO: Replace with a nice exception
        rpcport = find_free_net_port(9001)
        # Data dir must be set the class user to allow multiple nodes running
        basedir = path.dirname(__file__)
        genesis_file = path.join(basedir, 'genesis_golem.json')
        args = [
            program,
            '--datadir', self.__datadir,
            '--rpc',
            '--rpcport', str(rpcport),
            '--networkid', '9',
            '--genesis', genesis_file,
            '--nodiscover',
            '--gasprice', '0',
            '--verbosity', '0',
        ]

        self.__subprocess = Popen(args)
        self.rpcport = rpcport
        atexit.register(lambda: self.stop())
        # FIXME: We should check if the process was started.
        ps = psutil.Process(self.__subprocess.pid)
        WAIT_PERIOD = 0.01
        wait_time = 0
        while True:
            # FIXME: Add timeout limit, we don't want to loop here forever.
            time.sleep(WAIT_PERIOD)
            if rpcport in set(c.laddr[1] for c in ps.connections('tcp')):
                break
            wait_time += WAIT_PERIOD
        log.info("Ethereum node started in {} s: `{}`"
                 .format(wait_time, " ".join(args)))

    def stop(self):
        if self.__subprocess:
            start_time = time.clock()
            self.__subprocess.terminate()
            self.__subprocess.wait()
            self.__subprocess = None
            self.rpcport = None
            duration = time.clock() - start_time
            log.info("Ethereum node terminated in {:.2f} s".format(duration))
