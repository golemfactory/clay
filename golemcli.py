#!/usr/bin/env python

import os
import argparse
import logging
import sys

from multiprocessing import freeze_support
import click
import portalocker

from golem_sci.chains import MAINNET, RINKEBY
from golem.config.environments import set_environment  # noqa
from golem.core.simpleenv import get_local_datadir
from golem.rpc.cert import CertificateManager

from golem.rpc.common import CROSSBAR_HOST, CROSSBAR_PORT, CROSSBAR_DIR
from golem.core.common import config_logging, install_reactor

# Initialize magic CommandHelper (process decorators)
import golem.interface.client

from golem.interface.cli import CLI
from golem.interface.websockets import WebSocketCLI

logger = logging.getLogger('golemcli')


def start():
    freeze_support()
    delete_reactor()

    flags = dict(
        interactive=('-i', '--interactive'),
        mainnet=('-m', '--mainnet'),
        address=('-a', '--address'),
        port=('-p', '--port'),
        trust=('-t', '--verify-trust'),
        datadir=("-d", "--datadir")
    )

    flag_options = dict(
        interactive=dict(dest="interactive", action="store_true",
                         default=False, help="Enter interactive mode"),
        mainnet=dict(dest="mainnet", action="store_true", default=False,
                     help="Use mainnet chain"),
        address=dict(dest="address", type=str, default=CROSSBAR_HOST,
                     help="Golem node's RPC address"),
        port=dict(dest="port", type=int, default=CROSSBAR_PORT,
                  help="Golem node's RPC port"),
        datadir=dict(dest="datadir", default=None,
                     type=click.Path(
                         exists=True,
                         file_okay=False,
                         readable=True,
                     ),
                     help="Golem node's data dir"),
        trust=dict(dest="verify_trust", action="store_true", default=False,
                   help="Verify Golem node's certificate"),
    )

    # process initial arguments
    parser = argparse.ArgumentParser(add_help=False)
    for flag_name, flag in flags.items():
        parser.add_argument(*flag, **flag_options[flag_name])

    args = sys.argv[1:]
    parsed, forwarded = parser.parse_known_args(args)

    install_reactor()

    # platform trust settings
    if not parsed.verify_trust:
        disable_platform_trust()

    # setup logging if in interactive mode
    interactive = parsed.interactive

    if interactive:
        config_logging("_cli")
        cli = CLI()
    else:
        import logging
        logging.raiseExceptions = 0
        cli = CLI(main_parser=parser, main_parser_options=flag_options)

    check_golem_running(parsed.datadir, parsed.mainnet)

    if parsed.mainnet:
        set_environment('mainnet', None)

    datadir = get_local_datadir('default', root_dir=parsed.datadir)
    working_dir = os.path.join(datadir, CROSSBAR_DIR)

    # run the cli
    ws_cli = WebSocketCLI(
        cli,
        CertificateManager(working_dir),
        host=parsed.address,
        port=parsed.port
    )
    ws_cli.execute(forwarded, interactive=interactive)


def check_golem_running(datadir: str, cli_in_mainnet: bool):
    net_to_check = RINKEBY if cli_in_mainnet else MAINNET

    if is_app_running(datadir, net_to_check):
        cmd_hint = sys.argv + ['--mainnet']
        if cli_in_mainnet:
            cmd_hint = list(
                filter(lambda part: part not in ['--mainnet', '-m'], sys.argv)
            )

        msg = f"""
        ***************************************************************
        Detected Golem core running on {net_to_check} chain.
        In case of authorization failure, try running:
        {' '.join(cmd_hint)}
        ***************************************************************
        """

        logger.warning(msg)


def disable_platform_trust():
    from twisted.internet import _sslverify  # pylint: disable=protected-access
    _sslverify.platformTrust = lambda: None


def delete_reactor():
    if 'twisted.internet.reactor' in sys.modules:
        del sys.modules['twisted.internet.reactor']


def is_app_running(root_dir: str, net_name: str) -> bool:
    """ Checks if a lock file exists in the given data dir and whether
    that file is currently locked by another process.
    If both conditions are true we assume that an instance of Golem is running
    and using the specified data dir.
    """
    datadir = get_local_datadir(root_dir=root_dir, env_suffix=net_name)
    lock_path = os.path.join(datadir, 'LOCK')

    if os.path.isfile(lock_path):
        try:
            with portalocker.Lock(lock_path, timeout=1):
                return False
        except portalocker.LockException:
            return True

    return False


if __name__ == '__main__':
    start()
