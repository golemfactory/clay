import sys
sys.path.append( '../ui' )

from PyQt4.QtGui import QApplication, QDialog
from ui_nodemanager import Ui_NodesManagerWidget
from uicustomizer import ManagerUiCustomizer
from nodestatesnapshot import NodeStateSnapshot

class NodesManager:

    def __init__( self ):
        
        self.app = QApplication( sys.argv )
        self.window = QDialog()
        self.ui = Ui_NodesManagerWidget()
        self.ui.setupUi( self.window )
        self.uic = ManagerUiCustomizer(self.ui)

    def execute( self ):
        self.window.show()
        sys.exit(self.app.exec_())

    def UpdateNodeState( self, ns ):
        self.uic.UpdateRowsState( ns.getUID(), ns.getFormattedTimestamp(), ns.getRemoteProgress(), ns.getLocalProgress() )

if __name__ == "__main__":

    from threading import Thread
    import time

    class NodeSimulator(Thread):

        ########################
        def __init__(self, uid, numLocalTasks, numRemoteTasks, localTaskDuration, remoteTaskDuration):
            super(NodeSimulator, self).__init__()
            
            self.uid = uid
            self.numLocalTasks = numLocalTasks
            self.numRemoteTasks = numRemoteTasks
            self.localTaskDuration = localTaskDuration
            self.remoteTaskDuration = remoteTaskDuration
            self.startTime = time.time()

            self.locProgress = 0.0
            self.remProgress = 0.0

        ########################
        def getStateSnapshot( self ):
            return NodeStateSnapshot( self.uid, self.locProgress, self.remProgress )

        ########################
        def run( self ):
            self.startTime = time.time()
            while( time.time() - self.startTime < 5.0 ):
                print "Hej zoey"
                time.sleep( 0.3 )

            print "Finished"

    manager = NodesManager()

    ns0 = NodeStateSnapshot( "some uiid 0", 0.2, 0.7 )
    ns1 = NodeStateSnapshot( "some uiid 1", 0.2, 0.7 )
    ns2 = NodeStateSnapshot( "some uiid 2", 0.2, 0.7 )
    ns3 = NodeStateSnapshot( "some uiid 3", 0.2, 0.7 )

    manager.UpdateNodeState( ns0 )
    manager.UpdateNodeState( ns1 )
    manager.UpdateNodeState( ns2 )
    manager.UpdateNodeState( ns3 )

    ns = NodeSimulator()
    ns.start()

    manager.execute()
