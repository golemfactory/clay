import atexit
import logging
import time
from os import path
from subprocess import Popen

import appdirs
import psutil
from eth_rpc_client import Client as EthereumRpcClient


log = logging.getLogger('golem.eth.rpc')


def find_free_net_port(start_port):
    open_ports = set(c.laddr[1] for c in psutil.net_connections())
    while start_port in open_ports:
        start_port += 1
    return start_port


class Client(EthereumRpcClient):

    __client_subprocess = None
    __client_rpc_port = None

    @staticmethod
    def __start_client_subprocess():
        if not Client.__client_subprocess:
            assert not Client.__client_rpc_port
            rpcport = find_free_net_port(9001)
            basedir = path.dirname(__file__)
            # Data dir must be set the class user to allow multiple nodes running
            datadir = path.join(appdirs.user_data_dir('golem'), 'ethereum9')
            genesis_file = path.join(basedir, 'genesis_golem.json')
            peers_file = path.join(basedir, 'peers.js')
            args = [
                'geth',
                '--datadir', datadir,
                '--rpc',
                '--rpcport', str(rpcport),
                '--networkid', '9',
                '--genesis', genesis_file,
                '--nodiscover',
                '--verbosity', '0',
                'js', peers_file
            ]

            Client.__client_subprocess = Popen(args)
            Client.__client_rpc_port = rpcport
            atexit.register(Client.__terminate_client_subprocess)
            # FIXME: We should check if the process was started.
            ps = psutil.Process(Client.__client_subprocess.pid)
            WAIT_PERIOD = 0.01
            wait_time = 0
            while True:
                # FIXME: Add timeout limit, we don't want to loop here forever.
                time.sleep(WAIT_PERIOD)
                if rpcport in set(c.laddr[1] for c in ps.connections('tcp')):
                    break
                wait_time += WAIT_PERIOD
            log.info("Ethereum client started in {} s: `{}`"
                     .format(wait_time, " ".join(args)))

    @staticmethod
    def __terminate_client_subprocess():
        if Client.__client_subprocess:
            start_time = time.clock()
            Client.__client_subprocess.terminate()
            Client.__client_subprocess.wait()
            Client.__client_subprocess = None
            Client.__client_rpc_port = None
            duration = time.clock() - start_time
            log.info("Ethereum client terminated in {:.2f} s".format(duration))

    def __init__(self):
        self.__start_client_subprocess()
        assert self.__client_subprocess and self.__client_rpc_port
        super(Client, self).__init__(port=self.__client_rpc_port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    c = Client()
    prev = 0
    while True:
        time.sleep(1)
        n = c.get_block_number()
        print "Block", n
        if n > 0 and prev != n:
            break
        prev = n
