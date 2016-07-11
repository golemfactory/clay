import logging.config
from os import path

from golem.client import Client
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

LOG_NAME = "golem.log"


def config_logging(logname=LOG_NAME):
    """Config logger"""
    config_file = path.normpath(path.join(get_golem_path(), "gnr", "logging.ini"))
    logging.config.fileConfig(config_file, defaults={'logname': logname}, disable_existing_loggers=False)


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
    logic.register_new_renderer_type(build_blender_renderer_info(TaskWidget(Ui_BlenderWidget),
                                                                 BlenderRenderDialogCustomizer))
    logic.register_new_renderer_type(build_lux_render_info(TaskWidget(Ui_LuxWidget),
                                                           LuxRenderDialogCustomizer))


def load_environments():
    return [LuxRenderEnvironment(),
            BlenderEnvironment(),
            Environment()]


def start_and_configure_client(logic, environments, datadir,
                               transaction_system=False):
    client = Client(datadir=datadir, transaction_system=transaction_system)
    for env in environments:
        client.environments_manager.add_environment(env)

    client.environments_manager.load_config(client.datadir)

    client.start()
    logic.register_client(client)
    logic.start()
    logic.check_network_state()

    return client


def run_ranking(client, reactor):
    client.ranking.run(reactor)


def start_app(logic, app, gui, datadir=None, rendering=False,
              start_ranking=True, transaction_system=False):
    if datadir:
        config_logging(path.join(datadir, LOG_NAME))
    else:
        config_logging()

    reactor = install_reactor()
    register_gui(logic, app, gui)
    if rendering:
        register_rendering_task_types(logic)
    environments = load_environments()

    client = start_and_configure_client(logic, environments, datadir,
                                        transaction_system)

    if start_ranking:
        run_ranking(client, reactor)

    app.execute(True)

    reactor.run()
