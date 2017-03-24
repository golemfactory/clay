#!/usr/bin/env python

from multiprocessing import freeze_support

import click
import sys

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
def start(gui, payments, datadir, node_address, rpc_address, peer, task, qt, m):
    freeze_support()

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
        # Workaround for pyinstaller executable
        if 'twisted.internet.reactor' in sys.modules:
            del sys.modules['twisted.internet.reactor']

        address = '{}:{}'.format(rpc_address.address, rpc_address.port)
        start_gui(check_rpc_address(ctx=None, param=None,
                                    address=address))
    # Golem
    elif gui:
        from gui.startapp import start_app
        start_app(rendering=True, **config)
    # Golem headless
    else:
        from golem.core.common import config_logging

        config_logging(datadir=datadir)

        node = OptNode(node_address=node_address, **config)
        node.initialize()

        node.connect_with_peers(peer)
        node.add_tasks(task)
        node.run(use_rpc=True)


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
