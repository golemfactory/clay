import logging
import os
import subprocess
import sys

from twisted.internet.error import ReactorAlreadyRunning

from apps.appsmanager import AppsManager
from golem.client import Client
from golem.core.async import async_callback
from golem.core.common import config_logging, DEVNULL, is_windows, is_frozen
from golem.core.common import get_golem_path
from golem.core.deferred import install_unhandled_error_logger
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import Session, object_method_map

apps_manager = AppsManager()
apps_manager.load_apps()


def stop_reactor(*_):
    from twisted.internet import reactor
    if reactor.running:
        reactor.stop()


def load_environments():
    return apps_manager.get_env_list()


def register_task_types(logic):
    from gui.view.widget import TaskWidget
    for app in list(apps_manager.apps.values()):
        task_type = app.task_type_info(TaskWidget(app.widget), app.controller)
        logic.register_new_task_type(task_type)


def start_error(err):
    print("Startup error: {}".format(err))


def start_gui(address):
    if is_frozen():
        runner = [sys.executable]
    else:
        runner = [sys.executable,
                  os.path.join(get_golem_path(), sys.argv[0])]

    if is_windows():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags &= ~subprocess.STARTF_USESHOWWINDOW
    else:
        startupinfo = None

    return subprocess.Popen(
        runner + ['--qt', '-r', '{}:{}'.format(address.host, address.port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=DEVNULL,
        startupinfo=startupinfo
    )

def start_client(start_ranking, datadir=None, transaction_system=False,
                 use_monitor=True, client=None, reactor=None, geth_port=None,
                 **config_overrides):
    config_logging("client", datadir=datadir)
    logger = logging.getLogger("golem.client")
    install_unhandled_error_logger()
    import gevent
    if not reactor:
        from twisted.internet import asyncioreactor
        asyncioreactor.install(gevent.get_hub().loop.aio)
        from twisted.internet import reactor

    process_monitor = None

    from golem.core.processmonitor import ProcessMonitor
    from golem.docker.manager import DockerManager
    from golem.rpc.router import CrossbarRouter

    if not client:
        client = Client(datadir=datadir, transaction_system=transaction_system,
                        use_monitor=use_monitor, geth_port=geth_port,
                        **config_overrides)

    config = client.config_desc
    methods = object_method_map(client, CORE_METHOD_MAP)
    router = CrossbarRouter(
        host=config.rpc_address,
        port=config.rpc_port,
        datadir=client.datadir
    )
    session = Session(router.address, methods=methods)
    client.connect()

    def router_ready(*_):
        session.connect().addCallbacks(async_callback(session_ready),
                                       start_error)

    def session_ready(*_):
        global process_monitor
        client.configure_rpc(session)

        docker_manager = DockerManager.install(client.config_desc)
        docker_manager.check_environment()
        environments = load_environments()

        for env in environments:
            client.environments_manager.add_environment(env)
        client.environments_manager.load_config(client.datadir)

        logger.info('Router session ready. Starting client...')
        try:
            logger.debug('client.sync()')
            client.sync()
            logger.debug('client.start()')
            client.start()
            logger.debug('after client.start()')
        except SystemExit:
            reactor.callFromThread(stop_reactor)
        except Exception as exc:
            logger.exception("Client process error: {}"
                             .format(exc))

        logger.info('Starting GUI process...')
        gui_process = start_gui(router.address)
        process_monitor = ProcessMonitor(gui_process)
        process_monitor.add_callbacks(stop_reactor)
        logger.info('Starting process monitor...')
        process_monitor.start()

    reactor.addSystemEventTrigger("before", "shutdown", client.quit)
    reactor.addSystemEventTrigger("before", "shutdown", router.stop)
    router.start(reactor, router_ready, start_error)

    if start_ranking:
        client.ranking.run(reactor)

    try:
        reactor.run()
        gevent.get_hub().join()
    except ReactorAlreadyRunning:
        logger.debug("Client process: reactor is already running")

    if process_monitor:
        process_monitor.exit()


def start_app(start_ranking=False, datadir=None, transaction_system=False,
              rendering=False, use_monitor=True, geth_port=None,
              **config_overrides):
    start_client(start_ranking, datadir, transaction_system,
                 use_monitor=use_monitor, geth_port=geth_port,
                 **config_overrides)