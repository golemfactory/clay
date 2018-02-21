#!/usr/bin/env python

import os
import argparse
import sys


# Export pbr version for peewee_migrate user
os.environ["PBR_VERSION"] = '3.1.1'

from golem.core.common import config_logging, install_reactor  # noqa
from golem.interface.cli import CLI  # noqa
from golem.interface.client import debug  # noqa
from golem.interface.client.account import Account  # noqa
from golem.interface.client.environments import Environments  # noqa
from golem.interface.client.network import Network  # noqa
from golem.interface.client.payments import payments, incomes  # noqa
from golem.interface.client.resources import Resources  # noqa
from golem.interface.client.settings import Settings  # noqa
from golem.interface.client.tasks import Tasks, Subtasks  # noqa
from golem.interface.websockets import WebSocketCLI  # noqa


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
    install_reactor()
    ws_cli = WebSocketCLI(cli, host=parsed.address, port=parsed.port)
    ws_cli.execute(forwarded, interactive=interactive)


if __name__ == '__main__':
    start()
