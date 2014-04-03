
import sys
sys.path.append( '../ui' )
sys.path.append( '../' )
sys.path.append( '../core' )
sys.path.append( '../network' )

from PyQt4.QtGui import QApplication, QDialog
from PyQt4.QtCore import QTimer
from threading import Lock

from ui_nodemanager import Ui_NodesManagerWidget
from uicustomizer import ManagerUiCustomizer, NodeDataState
from NodeStateSnapshot import NodeStateSnapshot
from networksimulator import GLOBAL_SHUTDOWN, LocalNetworkSimulator
from NodesManagerLogic import NodesManagerLogicTest
from NodesManagerServer import NodesManagerServer

#FIXME: potencjalnie mozna tez spiac ze soba managery i wtedy kontrolowac zdalnie wszystkie koncowki i sobie odpalac nody w miare potrzeb, ale to nie na najblizsza prezentacje zabawa
class NodesManager:

    ########################
    def __init__( self, managerLogic = None ):
        self.app = QApplication( sys.argv )
        self.window = QDialog()
        self.ui = Ui_NodesManagerWidget()
        self.ui.setupUi( self.window )
        self.uic = ManagerUiCustomizer(self.ui, self)
        self.timer = QTimer()
        self.timer.timeout.connect( self.polledUpdate )
        self.lock = Lock()
        self.statesBuffer = []
        self.managerLogic = managerLogic

        self.uic.enableDetailedView( False )

        self.managerServer = NodesManagerServer( self, 20301 )

        #FIXME: some shitty python magic
        def closeEvent_(self_, event):
            try:
                self.managerLogic.getReactor().stop()
                self.managerLogic.terminateAllNodes()
            except Exception as ex:
                pass
            finally:
                GLOBAL_SHUTDOWN[ 0 ] = True
                event.accept()

        setattr( self.window.__class__, 'closeEvent', closeEvent_ )

    ########################
    def setManagerLogic( self, managerLogic ):
        self.managerLogic = managerLogic

    ########################
    def curSelectedNode( self ):
        return None

    ########################
    def appendStateUpdate( self, update ):
        with self.lock:
            self.statesBuffer.append( update )

    ########################
    def polledUpdate( self ):
        with self.lock:
            for ns in self.statesBuffer:
                self.updateNodeState( ns )

            self.statesBuffer = []

    ########################
    def execute( self, usingqt4Reactor = False ):
        self.window.show()
        self.timer.start( 100 )
        if not usingqt4Reactor:
            sys.exit(self.app.exec_())

    ########################
    def updateNodeState( self, ns ):
        assert isinstance( ns, NodeStateSnapshot )

        tcss = ns.getTaskChunkStateSnapshot()

        ndslt = {}
        for sp in tcss.values():
            ndslt[ sp.getChunkId() ] = {    "chunkProgress" : sp.getProgress(),
                                            "cpuPower" : "{}".format( sp.getCpuPower() ),
                                            "timeLeft" : "{}".format( sp.getEstimatedTimeLeft() ),
                                            "cshd" : sp.getChunkShortDescr()
                                        }

        ndscs = {}

        ltss = ns.getLocalTaskStateSnapshot()
        for sp in ltss.values():
            ndscs[ sp.getTaskId() ] = {   "taskProgress" : sp.getProgress(),
                                            "allocTasks" : "{}".format( sp.getTotalTasks() ),
                                            "allocChunks" : "{}".format( sp.getTotalChunks() ),
                                            "activeTasks" : "{}".format( sp.getActiveTasks() ),
                                            "activeChunks" : "{}".format( sp.getActiveChunks() ),
                                            "chunksLeft" : "{}".format( sp.getChunksLeft() ),
                                            "ltshd" : sp.getTaskShortDescr()
                                       }

        ep = "{}:{}".format( ns.endpointAddr, ns.endpointPort )
        ts = ns.getFormattedTimestamp()
        pn = "{}".format( ns.getPeersNum() )
        tn = "{}".format( ns.getTasksNum() )
        lm = ""
        if len( ns.getLastNetworkMessages() ) > 0:
            lm = ns.getLastNetworkMessages()[-1][ 0 ] + str( ns.getLastNetworkMessages()[-1][ 4 ] )
            

        ir = ns.isRunning()

        nodeDataState = NodeDataState( ir, ns.uid, ts, ep, pn, tn, lm, ndscs, ndslt )

        self.uic.UpdateNodePresentationState( nodeDataState )

    ########################
    def runAdditionalNodes( self, numNodes ):
        self.managerLogic.runAdditionalNodes( numNodes )

    ########################
    def terminateNode( self, uid ):
        self.managerLogic.terminateNode( uid )

    ########################
    def terminateAllNodes( self ):
        self.managerLogic.terminateAllNodes()

    ########################
    def enqueueNewTask( self, uid, w, h, numSamplesPerPixel, fileName ):
        self.managerLogic.enqueueNewTask( uid, w, h, numSamplesPerPixel, fileName );

if __name__ == "__main__":

    manager = NodesManager()

    numNodes = 1
    maxLocalTasks = 2
    maxRemoteTasks = 30
    maxLocTaskDuration = 10.0
    maxRemTaskDuration = 28.0
    maxInnerUpdateDelay = 2.0
    nodeSpawnDelay = 1.0

    simulator = LocalNetworkSimulator( manager, numNodes, maxLocalTasks, maxRemoteTasks, maxLocTaskDuration, maxRemTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay )
    manager.setManagerLogic( NodesManagerLogicTest( simulator ) )
    simulator.start()

    manager.execute()
