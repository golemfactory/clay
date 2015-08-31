
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

from tools.UiGen import genUiFiles

genUiFiles("./../src")

from golem.AppConfig import AppConfig
from golem.manager.NodesManager import  NodesManager
from golem.manager.NodesManagerLogic import EmptyManagerLogic
from golem.network.transport.Message import init_messages

def main():

    init_messages()

    port = AppConfig.managerPort()
    manager = NodesManager(None)
    logic = EmptyManagerLogic(port, manager.managerServer)
    manager.setManagerLogic(logic)

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    logic.setReactor(reactor)
    manager.execute(True)

    reactor.run()
    sys.exit(0)

main()
