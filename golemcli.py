#!/usr/bin/env python

import argparse
import sys

from golem.core.common import config_logging
from golem.interface.cli import CLI
from golem.interface.client import debug
from golem.interface.client.account import Account
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
    Account, incomes, payments, debug
}


def start():
    flags = dict(
        interactive=('-i', '--interactive'),
        address=('-a', '--address'),
        port=('-p', '--port'),
    )

    flag_options = dict(
        interactive=dict(dest="interactive", action="store_true",
                         default=False, help="Enter interactive mode"),
        address=dict(dest="address", type=str, default='localhost',
                     help="Golem node's RPC address"),
        port=dict(dest="port", type=int, default=61000,
                  help="Golem node's RPC port"),
    )

    # process initial arguments
    parser = argparse.ArgumentParser(add_help=False)
    for flag_name, flag in flags.items():
        parser.add_argument(*flag, **flag_options[flag_name])

    args = sys.argv[1:]
    parsed, forwarded = parser.parse_known_args(args)

    # setup logging if in interactive mode
    interactive = parsed.interactive

    if interactive:
        config_logging("_cli")
        cli = CLI()
    else:
        import logging
        logging.raiseExceptions = 0
        cli = CLI(main_parser=parser, main_parser_options=flag_options)

    # run the cli
    ws_cli = WebSocketCLI(cli, host=parsed.address, port=parsed.port)
    ws_cli.execute(forwarded, interactive=interactive)


if __name__ == '__main__':
    start()
