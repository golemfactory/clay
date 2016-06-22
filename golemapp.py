from multiprocessing import freeze_support

import click

from gnr.gnrstartapp import start_app
from gnr.node import GNRNode  # TODO: This also configures the logging.
from gnr.renderingapplicationlogic import RenderingApplicationLogic


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
def start(gui, payments, datadir, node_address, peer, task):
    freeze_support()

    if gui:
        logic = RenderingApplicationLogic()
        start_app(logic, datadir=datadir, rendering=True,
                  transaction_system=payments)
    else:
        node = GNRNode(datadir=datadir, node_address=node_address,
                       transaction_system=payments)
        node.initialize()

        node.connect_with_peers(peer)
        node.add_tasks(task)

        node.run()
