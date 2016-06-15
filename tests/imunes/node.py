import click

from golemapp import start
from gnr.node import GNRNode, node_cli, parse_node_addr


def disable_blender(ctx, param, value):
    del ctx, param
    if not value:
        GNRNode.default_environments = []


def set_network_info(ctx, param, value):
    addr = parse_node_addr(ctx, param, value)
    if addr:
        import golem.network.p2p.node
        # Patch the Node.collect_network_info() method to set the provided
        # address as the node's public address.

        def override_network_info(self, *args, **kwargs):
            self.pub_addr = addr
            self.prv_addr = addr

        golem.network.p2p.node.Node.collect_network_info = override_network_info


# This command group is created only to create extra options for running in
# imunes simulation.
@click.group()
@click.option('--blender/--no-blender', default=True, callback=disable_blender,
              help="Enable/disable Blender environment (enabled by default)")
@click.option('--public-address', '-A', multiple=False, type=click.STRING,
              callback=set_network_info,
              help="Public network address to use for this node")
def dummy_cli():
    pass


# Copy the extra options from `dummy_cli` to the `node_cli`
# group defined in `gnr.node`.
# This is probably a lame way of adding options to an existing command...
start_command = node_cli.commands['start']
for param in dummy_cli.params:
    start_command.params.append(param)


if __name__ == "__main__":
    start()
