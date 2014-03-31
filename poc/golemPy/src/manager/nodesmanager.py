import sys
sys.path.append( '../ui' )

from PyQt4.QtGui import QApplication, QDialog
from PyQt4.QtCore import QTimer
from threading import Lock

from ui_nodemanager import Ui_NodesManagerWidget
from uicustomizer import ManagerUiCustomizer, NodeDataState
from nodestatesnapshot import NodeStateSnapshot
from networksimulator import GLOBAL_SHUTDOWN, LocalNetworkSimulator
from nodesmanagerlogic import NodesManagerLogicTest

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

        #FIXME: some shitty python magic
        def closeEvent_(self_, event):
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
    def execute( self ):
        self.window.show()
        self.timer.start( 100 )
        sys.exit(self.app.exec_())

    ########################
    def updateNodeState( self, ns ):
        assert isinstance( ns, NodeStateSnapshot )

        chunkId = None
        chunkProgress = 0.0
        cpuPower = ""
        timeLeft = ""

        tcss = ns.getTaskChunkStateSnapshot()
        if len( tcss ) > 0:
            sp = tcss.itervalues().next()
            chunkId = sp.getChunkId()
            chunkProgress = sp.getProgress()
            cpuPower = "{}".format( sp.getCpuPower() )
            timeLeft = "{}".format( sp.getEstimatedTimeLeft() )

        taskId = None
        taskProgress = 0.0
        allocTasks = ""
        allocChunks = ""
        activeTasks = ""
        activeChunks = ""
        chunksLeft = ""

        ltss = ns.getLocalTaskStateSnapshot()
        if len( ltss ) > 0:
            sp = ltss.itervalues().next()
            taskId = sp.getTaskId()
            taskProgress = sp.getProgress()
            allocTasks = "{}".format( sp.getTotalTasks() )
            allocChunks = "{}".format( sp.getTotalChunks() )
            activeTasks = "{}".format( sp.getActiveTasks() )
            activeChunks = "{}".format( sp.getActiveChunks() )
            chunksLeft = "{}".format( sp.getChunksLeft() )

        ep = "{}:{}".format( ns.endpointAddr, ns.endpointPort )
        ts = ns.getFormattedTimestamp()
        pn = "{}".format( ns.getPeersNum() )
        tn = "{}".format( ns.getTasksNum() )
        lm = ""
        if len( ns.getLastNetworkMessages() ) > 0:
            lm = ns.getLastNetworkMessages()[-1]

        nodeDataState = NodeDataState( ns.uid, ts, ep, pn, tn, lm, chunkId, cpuPower, timeLeft, chunkProgress, taskId, allocTasks, allocChunks, activeTasks, activeChunks, chunksLeft, taskProgress )

        self.uic.UpdateNodePresentationState( nodeDataState )

    ########################
    def runAdditionalNodes( self, numNodes ):
        self.managerLogic.runAdditionalNodes( numNodes )

if __name__ == "__main__":

    manager = NodesManager()

    numNodes = 30
    maxLocalTasks = 3
    maxRemoteTasks = 30
    maxLocTaskDuration = 200.0
    maxRemTaskDuration = 28.0
    maxInnerUpdateDelay = 2.0
    nodeSpawnDelay = 1.0

    simulator = LocalNetworkSimulator( manager, numNodes, maxLocalTasks, maxRemoteTasks, maxLocTaskDuration, maxRemTaskDuration, maxInnerUpdateDelay, nodeSpawnDelay )
    manager.setManagerLogic( NodesManagerLogicTest( simulator ) )
    simulator.start()

    manager.execute()
