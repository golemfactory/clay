
import sys
sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/ui')
sys.path.append('../src/vm')
sys.path.append('../src/task')
sys.path.append('../src/network')
sys.path.append('../src/manager')
sys.path.append('../src/task/resource')
sys.path.append('../src/manager/server')
sys.path.append('../testtasks/minilight/src')
sys.path.append('../testtasks/pbrt')

from tools.uigen import gen_ui_files

gen_ui_files("./../src")

from golem.AppConfig import AppConfig
from golem.manager.NodesManager import  NodesManager
from golem.manager.NodesManagerLogic import EmptyManagerLogic
from golem.network.transport.message import init_messages

def main():

    init_messages()

    port = AppConfig.manager_port()
    manager = NodesManager(None)
    logic = EmptyManagerLogic(port, manager.manager_server)
    manager.set_manager_logic(logic)

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    logic.set_reactor(reactor)
    manager.execute(True)

    reactor.run()
    sys.exit(0)

main()
