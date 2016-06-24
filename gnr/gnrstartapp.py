import logging.config
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
from golem.client import start_client
from golem.core.common import get_golem_path
from golem.environments.environment import Environment
from golem.rpc.websockets import WebSocketRPCServerFactory, WebSocketRPCClientFactory


def config_logging():
    """Config logger"""
    config_file = path.normpath(path.join(get_golem_path(), "gnr", "logging.ini"))
    logging.config.fileConfig(config_file, disable_existing_loggers=False)


def install_qt4_reactor():
    print "install reactor"
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


def start_gui_process(queue, rendering):
    config_logging()
    reactor = install_qt4_reactor()

    service_info = queue.get(True, 3600)
    ws_address = service_info.ws_address
    ws_client = WebSocketRPCClientFactory(ws_address.host, ws_address.port)

    def on_success(*args, **kwargs):
        client = ws_client.build_client(service_info)

        logic = RenderingApplicationLogic()
        app = GNRGui(logic, AppMainWindow)
        gui = RenderingMainWindowCustomizer

        logic.register_gui(app.get_main_window(), gui)

        if rendering:
            logic.register_new_renderer_type(build_blender_renderer_info(TaskWidget(Ui_BlenderWidget),
                                                                         BlenderRenderDialogCustomizer))
            logic.register_new_renderer_type(build_lux_render_info(TaskWidget(Ui_LuxWidget),
                                                                   LuxRenderDialogCustomizer))

        logic_service_info = ws_client.add_service(logic)

        logic.register_client(client)
        logic.start()
        logic.check_network_state()

        #    client.set_interface_rpc(logic_service_info)

        app.execute(True)

    def on_error(*args, **kwargs):
        print "Error connecting", args, kwargs

    def start():
        ws_client.connect().addCallbacks(on_success, on_error)

    reactor.callWhenRunning(start)
    reactor.run()


def start_client_process(queue, datadir, transaction_system, start_ranking):

    from twisted.internet import reactor

    environments = load_environments()
    client = start_client(datadir, transaction_system)

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    def start():
        ws_server = WebSocketRPCServerFactory()
        ws_server.listen()

        service_info = ws_server.add_service(client)
        queue.put(service_info)

    if start_ranking:
        client.ranking.run(reactor)

    reactor.callWhenRunning(start)
    reactor.run()


def start_app(datadir=None, rendering=False,
              start_ranking=True, transaction_system=False):

    queue = Queue()

    client_process = Process(target=start_client_process, args=(queue, datadir, transaction_system, start_ranking))
    client_process.daemon = True
    client_process.start()

    gui_process = Process(target=start_gui_process, args=(queue, rendering))
    gui_process.daemon = True
    gui_process.start()

    client_process.join()
