import sys
import os

from golem.appconfig import AppConfig
from golem.core.common import get_golem_path
from golem.manager.nodesmanager import NodesManager
from gnrmanagerlogic import GNRManagerLogic
from golem.network.transport.message import init_manager_messages
import logging.config


def main():
    config_path = os.path.normpath(os.path.join(get_golem_path(), "gnr/logging.ini"))
    print config_path
    logging.config.fileConfig(config_path, disable_existing_loggers=False)
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
    manager_logic_path = os.path.normpath(os.path.join(get_golem_path(), "gnr"))
    print manager_logic_path
    logic = GNRManagerLogic(manager.manager_server, manager_logic_path)
    manager.set_manager_logic(logic)

    logic.set_reactor(reactor)
    manager.execute(True)

    reactor.run()
    sys.exit(0)


main()
