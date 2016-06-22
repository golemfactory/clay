import logging.config
from multiprocessing import Process
from os import path

import time

from gnr.customizers.renderingmainwindowcustomizer import RenderingMainWindowCustomizer
from gnr.ui.appmainwindow import AppMainWindow

from gnr.application import GNRGui

from golem.client import start_client
from golem.core.common import get_golem_path
from golem.environments.environment import Environment

from gnr.customizers.blenderrenderdialogcustomizer import BlenderRenderDialogCustomizer
from gnr.customizers.luxrenderdialogcustomizer import LuxRenderDialogCustomizer
from gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment
from gnr.task.luxrendertask import build_lux_render_info
from gnr.task.blenderrendertask import build_blender_renderer_info
from gnr.ui.gen.ui_BlenderWidget import Ui_BlenderWidget
from gnr.ui.gen.ui_LuxWidget import Ui_LuxWidget
from gnr.ui.widget import TaskWidget
from golem.rpc.client import JsonRPCClient
from golem.rpc.server import JsonRPCServer


def config_logging():
    """Config logger"""
    config_file = path.normpath(path.join(get_golem_path(), "gnr", "logging.ini"))
    logging.config.fileConfig(config_file, disable_existing_loggers=False)


def install_reactor():
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


def start_gui_process(client, logic, rendering):

    app = GNRGui(logic, AppMainWindow)
    gui = RenderingMainWindowCustomizer

    logic.register_gui(app.get_main_window(), gui)

    if rendering:
        logic.register_new_renderer_type(build_blender_renderer_info(TaskWidget(Ui_BlenderWidget),
                                                                     BlenderRenderDialogCustomizer))
        logic.register_new_renderer_type(build_lux_render_info(TaskWidget(Ui_LuxWidget),
                                                               LuxRenderDialogCustomizer))

    logic.register_client(client)
    logic.start()
    logic.check_network_state()

    app.execute(True)


rpc_server = None


def start_app(logic, datadir=None, rendering=False,
              start_ranking=True, transaction_system=False):

    reactor = install_reactor()
    environments = load_environments()
    client = start_client(datadir, transaction_system)

    for env in environments:
        client.environments_manager.add_environment(env)
    client.environments_manager.load_config(client.datadir)

    if start_ranking:
        client.ranking.run(reactor)

    def start_gui():
        global rpc_server
        rpc_server = JsonRPCServer.listen(client)
        rpc_client = JsonRPCClient(client, rpc_server.url)

        gui_process = Process(target=start_gui_process, args=(rpc_client, logic, rendering))
        gui_process.start()

    reactor.callWhenRunning(start_gui)
    reactor.run()
