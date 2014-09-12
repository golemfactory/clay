from golem.manager.NodesManagerLogic import EmptyManagerLogic
import time
import os
import subprocess

class GNRManagerLogic( EmptyManagerLogic ):

    def runAdditionalNodes(self, numNodes ):
        for i in range( numNodes ):
            time.sleep( 0.1 )
            os.chdir('../gnr/')
            pc = subprocess.Popen( ["python", "main.py"], creationflags = subprocess.CREATE_NEW_CONSOLE )
            os.chdir('../manager')
            self.activeNodes.append( pc )

    def enqueueNewTask( self, uid, w, h, numSamplesPerPixel, fileName ):
        pass

    def terminateAllLocalNodes( self, uid ):
        self.managerServer.sendTerminateAll( uid )

