import logging

import click
from apps.appsmanager import AppsManager
from golem.core.common import config_logging
from golem.core.deferred import install_unhandled_error_logger
from golem.network.transport.tcpnetwork import SocketAddress
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import object_method_map, Session, WebSocketAddress
from ipaddress import AddressValueError
from twisted.internet.defer import inlineCallbacks

config_logging("_gui")
logger = logging.getLogger("app")
install_unhandled_error_logger()

apps_manager = AppsManager()
apps_manager.load_apps()


def install_qt5_reactor():
    import qt5reactor
    qt5reactor.install()
    from twisted.internet import reactor
    return reactor


def register_rendering_task_types(logic):
    from gui.view.widget import TaskWidget
    for app in apps_manager.apps.values():
        task_type = app.task_type_info(TaskWidget(app.widget), app.controller)
        logic.register_new_task_type(task_type)


def check_rpc_address(ctx, param, address):
    split = address.rsplit(':', 1)
    host, port = split[0], int(split[1])

    try:
        SocketAddress(host, port)
    except AddressValueError as e:
        return click.BadParameter(
            "Invalid network address specified: {}".format(e.message))
    return WebSocketAddress(host, port, u'golem')


class GUIApp(object):

    def __init__(self, rendering):

        from gui.application import Gui
        from gui.applicationlogic import GuiApplicationLogic
        from gui.controller.mainwindowcustomizer import MainWindowCustomizer
        from gui.view.appmainwindow import AppMainWindow

        self.logic = GuiApplicationLogic()
        self.gui = Gui(self.logic, AppMainWindow)
        self.logic.register_gui(self.gui.get_main_window(),
                                MainWindowCustomizer)

        if rendering:
            register_rendering_task_types(self.logic)

    @inlineCallbacks
    def start(self, client):
        yield self.logic.register_client(client)
        yield self.logic.start()
        self.gui.execute()


def start_error(err):
    logger.error("GUI process error: {}".format(err))


def start_gui(rpc_address, gui_app=None):

    from golem.rpc.mapping.gui import GUI_EVENT_MAP
    from golem.rpc.session import Client

    gui_app = gui_app or GUIApp(rendering=True)
    events = object_method_map(gui_app.logic, GUI_EVENT_MAP)
    session = Session(rpc_address, events=events)

    reactor = install_qt5_reactor()

    def connect():
        session.connect().addCallbacks(session_ready, start_error)

    def session_ready(*_):
        core_client = Client(session, CORE_METHOD_MAP)
        reactor.callFromThread(gui_app.start, core_client)

    reactor.callWhenRunning(connect)
    reactor.addSystemEventTrigger('before', 'shutdown', session.disconnect)

    try:
        reactor.run()
    finally:
        if gui_app and gui_app.gui and gui_app.gui.app:
            gui_app.gui.app.deleteLater()
