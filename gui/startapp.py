import logging
import subprocess
from os import path

import sys
from twisted.internet import reactor
from twisted.internet.defer import setDebugging
from twisted.internet.error import ReactorAlreadyRunning

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.core.common import config_logging
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map

DEBUG_DEFERRED = True
CLIENT_LOG_NAME = "golem_client.log"

setDebugging(DEBUG_DEFERRED)


def stop_reactor():
    if reactor.running:
        reactor.stop()


def load_environments():
    apps_manager = AppsManager()
    apps_manager.load_apps()
    return apps_manager.get_env_list()


gui_process = None


def start_gui(address):
    global gui_process

    args = ['-r', '{}:{}'.format(address.host, address.port)]

    if hasattr(sys, 'frozen') and sys.frozen:
        gui_process = subprocess.Popen(['golemgui'] + args)
    else:
        gui_process = subprocess.Popen(['python', 'golemgui.py'] + args)


def start_client(gui, start_ranking, datadir=None,
                 transaction_system=False, client=None,
                 **config_overrides):

    if datadir:
        log_name = path.join(datadir, CLIENT_LOG_NAME)
    else:
        log_name = CLIENT_LOG_NAME

    config_logging(log_name)
    logger = logging.getLogger("golem.client")
    environments = load_environments()

    if not client:
        client = Client(datadir=datadir, transaction_system=transaction_system, **config_overrides)

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    config = client.config_desc
    methods = object_method_map(client, CORE_METHOD_MAP)

    host, port = config.rpc_address, config.rpc_port
    router = CrossbarRouter(host=host, port=port, datadir=client.datadir)
    session = Session(router.address, methods=methods)

    def router_ready(*_):
        session.connect().addCallbacks(session_ready, shutdown)

    def session_ready(*_):
        if gui:
            start_gui(router.address)
        try:
            client.configure_rpc(session)
            client.start()
        except Exception as exc:
            logger.exception(u"Client process error")

    def shutdown(err):
        print(u"Error: {}".format(err))

    router.start(reactor, router_ready, shutdown)

    if start_ranking:
        client.ranking.run(reactor)

    try:
        reactor.run()
    except ReactorAlreadyRunning:
        logger.debug(u"Client process: reactor is already running")


def start_app(gui=True, start_ranking=True, datadir=None,
              transaction_system=False, rendering=False, **config_overrides):

    start_client(gui, start_ranking, datadir,
                 transaction_system, **config_overrides)
