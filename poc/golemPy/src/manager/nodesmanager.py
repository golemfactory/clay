import sys
sys.path.append( '../ui' )

from PyQt4.QtGui import QApplication, QDialog
from PyQt4.QtCore import QTimer
from threading import Lock

from ui_nodemanager import Ui_NodesManagerWidget
from uicustomizer import ManagerUiCustomizer
from networksimulator import GLOBAL_SHUTDOWN, LocalNetworkSimulator

#FIXME: potencjalnie mozna tez spiac ze soba managery i wtedy kontrolowac zdalnie wszystkie koncowki i sobie odpalac nody w miare potrzeb, ale to nie na najblizsza prezentacje zabawa
class NodesManager:

    ########################
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
        
        self.uic.enableDetailedView( False )

        #FIXME: some shitty python magic
        def closeEvent_(self_, event):
            GLOBAL_SHUTDOWN[ 0 ] = True
            event.accept()

        setattr( self.window.__class__, 'closeEvent', closeEvent_ )

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
        self.uic.UpdateRowsState( ns.getUID(), ns.getFormattedTimestamp(), ns.getRemoteProgress(), ns.getLocalProgress() )

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
    simulator.start()

    manager.execute()
