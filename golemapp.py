#!/usr/bin/env python
import binascii
import os
import platform
import sys
import logging
from multiprocessing import freeze_support

import click
import humanize
import psutil
from cpuinfo import get_cpu_info
from ethereum import slogging
from portalocker import Lock, LockException

# Export pbr version for peewee_migrate user

os.environ["PBR_VERSION"] = '3.1.1'

# pylint: disable=wrong-import-position

import golem  # noqa
import golem.argsparser as argsparser  # noqa
from golem.clientconfigdescriptor import ClientConfigDescriptor, \
    ConfigApprover  # noqa
from golem.config.environments import set_environment  # noqa
from golem.core import variables  # noqa
from golem.core.common import install_reactor  # noqa
from golem.core.simpleenv import get_local_datadir  # noqa
from golem.rpc import (  # noqa
    generate_rpc_certificate,
    WORKER_PROCESS_MODULE,
    WORKER_PROCESS_STANDALONE_ARGS,
)

logger = logging.getLogger('golemapp')  # using __name__ gives '__main__' here

# ethereum.slogging and logging compatibility patch
orig_getLogger = slogging.SManager.getLogger


def monkey_patched_getLogger(*args, **kwargs):
    orig_class = logging.getLoggerClass()
    result = orig_getLogger(*args, **kwargs)
    logging.setLoggerClass(orig_class)
    return result


slogging.SManager.getLogger = monkey_patched_getLogger


@click.command()
@click.option('--monitor/--nomonitor', default=None)
@click.option('--concent', type=click.Choice(variables.CONCENT_CHOICES))
@click.option('--datadir', '-d',
              default=None,
              type=click.Path(
                  file_okay=False,
                  writable=True
              ))
@click.option('--protocol_id', type=click.STRING,
              callback=variables.PROTOCOL_CONST.patch_protocol_id,
              is_eager=True,
              expose_value=False,
              help="Golem nodes will connect "
                   "only inside sub-network with "
                   "a given protocol id")
@click.option('--node-address', '-a', multiple=False, type=click.STRING,
              callback=argsparser.parse_node_addr, metavar="<host>",
              help="Network address to use for this node")
@click.option('--rpc-address', '-r', multiple=False,
              callback=argsparser.parse_rpc_address, metavar="<host>:<port>",
              help="RPC server address to use")
@click.option('--peer', '-p', multiple=True,
              callback=argsparser.parse_peer, metavar="<host>:<port>",
              help="Connect with given peer")
@click.option('--mainnet', is_flag=True, default=False,
              help='Whether to run on Ethereum mainnet (shorthand '
                   'for --net mainnet)')
@click.option('--net', default=None, type=click.Choice(['mainnet', 'testnet']),)
@click.option('--geth-address', default=None, metavar="http://<host>:<port>",
              callback=argsparser.parse_http_addr,
              help="Connect with given geth node")
@click.option('--password', default=None,
              help="Password to unlock Golem. This flag should be mostly used "
              "during development as it's not a safe way to provide password")
@click.option('--accept-terms', is_flag=True, default=False,
              help="Accept Golem terms of use. This is equivalent to calling "
                   "`golemcli terms accept`")
@click.option('--accept-concent-terms', is_flag=True, default=False,
              help="Accept Concent terms of use. This is equivalent to calling "
                   "`golemcli concent terms accept`")
@click.option('--accept-all-terms', is_flag=True, default=False,
              help="Accept all terms of use")
@click.option('--version', '-v', is_flag=True, default=False,
              help="Show Golem version information")
@click.option('--log-level', default=None,
              type=click.Choice([
                  'CRITICAL',
                  'ERROR',
                  'WARNING',
                  'INFO',
                  'DEBUG',
              ]),
              help="Change level for Golem loggers and handlers")
