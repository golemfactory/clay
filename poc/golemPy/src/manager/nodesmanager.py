import sys
sys.path.append( '../ui' )

from PyQt4.QtGui import QApplication, QDialog
from PyQt4.QtCore import QTimer
from threading import Lock

from ui_nodemanager import Ui_NodesManagerWidget
from uicustomizer import ManagerUiCustomizer
from nodestatesnapshot import NodeStateSnapshot

GLOBAL_SHUTDOWN = [ False ]


class NodesManager:

    def __init__( self ):
        self.app = QApplication( sys.argv )
        self.window = QDialog()
        self.ui = Ui_NodesManagerWidget()
        self.ui.setupUi( self.window )
        self.uic = ManagerUiCustomizer(self.ui)
        self.timer = QTimer()
        self.timer.timeout.connect( self.polledUpdate )
        self.lock = Lock()
        self.statesBuffer = []
        
        #FIXME: some shitty python magic
        def closeEvent_(self_, event):
            GLOBAL_SHUTDOWN[ 0 ] = True
            event.accept()

        setattr( self.window.__class__, 'closeEvent', closeEvent_ )

    def appendStateUpdate( self, update ):
        with self.lock:
            self.statesBuffer.append( update )

    def polledUpdate( self ):
        with self.lock:
            for ns in self.statesBuffer:
                self.updateNodeState( ns )

            self.statesBuffer = []

    def execute( self ):
        self.window.show()
        self.timer.start( 100 )
        sys.exit(self.app.exec_())

    def updateNodeState( self, ns ):
        self.uic.UpdateRowsState( ns.getUID(), ns.getFormattedTimestamp(), ns.getRemoteProgress(), ns.getLocalProgress() )

if __name__ == "__main__":

    from threading import Thread
    import time
    import random
    from PyQt4 import QtCore

    class NodeSimulator(QtCore.QThread):

        updateRequest = QtCore.pyqtSignal()

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

        ########################
        def getId( self ):
            return self.id

        ########################
        def getStateSnapshot( self ):
            return NodeStateSnapshot( self.uid, self.locProgress, self.remProgress )

        ########################
        def run( self ):

            startTime = time.time()

            locTaskDuration = self.localTaskDuration
            remTaskDuration = self.remoteTaskDuration

            locTasksDuration = self.numLocalTasks * self.localTaskDuration
            remTasksDuration = self.numRemoteTasks * self.remoteTaskDuration

            totalDuration = max( locTasksDuration, remTasksDuration )

            locTask = 0
            locTaskStartTime = startTime
            remTask = 0
            remTaskStartTime = startTime

            print "Starting node '{}' local tasks: {} remote tasks: {}".format( self.uid, self.numLocalTasks, self.numRemoteTasks )
            print "->local task dura: {} secs, remote task dura: {} secs".format( self.localTaskDuration, self.remoteTaskDuration )

            while( time.time() - startTime < totalDuration ):
                
                if( GLOBAL_SHUTDOWN[ 0 ] ):
                    print "Global shutdown triggered - bailing out"
                    break

                time.sleep( self.innerUpdateDelay )

                curTime = time.time()

                if locTask < self.numLocalTasks:
                    dt = curTime - locTaskStartTime

                    if dt <= locTaskDuration:
                        self.locProgress = dt / locTaskDuration
                    else:
                        locTaskStartTime = curTime
                        locTask += 1
                        self.locProgress = 0.0

                if remTask < self.numRemoteTasks:
                    dt = curTime - remTaskStartTime

                    if dt <= remTaskDuration:
                        self.remProgress = dt / remTaskDuration
                    else:
                        remTaskStartTime = curTime
                        remTask += 1
                        self.remProgress = 0.0

                simulator.updateRequested( self.id )
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

            self.nodes = []

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

            curNode = 0

            print "Starting node simulator for {} nodes".format( self.numNodes )

            while curNode < self.numNodes:

                if GLOBAL_SHUTDOWN[ 0 ]:
                    break
                
                node = self.createNewNode( curNode )
                node.updateRequest.connect( self.updateRequested )
                self.nodes.append( node )
                node.start()

                time.sleep( self.getRandomizedUp( self.nodeSpawnDelay ) )

                curNode += 1

            print "Local network simulator finished running."
            print "Waiting for nodes to finish"
        
            #10 seconds should be just enough for each node to do its cleanup
            for node in self.nodes:
                node.wait( 10000 )

    manager = NodesManager()

    numNodes = 30
    maxLocalTasks = 15
    maxRemoteTasks = 300
    maxLocTaskDuration = 200.0
    maxRemTaskDuration = 25.0
    maxInnerUpdateDelay = 2.0
    nodeSpawnDelay = 2.0
    
    simulator = LocalNetworkSimulator( manager, numNodes, maxLocalTasks, maxRemoteTasks, maxLocTaskDuration, maxRemTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay )
    simulator.start()

    manager.execute()

    #ns0 = NodeStateSnapshot( "some uiid 0", 0.2, 0.7 )
    #ns1 = NodeStateSnapshot( "some uiid 1", 0.2, 0.7 )
    #ns2 = NodeStateSnapshot( "some uiid 2", 0.2, 0.7 )
    #ns3 = NodeStateSnapshot( "some uiid 3", 0.2, 0.7 )

    #manager.updateNodeState( ns0 )
    #manager.updateNodeState( ns1 )
    #manager.updateNodeState( ns2 )
    #manager.updateNodeState( ns3 )

