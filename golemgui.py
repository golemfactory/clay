import click
from twisted.internet.defer import inlineCallbacks, setDebugging
from twisted.internet.error import ReactorAlreadyRunning

from apps.appsmanager import AppsManager
from golem.core.common import config_logging
from golem.network.transport.tcpnetwork import SocketAddress
from golem.node import OptNode
from golem.rpc.mapping.core import CORE_METHOD_MAP
from golem.rpc.session import object_method_map, Session, WebSocketAddress

GUI_LOG_NAME = "golem_gui.log"

setDebugging(True)

apps_manager = AppsManager()
apps_manager.load_apps()


def install_qt5_reactor():
    try:
        import qt5reactor
    except ImportError:
        # Maybe qt5reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt5reactor
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
    except Exception as e:
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
        self.app = Gui(self.logic, AppMainWindow)
        self.logic.register_gui(self.app.get_main_window(),
                                MainWindowCustomizer)

        if rendering:
            register_rendering_task_types(self.logic)

    @inlineCallbacks
    def start(self, client):
        yield self.logic.register_client(client)
        yield self.logic.start()
        self.app.execute(using_qt5_reactor=True)


@click.command()
@click.option('--rpc-address', '-r', multiple=False, callback=check_rpc_address,
              help="RPC server address to use: <ipv4_addr>:<port> or [<ipv6_addr>]:<port>")
def start_gui(rpc_address, rendering=True):

    from golem.rpc.mapping.gui import GUI_EVENT_MAP
    from golem.rpc.session import Client
    import logging

    config_logging(GUI_LOG_NAME)
    logger = logging.getLogger("app")

    gui_app = GUIApp(rendering)
    reactor = install_qt5_reactor()

    events = object_method_map(gui_app.logic, GUI_EVENT_MAP)
    session = Session(rpc_address, events=events)

    def connect():
        session.connect().addCallbacks(session_ready, shutdown)

    def session_ready(*_):
        core_client = Client(session, CORE_METHOD_MAP)
        reactor.callFromThread(gui_app.start, core_client)
        gui_app.start(core_client)

    def shutdown(err):
        logger.error(u"GUI process error: {}".format(err))

    reactor.callWhenRunning(connect)
    reactor.addSystemEventTrigger('before', 'shutdown', session.disconnect)

    try:
        reactor.run()
    except ReactorAlreadyRunning:
        logger.debug(u"GUI process: reactor is already running")


if __name__ == '__main__':
    start_gui()
