#!/usr/bin/env python
import sys
import click
from multiprocessing import freeze_support
import logging
from ethereum import slogging
#Monkey patch for ethereum.slogging.
#SLogger aggressively mess up with python looger.
#This patch is to settle down this.
#It should be done before any SLogger is created.
orig_getLogger = slogging.SManager.getLogger
def monkey_patched_getLogger(*args, **kwargs):
    orig_class = logging.getLoggerClass()
    result = orig_getLogger(*args, **kwargs)
    logging.setLoggerClass(orig_class)
    return result
slogging.SManager.getLogger = monkey_patched_getLogger
from golem.node import OptNode


@click.command()
@click.option('--gui/--nogui', default=True)
@click.option('--payments/--nopayments', default=True)
@click.option('--datadir', '-d', type=click.Path())
@click.option('--node-address', '-a', multiple=False, type=click.STRING,
              callback=OptNode.parse_node_addr,
              help="Network address to use for this node")
@click.option('--rpc-address', '-r', multiple=False, callback=OptNode.parse_rpc_address,
              help="RPC server address to use: <ipv4_addr>:<port> or [<ipv6_addr>]:<port>")
@click.option('--peer', '-p', multiple=True, callback=OptNode.parse_peer,
              help="Connect with given peer: <ipv4_addr>:<port> or [<ipv6_addr>]:<port>")
@click.option('--task', '-t', multiple=True, type=click.Path(exists=True),
              callback=OptNode.parse_task_file,
              help="Request task from file")
@click.option('--qt', is_flag=True, default=False,
              help="Spawn Qt GUI only")
@click.option('--version', '-v', is_flag=True, default=False, help="Show Golem version information")
# Python flags, needed by crossbar (package only)
@click.option('-m', nargs=1, default=None)
@click.option('-u', is_flag=True, default=False, expose_value=False)
# Multiprocessing option (ignored)
@click.option('--multiprocessing-fork', nargs=1, expose_value=False)
# Crossbar arguments (package only)
@click.option('--cbdir', expose_value=False)
@click.option('--worker', expose_value=False)
@click.option('--type', expose_value=False)
@click.option('--realm', expose_value=False)
@click.option('--loglevel', expose_value=False)
@click.option('--title', expose_value=False)
def start(gui, payments, datadir, node_address, rpc_address, peer, task, qt, version, m):
    freeze_support()
    delete_reactor()
    set_fd_limit()

    if version:
        from golem.core.variables import APP_VERSION
        print ("GOLEM version: {}".format(APP_VERSION))
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
    # Qt GUI
    elif qt:
        from gui.startgui import start_gui, check_rpc_address
        address = '{}:{}'.format(rpc_address.address, rpc_address.port)
        start_gui(check_rpc_address(ctx=None, param=None,
                                    address=address))
    # Golem
    elif gui:
        from gui.startapp import start_app
        start_app(rendering=True, **config)
    # Golem headless
    else:
        install_reactor()

        from golem.core.common import config_logging
        config_logging(datadir=datadir)
        node = OptNode(node_address=node_address, **config)
        node.initialize()

        node.connect_with_peers(peer)
        node.add_tasks(task)
        node.run(use_rpc=True)


def set_fd_limit():
    from golem.core.common import is_windows
    from golem.core.variables import MIN_NOFILE

    if is_windows():
        return

    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)

    if soft is not None and soft < MIN_NOFILE:
        soft = MIN_NOFILE
    if hard is not None and hard < MIN_NOFILE:
        hard = MIN_NOFILE

    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
    except Exception as exc:
        print("Error setting open file descriptor limit: {}"
              .format(exc))


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


if __name__ == '__main__':
    start()
