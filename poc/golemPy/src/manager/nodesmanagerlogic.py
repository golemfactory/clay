class NodesManagerLogicTest:

    ########################
    def __init__( self, simulator ):
        self.simulator = simulator

    ########################
    def runAdditionalNodes( self, numNodes ):
        for i in range( numNodes ):
            self.simulator.addNewNode()