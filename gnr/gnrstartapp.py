import logging.config
import sys
from multiprocessing import Process
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


def start_gui_process(ws_rpc_client_info, rendering):
    config_logging()
    install_qt4_reactor()

    # client = client_builder.build()
    logic = RenderingApplicationLogic()
    app = GNRGui(logic, AppMainWindow)
    gui = RenderingMainWindowCustomizer

    logic.register_gui(app.get_main_window(), gui)

    if rendering:
        logic.register_new_renderer_type(build_blender_renderer_info(TaskWidget(Ui_BlenderWidget),
                                                                     BlenderRenderDialogCustomizer))
        logic.register_new_renderer_type(build_lux_render_info(TaskWidget(Ui_LuxWidget),
                                                               LuxRenderDialogCustomizer))

    # ws_address = ws_rpc_client_info.ws_address
    # ws_rpc = WebSocketRPCSession.create(ws_address)
    # ws_rpc.register_service(logic)
    # ws_rpc_logic_info = ws_rpc.client_info

#    client = ws_rpc.client(ws_rpc_client_info)

    client = None

    logic.register_client(client)
    logic.start()
    logic.check_network_state()

#    client.set_interface_rpc(ws_rpc_logic_info)

    app.execute(True)


def start_app(datadir=None, rendering=False,
              start_ranking=True, transaction_system=False):

    from twisted.internet import reactor

    environments = load_environments()
    client = start_client(datadir, transaction_system)

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    if start_ranking:
        client.ranking.run(reactor)

    def start_gui():

#        ws_listen_info = WebSocketServer.listen(port=45000)
#        ws_address = ws_listen_info.ws_address

        def on_rpc_server_started(*args, **kwargs):
#            ws_rpc.register_service(client)
#            ws_rpc_client_info = ws_rpc.client_info
            # rpc_server = JsonRPCServer.listen(client)
            # rpc_client_builder = JsonRPCClientBuilder(client, rpc_server.url)
#            gui_process = Process(target=start_gui_process, args=(ws_rpc_client_info, rendering))
#            gui_process.daemon = True
#            gui_process.start()
            pass

        def on_rpc_server_failure(*args, **kwargs):
            print "Cannot start the RPC server {} {}".format(args, kwargs)
            sys.exit(1)

#        ws_rpc, deferred = WebSocketRPCSession.create(ws_address)
#        deferred.addCallbacks(on_rpc_server_started, on_rpc_server_failure)

    reactor.callWhenRunning(start_gui)
    reactor.run()
