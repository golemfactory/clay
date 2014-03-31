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


import subprocess

class EmptyManagerLogic:

    ########################
    def __init__( self, port ):
        self.port = port
        self.reactor = None

    ########################
    def setReactor( self, reactor ):
        self.reactor = reactor

    ########################
    def getReactor( self ):
        return self.reactor

    ########################
    def runAdditionalNodes( self, numNodes ):
        for i in range( numNodes ):
            self.pc = subprocess.Popen( ["python", "clientmain.py"], creationflags = subprocess.CREATE_NEW_CONSOLE )

    ########################
    def terminateNode( self, uid ):
        pass

    ########################
    def terminateAllNodes( self ):
        pass

    ########################
    def enqueueNewTask( self, uid, w, h, numSamplesPerPixel, fileName ):
        pass
