import sys
sys.path.append( '../ui' )

from PyQt4.QtGui import QApplication, QDialog
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

        #FIXME: some shitty python magic
        def closeEvent_(self_, event):
            GLOBAL_SHUTDOWN[ 0 ] = True
            event.accept()

        setattr( self.window.__class__, 'closeEvent', closeEvent_ )

    def execute( self ):
        self.window.show()
        sys.exit(self.app.exec_())

    def UpdateNodeState( self, ns ):
        self.uic.UpdateRowsState( ns.getUID(), ns.getFormattedTimestamp(), ns.getRemoteProgress(), ns.getLocalProgress() )

if __name__ == "__main__":

    from threading import Thread
    import time
    import random
    from PyQt4 import QtCore

    class NodeSimulator(Thread):

        updateRequest = QtCore.pyqtSignal( int )

        ########################
        def __init__(self, id, uid, numLocalTasks, numRemoteTasks, localTaskDuration, remoteTaskDuration, innerUpdateDelay ):
            super(NodeSimulator, self).__init__()
            
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
            print "->local task duration: {} secs, remote task duration: {} secs".format( self.localTaskDuration, self.remoteTaskDuration )

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

                #print "\r                                                                      ",
                #print "\r{:3} : {}   {:3} : {}".format( locTask, self.locProgress, remTask, self.remProgress ),

            print "Finished node '{}'".format( self.uid )

    class LocalNetworkSimulator(Thread):

        ########################
        def __init__(self, numNodes, maxLocalTasks, maxRemoteTasks, maxLocalTaskDuration, maxRemoteTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay ):
            super(LocalNetworkSimulator, self).__init__()

            self.numNodes = numNodes
            self.maxLocTasks = maxLocalTasks
            self.maxRemTasks = maxRemoteTasks
            self.maxLocTaskDura = maxLocalTaskDuration
            self.maxRemTaskDura = maxRemoteTaskDuration
            self.maxInnerUpdateDelay = maxInnerUpdateDelay
            self.nodeSpawnDelay = nodeSpawnDelay

            self.nodes = []

        ########################
        def getRandomizedUp( self, value, scl = 1.4 ):
            return ( 0.1 +  scl * random.random() ) * value

        ########################
        def getRandomizedDown( self, value, scl = 0.7 ):
            return ( 1.0 - random.random() * scl ) * value

        ########################
        def createNewNode( self, id ):
            uid = "gen - uid - {}".format( id )
                node = NodeSimulator( curNode, "uid {}".format( curNode ), 1, 1, 1, 1, 0.2 )

        ########################
        def run( self ):
            curTime = time.time()

            curNode = 0

            while curNode < self.numNodes:

                if GLOBAL_SHUTDOWN[ 0 ]:
                    break
                
                self.nodes.append( node )
                node.start()

                time.sleep( self.getRandomizedUp( self.nodeSpawnDelay ) )

                curNode += 1

            print "Local network simulator finished running."
            print "Waiting for nodes to finish"
        
            for node in self.nodes:
                node.join()

    numNodes = 30
    maxLocalTasks = 15
    maxRemoteTasks = 300
    maxLocTaskDuration = 200.0
    maxRemTaskDuration = 25.0
    maxInnerUpdateDelay = 2.0
    nodeSpawnDelay = 2.0
    
    simulator = LocalNetworkSimulator( numNodes, maxLocalTasks, maxRemoteTasks, maxLocTaskDuration, maxRemTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay )
    simulator.start()

    manager = NodesManager()
    manager.execute()

    #ns0 = NodeStateSnapshot( "some uiid 0", 0.2, 0.7 )
    #ns1 = NodeStateSnapshot( "some uiid 1", 0.2, 0.7 )
    #ns2 = NodeStateSnapshot( "some uiid 2", 0.2, 0.7 )
    #ns3 = NodeStateSnapshot( "some uiid 3", 0.2, 0.7 )

    #manager.UpdateNodeState( ns0 )
    #manager.UpdateNodeState( ns1 )
    #manager.UpdateNodeState( ns2 )
    #manager.UpdateNodeState( ns3 )

