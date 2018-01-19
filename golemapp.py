#!/usr/bin/env python
import sys
import logging
from multiprocessing import freeze_support
import click
from ethereum import slogging

import golem
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
              callback=OptNode.parse_node_addr, metavar="<host>",
              help="Network address to use for this node")
@click.option('--rpc-address', '-r', multiple=False,
              callback=OptNode.parse_rpc_address, metavar="<host>:<port>",
              help="RPC server address to use")
@click.option('--peer', '-p', multiple=True,
              callback=OptNode.parse_peer, metavar="<host>:<port>",
              help="Connect with given peer")
@click.option('--start-geth', is_flag=True, default=False, is_eager=True,
              help="Start local geth node")
@click.option('--start-geth-port', default=None, type=int,
              callback=OptNode.enforce_start_geth_used, metavar="<port>",
              help="Port number to be used by locally started geth node")
@click.option('--geth-address', default=None, metavar="http://<host>:<port>",
              callback=OptNode.parse_http_addr,
              help="Connect with given geth node")
@click.option('--version', '-v', is_flag=True, default=False,
              help="Show Golem version information")
# Python flags, needed by crossbar (package only)
@click.option('-m', nargs=1, default=None)
@click.option('--node', expose_value=False)
@click.option('--klass', expose_value=False)
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
          start_geth, start_geth_port, geth_address, version, m, loglevel):
    freeze_support()
    delete_reactor()

    if version:
        print("GOLEM version: {}".format(golem.__version__))
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
                       start_geth_port=start_geth_port,
                       geth_address=geth_address, **config)
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
    import golem_messages
    from golem.core.variables import PROTOCOL_CONST

    log.info("GOLEM Version: %s", golem.__version__)
    log.info("Protocol Version: %s", PROTOCOL_CONST.ID)
    log.info("golem_messages Version: %s", golem_messages.__version__)


if __name__ == '__main__':
    start()
