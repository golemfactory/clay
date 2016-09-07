import sys

from golem.core.common import config_logging
from golem.interface.cli import CLI
from golem.interface.client.management import management_exit
from golem.interface.client.tasks import Tasks  # noqa
from golem.interface.websockets import WebSocketsCLI


def main():
    interactive = True
    if interactive:
        config_logging("golem_cli.log")

    imports = {management_exit, Tasks}

    cli = WebSocketsCLI(CLI, address='127.0.0.1', port=60103)
    cli.execute(sys.argv[1:], interactive=interactive)

if __name__ == '__main__':
    main()
