import os
import logging.config
from os import path

from golem.client import start_client
from golem.environments.environment import Environment
from golem.tools import uigen

uigen.gen_ui_files(path.join(path.dirname(__file__), "ui"))

from gnr.renderingenvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment, \
    LuxRenderEnvironment, BlenderEnvironment
from gnr.tasktype import build_pbrt_task_type, build_3ds_max_task_type, build_vray_task_type, \
    build_python_gnr_task_type, build_luxrender_task_type, build_blender_render_task_type
from gnr.task.pbrtgnrtask import build_pbrt_renderer_info
from gnr.task.threedsmaxtask import build_3ds_max_renderer_info
from gnr.task.vraytask import build_vray_renderer_info
from gnr.task.luxrendertask import build_lux_render_info
from gnr.task.blenderrendertask import build_blender_renderer_info

from gnr.ui.blenderrenderdialog import BlenderRenderDialog
from gnr.ui.luxrenderdialog import LuxRenderDialog
from gnr.ui.pbrtdialog import PbrtDialog
from gnr.ui.threedsmaxdialog import ThreeDSMaxDialog
from gnr.ui.vraydialog import VRayDialog

from gnr.customizers.blenderrenderdialogcustomizer import BlenderRenderDialogCustomizer
from gnr.customizers.luxrenderdialogcustomizer import LuxRenderDialogCustomizer
from gnr.customizers.pbrtdialogcustomizer import PbrtDialogCustomizer
from gnr.customizers.threedsmaxdialogcustomizer import ThreeDSMaxDialogCustomizer
from gnr.customizers.vraydialogcustomizer import VRayDialogCustomizer

from examples.manager.gnrmanagerlogic import run_additional_nodes, run_manager


def config_logging():
    """Config logger"""
    config_file = path.join(path.dirname(__file__), "logging.ini")
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


def register_gui(logic, app, gui):
    logic.register_gui(app.get_main_window(), gui)


def register_rendering_task_types(logic):
    logic.register_new_renderer_type(build_pbrt_renderer_info(PbrtDialog, PbrtDialogCustomizer))
    logic.register_new_renderer_type(build_3ds_max_renderer_info(ThreeDSMaxDialog, ThreeDSMaxDialogCustomizer))
    logic.register_new_renderer_type(build_vray_renderer_info(VRayDialog, VRayDialogCustomizer))
    logic.register_new_renderer_type(build_lux_render_info(LuxRenderDialog, LuxRenderDialogCustomizer))
    logic.register_new_renderer_type(build_blender_renderer_info(BlenderRenderDialog, BlenderRenderDialogCustomizer))


def register_task_types(logic):
    logic.register_new_task_type(build_pbrt_task_type())
    logic.register_new_task_type(build_3ds_max_task_type())
    logic.register_new_task_type(build_vray_task_type())
    logic.register_new_task_type(build_python_gnr_task_type())
    logic.register_new_task_type(build_luxrender_task_type())
    logic.register_new_task_type(build_blender_render_task_type())


def load_environments():
    return [PBRTEnvironment(),
            ThreeDSMaxEnvironment(),
            VRayEnvironment(),
            LuxRenderEnvironment(),
            BlenderEnvironment(),
            Environment()]


def start_and_configure_client(logic, environments):
    client = start_client()
    for env in environments:
        client.environments_manager.add_environment(env)

    client.environments_manager.load_config(client.config_desc.node_name)

    logic.register_client(client)
    logic.check_network_state()

    return client


def run_manager(logic, client):
    path = os.getcwd()

    def run_gnr_nodes(num_nodes):
        run_additional_nodes(path, num_nodes)

    nm_path = os.path.join(path, "..\\manager\\")

    def run_gnr_manager():
        run_manager(nm_path)

    logic.register_start_new_node_function(run_gnr_nodes)
    logic.register_start_nodes_manager_function(run_gnr_manager)

    client.environments_manager.load_config(client.config_desc.node_name)


def run_info_server(client, start_port=55555, next_port=55556, end_port=59999):
    from gnr.InfoServer import InfoServer
    info_server = InfoServer(client, start_port, next_port, end_port)
    info_server.start()


def run_manager_client(logic):
    logic.start_nodes_manager_client()


def run_ranking(client, reactor):
    client.ranking.run(reactor)


def run_add_task_client(logic):
    logic.start_add_task_client()


def run_add_task_server(client):
    client.run_add_task_server()
    #   from PluginServer import TaskAdderServer
    #   server =  TaskAdderServer(client.get_plugin_port())
    #   server.start()


def start_app(logic, app, gui, rendering=False, start_manager=False, start_manager_client=False,
              start_info_server=False, start_ranking=True, start_add_task_client=False, start_add_task_server=False):
    reactor = install_reactor()
    register_gui(logic, app, gui)
    if rendering:
        register_rendering_task_types(logic)
    else:
        register_task_types(logic)
    environments = load_environments()

    client = start_and_configure_client(logic, environments)

    if start_manager:
        run_manager(logic, client)
    if start_manager_client:
        run_manager_client(logic)
    if start_info_server:
        run_info_server(client)
    if start_ranking:
        run_ranking(client, reactor)
    if start_add_task_client:
        run_add_task_client(logic)
    if start_add_task_server:
        run_add_task_server(client)

    app.execute(False)

    reactor.run()
