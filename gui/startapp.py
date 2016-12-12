import logging
from multiprocessing import Process, Queue
from os import path

from twisted.internet.defer import inlineCallbacks

from golem.core.common import config_logging
from golem.core.processmonitor import ProcessMonitor

from apps.appsmanager import AppsManager
from apps.rendering.gui.controller.renderingmainwindowcustomizer import RenderingMainWindowCustomizer

from gui.renderingapplicationlogic import RenderingApplicationLogic
from gui.view.appmainwindow import AppMainWindow
from gui.view.widget import TaskWidget

from application import GNRGui

DEBUG_DEFERRED = True
GUI_LOG_NAME = "golem_gui.log"
CLIENT_LOG_NAME = "golem_client.log"

apps_manager = AppsManager()
apps_manager.load_apps()


if DEBUG_DEFERRED:
    from twisted.internet.defer import setDebugging
    setDebugging(True)


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
    for app in apps_manager.apps.values():
        logic.register_new_task_type(app.build_info(TaskWidget(app.widget), app.controller))


class GUIApp(object):

    def __init__(self, rendering):
        self.logic = RenderingApplicationLogic()
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


def start_gui_process(queue, datadir, rendering=True, reactor=None):

    if datadir:
        log_name = path.join(datadir, GUI_LOG_NAME)
    else:
        log_name = GUI_LOG_NAME

    config_logging(log_name)
    logger = logging.getLogger("app")

    rpc_address = queue.get(True, 240)

    if not reactor:
        reactor = install_qt4_reactor()

    gui_app = GUIApp(rendering)

    from golem.rpc.session import Session, Client, object_method_map
    from golem.rpc.mapping.core import CORE_METHOD_MAP
    from golem.rpc.mapping.gui import GUI_EVENT_MAP

    events = object_method_map(gui_app.logic, GUI_EVENT_MAP)
    session = Session(rpc_address, events=events)

    def session_ready(*_):
        core_client = Client(session, CORE_METHOD_MAP)
        gui_app.start(core_client)

    def shutdown(err):
        logger.error(u"GUI process error: {}".format(err))

    def connect():
        session.connect().addCallbacks(session_ready, shutdown)

    reactor.callWhenRunning(connect)
    if not reactor.running:
        reactor.run()


def start_client_process(queue, start_ranking, datadir=None,
                         transaction_system=False, client=None):

    from golem.client import Client

    if datadir:
        log_name = path.join(datadir, CLIENT_LOG_NAME)
    else:
        log_name = CLIENT_LOG_NAME

    config_logging(log_name)
    logger = logging.getLogger("golem.client")

    environments = load_environments()

    if not client:
        client = Client(datadir=datadir, transaction_system=transaction_system)

    from twisted.internet import reactor
    from golem.rpc.router import CrossbarRouter
    from golem.rpc.session import Session, object_method_map
    from golem.rpc.mapping.core import CORE_METHOD_MAP

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    router = CrossbarRouter(datadir=client.datadir)

    def router_ready(*_):
        methods = object_method_map(client, CORE_METHOD_MAP)
        session = Session(router.address, methods=methods)
        client.configure_rpc(session)

        deferred = session.connect()
        deferred.addCallbacks(session_ready, shutdown)

    def session_ready(*_):
        try:
            client.start()
        except Exception as exc:
            logger.error(u"Client process error: {}".format(exc))
            queue.put(exc)
            return

        queue.put(router.address)
        queue.close()

    def shutdown(err):
        queue.put(Exception(u"Error: {}".format(err)))

    router.start(reactor, router_ready, shutdown)

    if start_ranking:
        client.ranking.run(reactor)

    if not reactor.running:
        reactor.run()


def start_app(datadir=None, rendering=False,
              start_ranking=True, transaction_system=False):

    queue = Queue()

    gui_process = Process(target=start_gui_process,
                          args=(queue, datadir, rendering))
    gui_process.daemon = True
    gui_process.start()

    process_monitor = ProcessMonitor(gui_process)
    process_monitor.add_shutdown_callback(stop_reactor)
    process_monitor.start()

    try:
        start_client_process(queue, start_ranking, datadir, transaction_system)
    except Exception as exc:
        print(u"Exception in Client process: {}".format(exc))

    process_monitor.exit()
