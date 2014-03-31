from threading import Thread, Lock
import time
import random

from PyQt4 import QtCore

from nodestatesnapshot import NodeStateSnapshot, LocalTaskStateSnapshot, TaskChunkStateSnapshot


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

        self.forcedQuit = False

        self.localAddr = "127.0.0.1"
        self.localPort = int( random.random() * 60000.0 + 1024.0 )
        self.peersNum = 0
        self.tasksNum = 0
        self.running = True

    ########################
    def terminate( self ):
        self.forcedQuit = True

    ########################
    def getId( self ):
        return self.id

    ########################
    def getUid( self ):
        return self.uid

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
        tcss = TaskChunkStateSnapshot( '0xbaadf00d', 1600.0, ctl, self.remProgress, "chunk data: {}".format( self.remTask ) )

        allChunks = 1000 * 1000

        totalTasks = int( 1000.0 * self.locProgress )
        totalChunks = 1000 * totalTasks
        
        activeRandom = random.random()
        activeTasks = int( activeRandom * totalTasks )
        activeChunks = int( activeRandom * totalChunks )

        ltss = LocalTaskStateSnapshot( '0xcdcdcdcd', totalTasks, totalChunks, activeTasks, activeChunks, allChunks - totalChunks, self.locProgress, "task data: {}".format( self.locTask ) ) 

        return NodeStateSnapshot( self.running, self.uid, self.peersNum, self.tasksNum, self.localAddr, self.localPort, ['test message {}'.format( random.randint(0,200) )], ['test message {}'.format( random.randint(10, 70) )], { '0' : tcss }, { '0xcdcdcd' : ltss } )

    ########################
    def run( self ):

        startTime = time.time()
        self.locTasksDuration = self.numLocalTasks * self.localTaskDuration
        self.remTasksDuration = self.numRemoteTasks * self.remoteTaskDuration

        totalDuration = max( self.locTasksDuration, self.remTasksDuration )

        self.locTask = 0
        self.locTaskStartTime = startTime
        self.remTask = 0
        self.remTaskStartTime = startTime

        print "Starting node '{}' local tasks: {} remote tasks: {}".format( self.uid, self.numLocalTasks, self.numRemoteTasks )
        print "->local task dura: {} secs, remote task dura: {} secs".format( self.localTaskDuration, self.remoteTaskDuration )

        while( time.time() - startTime < totalDuration ):
                
            if GLOBAL_SHUTDOWN[ 0 ]:
                print "{}: Global shutdown triggered - bailing out".format( self.uid )
                break

            if self.forcedQuit:
                print "{}: Forced quit triggered - bailing out".format( self.uid )
                break

            time.sleep( self.innerUpdateDelay )

            curTime = time.time()

            if self.locTask < self.numLocalTasks:
                dt = curTime - self.locTaskStartTime

                if dt <= self.localTaskDuration:
                    self.locProgress = dt / self.localTaskDuration
                else:
                    self.locTaskStartTime = curTime
                    self.locTask += 1
                    self.locProgress = 0.0

            if self.remTask < self.numRemoteTasks:
                dt = curTime - self.remTaskStartTime

                if dt <= self.remoteTaskDuration:
                    self.remProgress = dt / self.remoteTaskDuration
                else:
                    self.remTaskStartTime = curTime
                    self.remTask += 1
                    self.remProgress = 0.0

            self.simulator.updateRequested( self.id )
            #self.updateRequest.emit()
            #self.emit(QtCore.SIGNAL("Activated()"),self.dupa, QtCore.Qt.QueuedConnection)
            #print "\r                                                                      ",
            #print "\r{:3} : {}   {:3} : {}".format( locTask, self.locProgress, remTask, self.remProgress ),

        print "Finished node '{}'".format( self.uid )
        
        if self.running:
            self.running = False
            self.simulator.updateRequested( self.id )

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
    def terminateAllNodes( self ):
        with self.lock:
            for node in self.nodes:
                node.terminate()

    ########################
    def terminateNode( self, uid ):
        with self.lock:
            for i, node in enumerate( self.nodes ):
                if node.getUid() == uid:
                    node.terminate()
                    #self.nodes.pop( i )
                    break

    ########################
    def addNewNode( self ):
        with self.lock:
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
