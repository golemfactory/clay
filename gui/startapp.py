from multiprocessing import Process, Queue
from os import path
from twisted.internet.defer import inlineCallbacks, setDebugging
from twisted.internet.error import ReactorAlreadyRunning

from apps.appsmanager import AppsManager
from golem.core.common import config_logging
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import Session, object_method_map

DEBUG_DEFERRED = True
GUI_LOG_NAME = "golem_gui.log"
CLIENT_LOG_NAME = "golem_client.log"

setDebugging(DEBUG_DEFERRED)
apps_manager = AppsManager()
apps_manager.load_apps()


def install_qt4_reactor():
    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    return reactor


def stop_reactor():
    from twisted.internet import reactor
    if reactor.running:
        reactor.stop()


def load_environments():
    return apps_manager.get_env_list()


def register_rendering_task_types(logic):
    from gui.view.widget import TaskWidget
    for app in apps_manager.apps.values():
        task_type = app.build_info(TaskWidget(app.widget), app.controller)
        logic.register_new_task_type(task_type)


class GUIApp(object):

    def __init__(self, rendering):
        from application import GNRGui
        from apps.rendering.gui.controller.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
        from gui.applicationlogic import GNRApplicationLogic
        from gui.view.appmainwindow import AppMainWindow

        self.logic = GNRApplicationLogic()
        self.app = GNRGui(self.logic, AppMainWindow)
        self.logic.register_gui(self.app.get_main_window(),
                                RenderingMainWindowCustomizer)

        if rendering:
            register_rendering_task_types(self.logic)

    @inlineCallbacks
    def start(self, client):
        yield self.logic.register_client(client)
        yield self.logic.start()
        self.app.execute(using_qt4_reactor=True)


def start_gui_process(queue, datadir, rendering=True, gui_app=None, reactor=None):

    from golem.rpc.mapping.gui import GUI_EVENT_MAP
    from golem.rpc.session import Client
    import logging

    if datadir:
        log_name = path.join(datadir, GUI_LOG_NAME)
    else:
        log_name = GUI_LOG_NAME

    config_logging(log_name)
    logger = logging.getLogger("app")
    rpc_address = queue.get(True, 240)

    if not gui_app:
        gui_app = GUIApp(rendering)
    if not reactor:
        reactor = install_qt4_reactor()

    events = object_method_map(gui_app.logic, GUI_EVENT_MAP)
    session = Session(rpc_address, events=events)

    def connect():
        session.connect().addCallbacks(session_ready, shutdown)

    def session_ready(*_):
        core_client = Client(session, CORE_METHOD_MAP)
        gui_app.start(core_client)

    def shutdown(err):
        logger.error(u"GUI process error: {}".format(err))

    reactor.callWhenRunning(connect)
    reactor.addSystemEventTrigger('before', 'shutdown', session.disconnect)

    try:
        reactor.run()
    except ReactorAlreadyRunning:
        logger.debug(u"GUI process: reactor is already running")


def start_client_process(queue, start_ranking, datadir=None,
                         transaction_system=False, client=None,
                         **config_overrides):

    from golem.client import Client
    from golem.rpc.router import CrossbarRouter
    from twisted.internet import reactor
    import logging

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
        try:
            client.configure_rpc(session)
            client.start()
        except Exception as exc:
            logger.error(u"Client process error: {}".format(exc))
            queue.put(exc)
        else:
            queue.put(router.address)

    def shutdown(err):
        queue.put(Exception(u"Error: {}".format(err)))

    router.start(reactor, router_ready, shutdown)

    if start_ranking:
        client.ranking.run(reactor)

    try:
        reactor.run()
    except ReactorAlreadyRunning:
        logger.debug(u"Client process: reactor is already running")


def start_app(start_ranking=True, datadir=None,
              transaction_system=False, rendering=False, **config_overrides):

    queue = Queue()

    gui_process = Process(target=start_gui_process,
                          args=(queue, datadir, rendering))
    gui_process.daemon = True
    gui_process.start()

    from golem.core.processmonitor import ProcessMonitor

    process_monitor = ProcessMonitor(gui_process)
    process_monitor.add_shutdown_callback(stop_reactor)
    process_monitor.start()

    try:
        start_client_process(queue, start_ranking, datadir,
                             transaction_system, **config_overrides)
    except Exception as exc:
        print(u"Exception in Client process: {}".format(exc))

    process_monitor.exit()
