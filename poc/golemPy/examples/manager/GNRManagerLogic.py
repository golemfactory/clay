from golem.manager.NodesManagerLogic import EmptyManagerLogic
import time
import os
import subprocess

def runAdditionalNodes( path,  numNodes ):
    for i in range( numNodes ):
        time.sleep( 0.1 )
        prevPath = os.getcwd()
        os.chdir( path )
        pc = subprocess.Popen( ["python", "main.py"], creationflags = subprocess.CREATE_NEW_CONSOLE )
        os.chdir( prevPath )

class GNRManagerLogic( EmptyManagerLogic ):

    def __init__(self, managerServer, nodePath ):
        EmptyManagerLogic.__init__( self, managerServer )
        self.nodePath = nodePath

    def runAdditionalNodes(self, numNodes ):
        runAdditionalNodes( "../gnr", numNodes )

    ########################
    def enqueueNewTask( self, uid, w, h, numSamplesPerPixel, fileName ):
        pass

    ########################
    def terminateAllLocalNodes( self, uid ):
        self.managerServer.sendTerminateAll( uid )

    ########################
    def runAdditionalLocalNodes( self, uid, numNodes ):
        self.managerServer.sendNewNodes( uid, numNodes )

