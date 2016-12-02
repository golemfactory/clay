import logging
from multiprocessing import Process, Queue
from os import path

from gnr.application import GNRGui
from gnr.customizers.blenderrenderdialogcustomizer import BlenderRenderDialogCustomizer
from gnr.customizers.luxrenderdialogcustomizer import LuxRenderDialogCustomizer
from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment
from gnr.task.blenderrendertask import build_blender_renderer_info
from gnr.task.luxrendertask import build_lux_render_info
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.gen.ui_BlenderWidget import Ui_BlenderWidget
from gnr.ui.gen.ui_LuxWidget import Ui_LuxWidget
from gnr.ui.widget import TaskWidget
from golem.core.common import config_logging
from golem.core.processmonitor import ProcessMonitor
from golem.environments.environment import Environment
from twisted.internet.defer import inlineCallbacks

GUI_LOG_NAME = "golem_gui.log"
CLIENT_LOG_NAME = "golem_client.log"


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
    return [LuxRenderEnvironment(),
            BlenderEnvironment(),
            Environment()]


def register_rendering_task_types(logic):
    logic.register_new_renderer_type(build_blender_renderer_info(TaskWidget(Ui_BlenderWidget),
                                                                 BlenderRenderDialogCustomizer))
    logic.register_new_renderer_type(build_lux_render_info(TaskWidget(Ui_LuxWidget),
                                                           LuxRenderDialogCustomizer))


class GUIApp(object):

    def __init__(self, rendering):
        self.logic = RenderingApplicationLogic()
        self.app = GNRGui(self.logic, AppMainWindow)
        self.logic.register_gui(self.app.get_main_window(),
                                RenderingMainWindowCustomizer)
        self.client = None

        if rendering:
            register_rendering_task_types(self.logic)

    @inlineCallbacks
    def start(self, client, logic_service_info):
        try:
            self.client = client
            self.logic.client = client
            # yield self.logic.register_client(self.client, logic_service_info)
            yield self.logic.start()
            # yield self.logic.check_network_state()
            self.app.execute(True)
        except Exception as exc:
            import traceback
            traceback.print_exc()


def start_gui_process(queue, datadir, rendering=True, gui_app=None, reactor=None):

    if datadir:
        log_name = path.join(datadir, GUI_LOG_NAME)
    else:
        log_name = GUI_LOG_NAME

    config_logging(log_name)
    logger = logging.getLogger("gnr.app")

    rpc_address = queue.get(True, 3600)

    if not gui_app:
        gui_app = GUIApp(rendering)
    if not reactor:
        reactor = install_qt4_reactor()

    from golem.rpc.session import SessionConnector, Session, Client
    from golem.rpc.mapping.core import CORE_METHOD_MAP

    connector = SessionConnector(Session, rpc_address)

    def session_ready(*_):
        try:
            core_client = Client(connector.session, CORE_METHOD_MAP)
            gui_app.start(client=core_client, logic_service_info=None)
        except Exception:
            import traceback
            traceback.print_exc()

    def shutdown(err):
        logger.error("GUI process error: {}".format(err))

    def connect():
        connector.session.ready.addCallbacks(session_ready, shutdown)
        deferred = connector.connect()
        deferred.addErrback(shutdown)

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
        try:
            client = Client(datadir=datadir, transaction_system=transaction_system)
            client.start()
        except Exception as exc:
            logger.error("Client process error: {}".format(exc))
            queue.put(exc)
            return

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    from twisted.internet import reactor
    from golem.rpc.router import CrossbarRouter
    from golem.rpc.session import SessionConnector, Session, object_method_map
    from golem.rpc.mapping.core import CORE_METHOD_MAP

    router = CrossbarRouter(datadir=client.datadir)

    def router_ready(*_):
        connector = SessionConnector(Session, router.address)
        connector.session.methods = object_method_map(client, CORE_METHOD_MAP)
        connector.session.ready.addCallbacks(session_ready, shutdown)

        deferred = connector.connect()
        deferred.addErrback(shutdown)

    def session_ready(*_):
        queue.put(router.address)
        queue.close()

    def shutdown(err):
        queue.put(Exception("Error: {}".format(err)))

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
        print "Exception in Client process: {}".format(exc)

    process_monitor.exit()
