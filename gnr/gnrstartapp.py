import logging.config
from multiprocessing import Process, Queue
from os import path

from twisted.internet.defer import inlineCallbacks

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
from golem.client import start_client
from golem.core.common import get_golem_path
from golem.environments.environment import Environment
from golem.rpc.websockets import WebSocketRPCServerFactory, WebSocketRPCClientFactory


def config_logging():
    """Config logger"""
    config_file = path.normpath(path.join(get_golem_path(), "gnr", "logging.ini"))
    logging.config.fileConfig(config_file, disable_existing_loggers=False)


def install_qt4_reactor():
    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    return reactor


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
        self.client = client
        yield self.logic.register_client(self.client, logic_service_info)
        yield self.logic.start()
        yield self.logic.check_network_state()
        self.app.execute(True)


def start_gui_process(queue, rendering):
    config_logging()

    client_service_info = queue.get(True, 3600)
    queue.close()

    gui_app = GUIApp(rendering)
    reactor = install_qt4_reactor()

    ws_address = client_service_info.rpc_address
    ws_client = WebSocketRPCClientFactory(ws_address.host, ws_address.port)

    def on_connected(_):
        client = ws_client.build_client(client_service_info)
        logic_service_info = ws_client.add_service(gui_app.logic)
        gui_app.start(client, logic_service_info)

    def on_error(*args, **kwargs):
        print "Error connecting to client", args, kwargs

    def connect():
        ws_client.connect().addCallbacks(on_connected, on_error)

    reactor.callWhenRunning(connect)
    reactor.run()


def start_client_process(queue, datadir, transaction_system, start_ranking):
    config_logging()

    environments = load_environments()

    try:
        client = start_client(datadir, transaction_system)
    except Exception as exc:
        print "Exiting client process: {}".format(exc)
        queue.close()
        return

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    def listen():
        ws_server = WebSocketRPCServerFactory()
        ws_server.listen()

        client_service_info = client.set_rpc_server(ws_server)

        queue.put(client_service_info)
        queue.close()

    from twisted.internet import reactor

    if start_ranking:
        client.ranking.run(reactor)

    reactor.callWhenRunning(listen)
    reactor.run()


def start_app(datadir=None, rendering=False,
              start_ranking=True, transaction_system=False):

    queue = Queue()

    client_process = Process(target=start_client_process, args=(queue, datadir, transaction_system, start_ranking))
    client_process.daemon = True
    client_process.start()

    # gui_process = Process(target=start_gui_process, args=(queue, rendering))
    # gui_process.daemon = True
    # gui_process.start()

    # start_client_process(queue, datadir, transaction_system, start_ranking)
    start_gui_process(queue, rendering)

    # gui_process.join()
    # client_process.join()
