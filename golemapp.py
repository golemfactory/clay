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

logger = logging.getLogger('golemapp')  # using __name__ gives '__main__' here

# Monkey patch for ethereum.slogging.
# SLogger aggressively mess up with python looger.
# This patch is to settle down this.
# It should be done before any SLogger is created.
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
# Python flags, needed by crossbar (package only)
@click.option('-m', nargs=1, default=None)
@click.option('--node', expose_value=False)
@click.option('--klass', expose_value=False)
@click.option('-u', is_flag=True, default=False, expose_value=False)
# Multiprocessing option (ignored)
@click.option('--multiprocessing-fork', nargs=1, expose_value=False)
# Crossbar arguments (package only)
@click.option('--cbdir', expose_value=False)
@click.option('--worker', expose_value=False)
@click.option('--type', expose_value=False)
@click.option('--realm', expose_value=False)
@click.option('--loglevel', expose_value=False)  # Crossbar specific level
@click.option('--title', expose_value=False)
def start(  # pylint: disable=too-many-arguments, too-many-locals
        monitor, concent, datadir, node_address, rpc_address, peer, mainnet,
        net, geth_address, password, accept_terms, accept_concent_terms,
        accept_all_terms, version, log_level, enable_talkback, m):

    freeze_support()
    delete_reactor()

    # Crossbar
    if m == 'crossbar.worker.process':
        start_crossbar_worker(m)
        return 0

    if version:
        print("GOLEM version: {}".format(golem.__version__))
        return 0

    set_environment('mainnet' if mainnet else net, concent)
    # These are done locally since they rely on golem.config.active to be set
    from golem.config.active import CONCENT_VARIANT
    from golem.appconfig import AppConfig
    from golem.node import Node

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

        # Golem headless
        install_reactor()

        from golem.core.common import config_logging
        config_logging(
            datadir=datadir,
            loglevel=log_level,
            config_desc=config_desc)

        log_golem_version()
        log_platform_info()
        log_ethereum_chain()
        log_concent_choice(CONCENT_VARIANT)

        node = Node(
            datadir=datadir,
            app_config=app_config,
            config_desc=config_desc,
            peers=peer,
            use_monitor=monitor,
            use_talkback=enable_talkback,
            concent_variant=CONCENT_VARIANT,
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


def delete_reactor():
    if 'twisted.internet.reactor' in sys.modules:
        del sys.modules['twisted.internet.reactor']


def start_crossbar_worker(module):
    idx = sys.argv.index('-m')
    sys.argv.pop(idx)
    sys.argv.pop(idx)

    if '-u' in sys.argv:
        # ignore; unbuffered mode causes issues on Windows
        sys.argv.remove('-u')

    import importlib
    module = importlib.import_module(module)
    module.run()


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


def log_ethereum_chain():
    from golem.config.active import EthereumConfig
    logger.info("Ethereum chain: %s", EthereumConfig.CHAIN)


def log_concent_choice(value: dict):
    if None in value.values():
        logger.info('Concent disabled')
        return
    logger.info('Concent url: %s', value['url'])
    logger.info(
        'Concent public key: %s',
        binascii.hexlify(value['pubkey']).decode('ascii'),
    )


def generate_rpc_certificate(datadir: str):
    from golem.rpc.cert import CertificateManager
    from golem.rpc.common import CROSSBAR_DIR

    cert_dir = os.path.join(datadir, CROSSBAR_DIR)
    os.makedirs(cert_dir, exist_ok=True)

    cert_manager = CertificateManager(cert_dir)
    cert_manager.generate_if_needed()


if __name__ == '__main__':
    start()  # pylint: disable=no-value-for-parameter
