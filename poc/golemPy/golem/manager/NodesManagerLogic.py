
import subprocess
import time
import random
from golem.task.TaskBase import TaskHeader

class NodesManagerLogicTest:

    ########################
    def __init__( self, simulator ):
        self.simulator = simulator

    ########################
    def runAdditionalNodes( self, numNodes ):
        for i in range( numNodes ):
            self.simulator.addNewNode()

    ########################
    def terminateNode( self, uid ):
        self.simulator.terminateNode( uid )

    ########################
    def terminateAllNodes( self ):
        self.simulator.terminateAllNodes()

    ########################
    def enqueueNewTask( self, uid, w, h, numSamplesPerPixel, fileName ):
        self.simulator.enqueueNodeTask( uid, w, h, numSamplesPerPixel, fileName )

class EmptyManagerLogic:

    ########################
    def __init__( self, managerServer ):
        self.reactor = None
        self.managerServer = managerServer
        self.activeNodes = []

    ########################
    def setReactor( self, reactor ):
        self.reactor = reactor
        self.managerServer.setReactor( reactor )

    ########################
    def getReactor( self ):
        return self.reactor

    ########################
    def runAdditionalNodes( self, numNodes ):
        for i in range( numNodes ):
            time.sleep( 0.1 )
            pc = subprocess.Popen( ["python", "main.py"], creationflags = subprocess.CREATE_NEW_CONSOLE )
            self.activeNodes.append( pc )

    ########################
    def terminateNode( self, uid ):
        self.managerServer.sendTerminate( uid )

    ########################
    def terminateAllNodes( self ):
        for node in self.managerServer.managerSessions:
            try:
                self.managerServer.sendTerminate( node.uid )
            except:
                logger.warning("Can't send terminate signal to node {}".format( node.uid ))

    ########################
    def enqueueNewTask( self, uid, w, h, numSamplesPerPixel, fileName ):
        hash = random.getrandbits(128)
        th = TaskHeader( uid, "222222", "", 0 )    
        self.managerServer.sendNewTask( uid, PbrtRenderTask( th, "", 32, 16, 2, "test_chunk_", "resources/city-env.pbrt" ) )
        #self.managerServer.sendNewTask( uid, VRayTracingTask( w, h, numSamplesPerPixel, th, fileName ) )
