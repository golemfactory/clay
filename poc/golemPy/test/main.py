
import sys
sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/ui')
sys.path.append('../src/vm')
sys.path.append('../src/task')
sys.path.append('../src/network')
sys.path.append('../src/manager')
sys.path.append('../testtasks/minilight/src')

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor

from threading import Thread
from appconfig import AppConfig
from clientconfigdescriptor import ClientConfigDescriptor
from nodesmanager import  NodesManager
from nodesmanagerlogic import EmptyManagerLogic



def main():

    #initMessages()
    port = AppConfig.managerPort()

    manager = NodesManager( EmptyManagerLogic( port ) )
    manager.execute()

main()
