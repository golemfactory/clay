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

    manager = NodesManager()

    ns0 = NodeStateSnapshot( "some uiid 0", 0.2, 0.7 )
    ns1 = NodeStateSnapshot( "some uiid 1", 0.2, 0.7 )
    ns2 = NodeStateSnapshot( "some uiid 2", 0.2, 0.7 )
    ns3 = NodeStateSnapshot( "some uiid 3", 0.2, 0.7 )

    manager.UpdateNodeState( ns0 )
    manager.UpdateNodeState( ns1 )
    manager.UpdateNodeState( ns2 )
    manager.UpdateNodeState( ns3 )

    manager.execute()
