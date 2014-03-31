from threading import Thread, Lock
import time
import random

from PyQt4 import QtCore

from nodestatesnapshot import NodeStateSnapshot


GLOBAL_SHUTDOWN = [ False ]

class NodeSimulator(QtCore.QThread):

    #updateRequest = QtCore.pyqtSignal()

    ########################
    def __init__(self, simulator, id, uid, numLocalTasks, numRemoteTasks, localTaskDuration, remoteTaskDuration, innerUpdateDelay ):
        super(NodeSimulator, self).__init__()
            
        self.simulator = simulator
        self.id = id
        self.uid = uid
        self.numLocalTasks = numLocalTasks
        self.numRemoteTasks = numRemoteTasks
        self.localTaskDuration = localTaskDuration
        self.remoteTaskDuration = remoteTaskDuration
        self.startTime = time.time()
        self.innerUpdateDelay = innerUpdateDelay
        
        self.locProgress = 0.0
        self.remProgress = 0.0

        self.localAddr = "127.0.0.1"
        self.localPort = int( random.random() * 60000.0 + 1024.0 )
        self.peersNum = 0
        self.tasksNum = 0

    ########################
    def getId( self ):
        return self.id

    ########################
    def getStateSnapshot( self ):
        addPeers = 1 if random.random() >= 0.45 else -1

        self.peersNum += addPeers

        if self.peersNum < 0:
            self.peersNum = 0
        if self.peersNum > 10:
            self.peersNum = 10

        addTasks = 1 if random.random() >= 0.5 else -1

        self.tasksNum += addTasks

        if self.tasksNum < 0:
            self.tasksNum = 0
        if self.tasksNum > 200:
            self.tasksNum = 200

        curTime = time.time()

        ctl = self.remoteTaskDuration - ( curTime - self.remTaskStartTime )
        ctl = max( 0.0, ctl )
        tcss = TaskChunkStateSnapshot( '0', 1600.0, ctl, self.remProgress )

        allChunks = 1000 * 1000

        totalTasks = int( 1000.0 * self.locProgress )
        totalChunks = 1000 * totalTasks
        
        activeRandom = random.random()
        activeTasks = int( activeRandom * totalTasks )
        activeChunks = int( activeRandom * totalChunks )

        ltss = LocalTaskStateSnapshot( totalTasks, totalChunks, activeTasks, activeChunks, allChunks - totalChunks, self.locProgress ) 

        return NodeStateSnapshot( self.uid, self.peersNum, self.tasksNum, self.localAddr, self.localPort, ['test message'], ['test message'], { '0' : tcss }, { '0xcdcdcd' : ltss } )

    ########################
    def run( self ):

        startTime = time.time()

        locTaskDuration = self.localTaskDuration
        remTaskDuration = self.remoteTaskDuration

        self.locTasksDuration = self.numLocalTasks * self.localTaskDuration
        self.remTasksDuration = self.numRemoteTasks * self.remoteTaskDuration

        totalDuration = max( locTasksDuration, remTasksDuration )

        locTask = 0
        self.locTaskStartTime = startTime
        remTask = 0
        self.remTaskStartTime = startTime

        print "Starting node '{}' local tasks: {} remote tasks: {}".format( self.uid, self.numLocalTasks, self.numRemoteTasks )
        print "->local task dura: {} secs, remote task dura: {} secs".format( self.localTaskDuration, self.remoteTaskDuration )

        while( time.time() - startTime < totalDuration ):
                
            if( GLOBAL_SHUTDOWN[ 0 ] ):
                print "Global shutdown triggered - bailing out"
                break

            time.sleep( self.innerUpdateDelay )

            curTime = time.time()

            if locTask < self.numLocalTasks:
                dt = curTime - self.locTaskStartTime

                if dt <= self.locTaskDuration:
                    self.locProgress = dt / self.locTaskDuration
                else:
                    self.locTaskStartTime = curTime
                    locTask += 1
                    self.locProgress = 0.0

            if remTask < self.numRemoteTasks:
                dt = curTime - self.remTaskStartTime

                if dt <= self.remTaskDuration:
                    self.remProgress = dt / self.remTaskDuration
                else:
                    self.remTaskStartTime = curTime
                    remTask += 1
                    self.remProgress = 0.0

            self.simulator.updateRequested( self.id )
            #self.updateRequest.emit()
            #self.emit(QtCore.SIGNAL("Activated()"),self.dupa, QtCore.Qt.QueuedConnection)
            #print "\r                                                                      ",
            #print "\r{:3} : {}   {:3} : {}".format( locTask, self.locProgress, remTask, self.remProgress ),

        print "Finished node '{}'".format( self.uid )

class LocalNetworkSimulator(Thread):

    ########################
    def __init__(self, manager, numNodes, maxLocalTasks, maxRemoteTasks, maxLocalTaskDuration, maxRemoteTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay ):
        super(LocalNetworkSimulator, self).__init__()

        self.manager = manager
        self.numNodes = numNodes
        self.maxLocTasks = maxLocalTasks
        self.maxRemTasks = maxRemoteTasks
        self.maxLocTaskDura = maxLocalTaskDuration
        self.maxRemTaskDura = maxRemoteTaskDuration
        self.maxInnerUpdateDelay = maxInnerUpdateDelay
        self.nodeSpawnDelay = nodeSpawnDelay
        self.curNode = 0
        self.lock = Lock()

        self.nodes = []

    ########################
    def addNewNode( self ):
        with self.lock:
            self.numNodes += 1
            node = self.createNewNode( self.curNode )
            self.nodes.append( node )
            node.start()
            self.curNode += 1
            #node.updateRequest.connect( self.updateRequested )

    ########################
    def updateRequested( self, id ):
        self.manager.appendStateUpdate( self.nodes[ id ].getStateSnapshot() )

    ########################
    def getRandomizedUp( self, value, scl = 1.4 ):
        return ( 0.1 +  scl * random.random() ) * value

    ########################
    def getRandomizedDown( self, value, scl = 0.7 ):
        return ( 1.0 - random.random() * scl ) * value

    ########################
    def createNewNode( self, id ):
        uid = "gen - uid - {}".format( id )
        numLocTasks = int( self.getRandomizedDown( self.maxLocTasks ) )
        numRemTasks = int( self.getRandomizedDown( self.maxRemTasks ) )
        locTaskDura = self.getRandomizedDown( self.maxLocTaskDura )
        remTaskDura = self.getRandomizedDown( self.maxRemTaskDura )
        updateDelay = self.getRandomizedDown( self.maxInnerUpdateDelay )

        return NodeSimulator( self, id, uid, numLocTasks, numRemTasks, locTaskDura, remTaskDura, updateDelay )

    ########################
    def run( self ):
        time.sleep( 1 ) #just out of decency

        curTime = time.time()

        print "Starting node simulator for {} nodes".format( self.numNodes )

        while not GLOBAL_SHUTDOWN[ 0 ]:

            if self.curNode < self.numNodes:
                self.addNewNode()

            time.sleep( self.getRandomizedUp( self.nodeSpawnDelay ) )

        print "Local network simulator finished running."
        print "Waiting for nodes to finish"

        #10 seconds should be just enough for each node to do its cleanup
        for node in self.nodes:
            node.wait()

        print "Simulation finished"
