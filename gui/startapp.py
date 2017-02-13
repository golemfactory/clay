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
from golem.core.processmonitor import ProcessMonitor
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.router import CrossbarRouter
from golem.rpc.session import Session, object_method_map

CLIENT_LOG_NAME = "golem_client.log"

setDebugging(True)
apps_manager = AppsManager()
apps_manager.load_apps()


def stop_reactor():
    if reactor.running:
        reactor.stop()


def load_environments():
    return apps_manager.get_env_list()


def register_task_types(logic):
    from gui.view.widget import TaskWidget
    for app in apps_manager.apps.values():
        task_type = app.task_type_info(TaskWidget(app.widget), app.controller)
        logic.register_new_task_type(task_type)


def start_error(err):
    print(u"Startup error: {}".format(err))


def start_gui(address):
    args = ['-r', '{}:{}'.format(address.host, address.port)]

    if hasattr(sys, 'frozen') and sys.frozen:
        return subprocess.Popen(['golemgui'] + args)
    else:
        return subprocess.Popen(['python', 'golemgui.py'] + args)


def start_client(start_ranking, datadir=None,
                 transaction_system=False, client=None,
                 **config_overrides):

    if datadir:
        log_name = path.join(datadir, CLIENT_LOG_NAME)
    else:
        log_name = CLIENT_LOG_NAME

    config_logging(log_name)
    logger = logging.getLogger("golem.client")
    environments = load_environments()
    process_monitor = None

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
        session.connect().addCallbacks(session_ready, start_error)

    def session_ready(*_):
        global process_monitor
        gui_process = start_gui(router.address)

        process_monitor = ProcessMonitor(gui_process)
        process_monitor.add_shutdown_callback(stop_reactor)
        process_monitor.start()

        try:
            client.configure_rpc(session)
            client.start()
        except Exception as exc:
            logger.exception(u"Client process error: {}"
                             .format(exc))

    router.start(reactor, router_ready, start_error)

    if start_ranking:
        client.ranking.run(reactor)

    try:
        reactor.run()
    except ReactorAlreadyRunning:
        logger.debug(u"Client process: reactor is already running")

    if process_monitor:
        process_monitor.exit()


def start_app(start_ranking=True, datadir=None,
              transaction_system=False, rendering=False, **config_overrides):

    start_client(start_ranking, datadir,
                 transaction_system, **config_overrides)
