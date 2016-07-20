from multiprocessing import freeze_support

import click

from gnr.gnrstartapp import start_app
from gnr.node import GNRNode  # TODO: This also configures the logging.
from golem.core.common import config_logging


@click.command()
@click.option('--gui/--nogui', default=True)
@click.option('--payments/--nopayments', default=False)
@click.option('--datadir', '-d', type=click.Path())
@click.option('--node-address', '-a', multiple=False, type=click.STRING,
              callback=GNRNode.parse_node_addr,
              help="Network address to use for this node")
@click.option('--peer', '-p', multiple=True, callback=GNRNode.parse_peer,
              help="Connect with given peer: <ipv4_addr>:<port> or [<ipv6_addr>]:<port>")
@click.option('--task', '-t', multiple=True, type=click.Path(exists=True),
              callback=GNRNode.parse_task_file,
              help="Request task from file")
@click.option('--multiprocessing-fork', nargs=1, default=None)
def start(gui, payments, datadir, node_address, peer, task, multiprocessing_fork):

    freeze_support()

    if gui:
        start_app(datadir=datadir, rendering=True,
                  transaction_system=payments)
    else:
        config_logging()

        node = GNRNode(datadir=datadir, node_address=node_address,
                       transaction_system=payments)
        node.initialize()

        node.connect_with_peers(peer)
        node.add_tasks(task)

        node.run()
