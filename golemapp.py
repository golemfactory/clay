#!/usr/bin/env python
import sys
import logging
from multiprocessing import freeze_support
import click
from ethereum import slogging

from golem.core.variables import PROTOCOL_CONST
from golem.node import OptNode


# Monkey patch for ethereum.slogging.
# SLogger aggressively mess up with python looger.
# This patch is to settle down this.
# It should be done before any SLogger is created.
orig_getLogger = slogging.SManager.getLogger


def monkey_patched_getLogger(*args, **kwargs):
    orig_class = logging.getLoggerClass()
    result = orig_getLogger(*args, **kwargs)
    logging.setLoggerClass(orig_class)
    return result


slogging.SManager.getLogger = monkey_patched_getLogger


@click.command()
@click.option('--payments/--nopayments', default=True)
@click.option('--monitor/--nomonitor', default=True)
@click.option('--datadir', '-d', type=click.Path(
    file_okay=False,
    writable=True
))
@click.option('--protocol_id', type=click.INT,
              callback=PROTOCOL_CONST.patch_protocol_id,
              is_eager=True,
              expose_value=False,
              help="Golem nodes will connect "
                   "only inside sub-network with "
                   "a given protocol id")
@click.option('--node-address', '-a', multiple=False, type=click.STRING,
              callback=OptNode.parse_node_addr,
              help="Network address to use for this node")
@click.option('--rpc-address', '-r', multiple=False,
              callback=OptNode.parse_rpc_address,
              help="RPC server address to use: <ipv4_addr>:<port> or "
                   "[<ipv6_addr>]:<port>")
@click.option('--peer', '-p', multiple=True, callback=OptNode.parse_peer,
              help="Connect with given peer: <ipv4_addr>:<port> or "
                   "[<ipv6_addr>]:<port>")
@click.option('--start-geth', is_flag=True, default=False,
              help="Start geth node")
@click.option('--version', '-v', is_flag=True, default=False,
              help="Show Golem version information")
# Python flags, needed by crossbar (package only)
@click.option('-m', nargs=1, default=None)
@click.option('--geth-port', default=None)
@click.option('-u', is_flag=True, default=False, expose_value=False)
# Multiprocessing option (ignored)
@click.option('--multiprocessing-fork', nargs=1, expose_value=False)
# Crossbar arguments (package only)
@click.option('--cbdir', expose_value=False)
@click.option('--worker', expose_value=False)
@click.option('--type', expose_value=False)
@click.option('--realm', expose_value=False)
@click.option('--loglevel', default=None,
              help="Change level for all loggers and handlers, "
              "possible values are WARNING, INFO or DEBUG")
@click.option('--title', expose_value=False)
def start(payments, monitor, datadir, node_address, rpc_address, peer,
          start_geth, version, m, geth_port, loglevel):
    freeze_support()
    delete_reactor()

    if version:
        from golem.core.variables import APP_VERSION
        print("GOLEM version: {}".format(APP_VERSION))
        return 0

    # Workarounds for pyinstaller executable
    sys.modules['win32com.gen_py.os'] = None
    sys.modules['win32com.gen_py.pywintypes'] = None
    sys.modules['win32com.gen_py.pythoncom'] = None

    config = dict(datadir=datadir, transaction_system=payments)

    if rpc_address:
        config['rpc_address'] = rpc_address.address
        config['rpc_port'] = rpc_address.port
    # Crossbar
    if m == 'crossbar.worker.process':
        start_crossbar_worker(m)
    # Golem headless
    else:
        from golem.core.common import config_logging
        config_logging(datadir=datadir, loglevel=loglevel)
        install_reactor()
        log_golem_version()

        node = OptNode(peers=peer, node_address=node_address,
                       use_monitor=monitor, start_geth=start_geth,
                       geth_port=geth_port, **config)
        node.run(use_rpc=True)


def delete_reactor():
    if 'twisted.internet.reactor' in sys.modules:
        del sys.modules['twisted.internet.reactor']


def install_reactor():
    from golem.core.common import is_windows
    if is_windows():
        from twisted.internet import iocpreactor
        iocpreactor.install()
    from twisted.internet import reactor
    return reactor


def start_crossbar_worker(module):
    idx = sys.argv.index('-m')
    sys.argv.pop(idx)
    sys.argv.pop(idx)

    if '-u' in sys.argv:
        # ignore; unbuffered mode causes issues on Windows
        sys.argv.remove('-u')

    import importlib
    module = importlib.import_module(module)
    module.run()


def log_golem_version():
    log = logging.getLogger('golem.version')
    # initial version info
    from golem.core.variables import APP_VERSION, PROTOCOL_CONST

    log.info("GOLEM Version: " + APP_VERSION)
    log.info("P2P Protocol Version: " + str(PROTOCOL_CONST.P2P_ID))
    log.info("Task Protocol Version: " + str(PROTOCOL_CONST.TASK_ID))


if __name__ == '__main__':
    start()