@click.option('--enable-talkback', is_flag=True, default=None)
@click.option('--hyperdrive-port', type=int, help="Hyperdrive public port")
@click.option('--hyperdrive-rpc-port', type=int, help="Hyperdrive RPC port")
def start(  # pylint: disable=too-many-arguments, too-many-locals
        monitor, concent, datadir, node_address, rpc_address, peer, mainnet,
        net, geth_address, password, accept_terms, accept_concent_terms,
        accept_all_terms, version, log_level, enable_talkback,
        hyperdrive_port, hyperdrive_rpc_port,
):
    if version:
        print("GOLEM version: {}".format(golem.__version__))
        return 0

    set_environment('mainnet' if mainnet else net, concent)

    # These are done locally since they rely on golem.config.active to be set
    from golem.config.active import EthereumConfig
    from golem.appconfig import AppConfig
    from golem.node import Node

    ethereum_config = EthereumConfig()

    # We should use different directories for different chains
    datadir = get_local_datadir('default', root_dir=datadir)
    os.makedirs(datadir, exist_ok=True)

    def _start():
        generate_rpc_certificate(datadir)

        # Workarounds for pyinstaller executable
        sys.modules['win32com.gen_py.os'] = None
        sys.modules['win32com.gen_py.pywintypes'] = None
        sys.modules['win32com.gen_py.pythoncom'] = None

        app_config = AppConfig.load_config(datadir)
        config_desc = ClientConfigDescriptor()
        config_desc.init_from_app_config(app_config)
        config_desc = ConfigApprover(config_desc).approve()

        if rpc_address:
            config_desc.rpc_address = rpc_address.address
            config_desc.rpc_port = rpc_address.port
        if node_address:
            config_desc.node_address = node_address
        if hyperdrive_port:
            config_desc.hyperdrive_port = hyperdrive_port
        if hyperdrive_rpc_port:
            config_desc.hyperdrive_rpc_port = hyperdrive_rpc_port

        # Golem headless
        install_reactor()

        from golem.core.common import config_logging
        config_logging(
            datadir=datadir,
            loglevel=log_level,
            config_desc=config_desc)

        log_golem_version()
        log_platform_info()
        log_ethereum_config(ethereum_config)
        log_concent_choice(ethereum_config.CONCENT_VARIANT)

        node = Node(
            datadir=datadir,
            app_config=app_config,
            config_desc=config_desc,
            peers=peer,
            use_monitor=monitor,
            use_talkback=enable_talkback,
            concent_variant=ethereum_config.CONCENT_VARIANT,
            geth_address=geth_address,
            password=password,
        )

        if accept_terms:
            node.accept_terms()

        if accept_concent_terms:
            node.accept_concent_terms()

        if accept_all_terms:
            node.accept_terms()
            node.accept_concent_terms()

        node.start()

    try:
        with Lock(os.path.join(datadir, 'LOCK'), timeout=1):
            _start()

    except LockException:
        logger.error(f'directory {datadir} is locked, possibly used by '
                     'another Golem instance')
        return 1
    return 0


@click.command(context_settings=dict(
    allow_extra_args=True,
    ignore_unknown_options=True,
))
def start_crossbar_worker():
    # Remove extra arguments used for spawning a frozen version of Crossbar
    for arg in WORKER_PROCESS_STANDALONE_ARGS:
        sys.argv.pop(sys.argv.index(arg))

    # Drop the "unbuffered mode" flag which causes issues on Windows
    if '-u' in sys.argv:
        sys.argv.remove('-u')

    # Run the worker process module
    import runpy
    runpy.run_module(WORKER_PROCESS_MODULE, run_name="__main__")


def main():
    freeze_support()

    # When the pyinstaller binary forks, the reactor might already be imported
    # by the parent process and copied to child's memory.
    if 'twisted.internet.reactor' in sys.modules:
        del sys.modules['twisted.internet.reactor']

    # Crossbar (standalone) is invoked with extra positional arguments
    if all(a in sys.argv for a in WORKER_PROCESS_STANDALONE_ARGS):
        start_crossbar_worker()
    else:
        start()  # pylint: disable=no-value-for-parameter


def log_golem_version():
    # initial version info
    import golem_messages
    from golem.core.variables import PROTOCOL_CONST

    logger.info("GOLEM Version: %s", golem.__version__)
    logger.info("Protocol Version: %s", PROTOCOL_CONST.ID)
    logger.info("golem_messages Version: %s", golem_messages.__version__)


def log_platform_info():
    # platform
    logger.info("system: %s, release: %s, version: %s, machine: %s",
                platform.system(), platform.release(), platform.version(),
                platform.machine())

    # cpu
    cpuinfo = get_cpu_info()
    logger.info("cpu: %s %s, %s cores",
                cpuinfo['vendor_id'], cpuinfo['brand'], cpuinfo['count'])

    # ram
    meminfo = psutil.virtual_memory()
    swapinfo = psutil.swap_memory()
    logger.info("memory: %s, swap: %s",
                humanize.naturalsize(meminfo.total, binary=True),
                humanize.naturalsize(swapinfo.total, binary=True))


def log_ethereum_config(ethereum_config):
    logger.info("Ethereum chain: %s", ethereum_config.CHAIN)
    logger.debug("Ethereum config: %s", [
        (attr, getattr(ethereum_config, attr))
        for attr in dir(ethereum_config) if not attr.startswith('__')
    ])


def log_concent_choice(value: dict):
    if None in value.values():
        logger.info('Concent disabled')
        return
    logger.info('Concent url: %s', value['url'])
    logger.info(
        'Concent public key: %s',
        binascii.hexlify(value['pubkey']).decode('ascii'),
    )


if __name__ == '__main__':
    main()
