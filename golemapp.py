#!/usr/bin/env python
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

# Export pbr version for peewee_migrate user

os.environ["PBR_VERSION"] = '3.1.1'

# pylint: disable=wrong-import-position

import golem  # noqa
import golem.argsparser as argsparser  # noqa

from golem.appconfig import AppConfig  # noqa
from golem.clientconfigdescriptor import ClientConfigDescriptor, \
    ConfigApprover  # noqa
from golem.config.environments import set_environment  # noqa

from golem.core.common import install_reactor  # noqa
from golem.core.simpleenv import get_local_datadir  # noqa
from golem.core.variables import PROTOCOL_CONST  # noqa
from golem.node import Node  # noqa
from golem.tools.talkback import enable_sentry_logger  # noqa

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
@click.option('--monitor/--nomonitor', default=True)
@click.option('--concent/--noconcent', default=False)
@click.option('--datadir', '-d',
              default=get_local_datadir('default'),
              type=click.Path(
                  file_okay=False,
                  writable=True
              ))
@click.option('--protocol_id', type=click.STRING,
              callback=PROTOCOL_CONST.patch_protocol_id,
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
# Local geth is currently experimental, see issue #2476
# @click.option('--start-geth', is_flag=True, default=False, is_eager=True,
#               help="Start local geth node")
# @click.option('--start-geth-port', default=None, type=int,
#               callback=argsparser.enforce_start_geth_used, metavar="<port>",
#               help="Port number to be used by locally started geth node")
@click.option('--geth-address', default=None, metavar="http://<host>:<port>",
              callback=argsparser.parse_http_addr,
              help="Connect with given geth node")
@click.option('--password', default=None,
              help="Password to unlock Golem. This flag should be mostly used "
              "during development as it's not a safe way to provide password")
@click.option('--accept-terms', is_flag=True, default=False,
              help="Accept Golem terms of use. This is equivalent to calling "
                   "`golemcli terms accept`")
@click.option('--generate-rpc-cert', is_flag=True, default=False,
              help="Generate RPC certificate if they do not exist")
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
def start(monitor, concent, datadir, node_address, rpc_address, peer, mainnet,
          net, geth_address, password, accept_terms, generate_rpc_cert, version,
          log_level, enable_talkback, m):

    freeze_support()
    delete_reactor()
    set_environment('mainnet' if mainnet else net)

    # Import active configuration after the environment has been set
    from golem.config.active import ETHEREUM_CHAIN, IS_MAINNET

    if version:
        print("GOLEM version: {}".format(golem.__version__))
        return 0

    # We should use different directories for different chains
    datadir = os.path.join(datadir, ETHEREUM_CHAIN)

    if generate_rpc_cert:
        generate_rpc_certificate(datadir)
        return 0

    # Workarounds for pyinstaller executable
    sys.modules['win32com.gen_py.os'] = None
    sys.modules['win32com.gen_py.pywintypes'] = None
    sys.modules['win32com.gen_py.pythoncom'] = None

    app_config = AppConfig.load_config(datadir, mainnet=IS_MAINNET)
    config_desc = ClientConfigDescriptor()
    config_desc.init_from_app_config(app_config)
    config_desc = ConfigApprover(config_desc).approve()

    if rpc_address:
        config_desc.rpc_address = rpc_address.address
        config_desc.rpc_port = rpc_address.port
    if node_address:
        config_desc.node_address = node_address
    # Crossbar
    if m == 'crossbar.worker.process':
        start_crossbar_worker(m)
    # Golem headless
    else:
        install_reactor()

        from golem.core.common import config_logging
        config_logging(datadir=datadir, loglevel=log_level)

        if enable_talkback is None:
            enable_talkback = bool(config_desc.enable_talkback)
        enable_sentry_logger(enable_talkback)

        log_golem_version()
        log_platform_info()
        log_ethereum_chain()

        node = Node(
            datadir=datadir,
            app_config=app_config,
            config_desc=config_desc,
            peers=peer,
            use_monitor=monitor,
            use_concent=concent,
            mainnet=IS_MAINNET,
            start_geth=False,
            start_geth_port=None,
            geth_address=geth_address,
            password=password,
        )

        if accept_terms:
            node.accept_terms()

        node.start()


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
    from golem.config.active import ETHEREUM_CHAIN
    logger.info("Ethereum chain: %s", ETHEREUM_CHAIN)


def generate_rpc_certificate(datadir: str):
    from golem.rpc.cert import CertificateManager
    from golem.rpc.common import CROSSBAR_DIR

    cert_dir = os.path.join(datadir, CROSSBAR_DIR)
    os.makedirs(cert_dir, exist_ok=True)

    cert_manager = CertificateManager(cert_dir)
    cert_manager.generate_if_needed()

    print('RPC self-signed certificate has been created')


if __name__ == '__main__':
    start()
