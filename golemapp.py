from multiprocessing import freeze_support

import click
import sys

from golem.core.common import config_logging
from golem.node import OptNode

from gui.startapp import start_app


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
@click.option('--multiprocessing-fork', nargs=1, default=None)
# Python flags, needed by crossbar (package only)
@click.option('-u', is_flag=True, default=False)
@click.option('-m', nargs=1, default=None)
# Crossbar arguments (package only)
@click.option('--cbdir', expose_value=False)
@click.option('--worker', expose_value=False)
@click.option('--type', expose_value=False)
@click.option('--realm', expose_value=False)
@click.option('--loglevel', expose_value=False)
@click.option('--title', expose_value=False)
def start(gui, payments, datadir, node_address, rpc_address, peer, task, multiprocessing_fork, u, m):
    freeze_support()

    config = dict(datadir=datadir, transaction_system=payments)
    if rpc_address:
        config['rpc_address'] = rpc_address.address
        config['rpc_port'] = rpc_address.port

    # Crossbar
    if m == 'crossbar.worker.process':
        start_crossbar_worker(u, m)
    # GUI or headless mode
    elif gui:
        start_app(rendering=True, **config)
    else:
        config_logging()

        node = OptNode(node_address=node_address, **config)
        node.initialize()

        node.connect_with_peers(peer)
        node.add_tasks(task)
        node.run(use_rpc=True)


def start_crossbar_worker(unbuffered, module):
    idx = sys.argv.index('-m')
    sys.argv.pop(idx + 1)
    sys.argv.pop(idx)

    if unbuffered:
        # ignore; unbuffered mode causes issues on Windows
        sys.argv.remove('-u')

    import importlib
    module = importlib.import_module(module)
    module.run()


if __name__ == '__main__':
    start()
