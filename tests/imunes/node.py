import click

from golemapp import start
from golem.node import OptNode


def disable_blender(ctx, param, value):
    del ctx, param
    if not value:
        OptNode.default_environments = []


def set_network_info(ctx, param, value):
    addr = OptNode.parse_node_addr(ctx, param, value)
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
@click.command()
@click.option('--blender/--no-blender', default=True, callback=disable_blender,
              help="Enable/disable Blender environment (enabled by default)")
@click.option('--public-address', '-A', multiple=False, type=click.STRING,
              callback=set_network_info,
              help="Public network address to use for this node")
@click.pass_context
def immunes_start(ctx):
    # FIXME: Pass other options/arguments to golemapp.start
    # This does not work.
    ctx.forward(start)


# Copy the extra options from `dummy_cli` to the `node_cli`
# group defined in `gui.node`.
# This is probably a lame way of adding options to an existing command...
# FIXME: See above
# start_command = node_cli.commands['start']
# for param in dummy_cli.params:
#     start_command.params.append(param)


if __name__ == "__main__":
    start()
