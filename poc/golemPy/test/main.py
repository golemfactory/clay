
import sys
sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/ui')
sys.path.append('../src/vm')
sys.path.append('../src/task')
sys.path.append('../src/network')
sys.path.append('../src/manager')
sys.path.append('../testtasks/minilight/src')

import subprocess

from twisted.internet import reactor
from threading import Thread
from appconfig import AppConfig
from clientconfigdescriptor import ClientConfigDescriptor
from nodesmanager import  NodesManager
from nodesmanagerlogic import EmptyManagerLogic

class ReactorThread(Thread):

    def __init__( self ):
        super(ReactorThread, self).__init__()

    def run():
        reactor.run()

def main():

    #initMessages()

    managerPort = AppConfig.managerPort()

    reactorThread = ReactorThread()

    manager = NodesManager( EmptyManagerLogic() )
    manager.execute()

    reactorThread.run()

main()
