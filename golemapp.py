import os
from multiprocessing import freeze_support

import click
import sys

from golem.core.common import config_logging
from golem.node import OptNode

from gui.startapp import start_app


@click.command(context_settings=dict(
    ignore_unknown_options=True,
))
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
@click.option('--multiprocessing-fork', nargs=1, expose_value=False, default=None)
# Python flags, needed by crossbar (package only)
@click.option('-u', is_flag=True, default=False)
@click.option('-m', nargs=1, default=None)
# Skip Crossbar arguments (package only)
@click.argument('_', nargs=-1, type=click.UNPROCESSED)
def start(gui, payments, datadir, node_address, rpc_address, peer, task, u, m, _):

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
        import gc
        gc.garbage.append(sys.stdout)
        gc.garbage.append(sys.stderr)
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
        sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)
        sys.argv.remove('-u')

    import importlib
    module = importlib.import_module(module)
    module.run()


if __name__ == '__main__':
    start()
