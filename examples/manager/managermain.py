import sys
import os

sys.path.append(os.environ.get('GOLEM'))

from golem.tools.uigen import gen_ui_files

gen_ui_files("./../../golem/ui")

from golem.appconfig import AppConfig
from golem.manager.nodesmanager import NodesManager
from gnrmanagerlogic import GNRManagerLogic
from golem.network.transport.message import init_manager_messages
import logging.config


def main():
    logging.config.fileConfig('../gnr/logging.ini', disable_existing_loggers=False)
    init_manager_messages()

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    port = AppConfig.manager_port()
    manager = NodesManager(None, port)
    logic = GNRManagerLogic(manager.manager_server, "../gnr")
    manager.set_manager_logic(logic)

    logic.set_reactor(reactor)
    manager.execute(True)

    reactor.run()
    sys.exit(0)


main()
