import click

from gnr.node import start, GNRNode, node_cli


def disable_blender(ctx, param, value):
    del ctx, param
    if not value:
        GNRNode.default_environments = []


# This command group is created only to create a `--blender` option somewhere.
@click.group()
@click.option('--blender/--no-blender', default=True, callback=disable_blender,
              help="Enable/disable Blender environment (enabled by default)")
def dummy_cli():
    pass


# Extract the `blender` option from `dummy_cli` and add it to the `node_cli`
# group defined in `gnr.node`.
# This is probably a lame way of adding an option to an existing command...
assert len(dummy_cli.params) == 1
blender_option = dummy_cli.params[0]
assert blender_option.name == 'blender'

start_command = node_cli.commands['start']
start_command.params.append(blender_option)

if __name__ == "__main__":
    start()
