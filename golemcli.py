import argparse
import sys

from golem.core.common import config_logging
from golem.interface.cli import CLI
from golem.interface.client import account
from golem.interface.client.environments import Environments
from golem.interface.client.network import Network
from golem.interface.client.payments import payments, incomes
from golem.interface.client.resources import Resources
from golem.interface.client.settings import Settings
from golem.interface.client.tasks import Tasks, Subtasks
from golem.interface.websockets import WebSocketCLI

# prevent 'unused' warnings
_ = {
    Tasks, Subtasks, Network, Environments, Resources, Settings,
    account, incomes, payments,
}


def start():
    # process initial arguments
    arguments = dict(
        interactive=('-i', '--interactive'),
        address=('-a', '--address'),
        port=('-p', '--port'),
    )

    args = sys.argv[1:]

    parser = argparse.ArgumentParser()

    parser.add_argument(*arguments['interactive'], dest="interactive", action="store_true", default=False)
    parser.add_argument(*arguments['address'], dest="address", type=str, default='127.0.0.1')
    parser.add_argument(*arguments['port'], dest="port", type=int, default=60103)

    parsed, forwarded = parser.parse_known_args(args)

    # setup logging if in interactive mode
    interactive = parsed.interactive or not forwarded

    if interactive:
        config_logging("golem_cli.log")
    else:
        import logging
        logging.raiseExceptions = 0

    # run the cli
    cli = WebSocketCLI(CLI, address=parsed.address, port=parsed.port)
    cli.execute(forwarded, interactive=interactive)


if __name__ == '__main__':
    start()
