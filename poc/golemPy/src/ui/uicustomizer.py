from PyQt4 import QtCore, QtGui
from ui_nodemanager import Ui_NodesManagerWidget

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

#FIXME: add start local task button to manager (should trigger another local task for selected node)
#FIXME: rething deleting nodes which seem to be inactive
class TableRowDataEntry:

    ########################
    def __init__( self, uidItem, timestampItem, remoteProgressBar, localProgressBar ):
        self.uid = uidItem
        self.timestamp = timestampItem
        self.remoteProgress = remoteProgressBar
        self.localProgress = localProgressBar

class ManagerUiCustomizer(QtCore.QObject):

    ########################
    def __init__( self, widget, managerLogic ):
        self.widget = widget
        self.table = widget.nodeTableWidget
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.tableData = {}
        self.logic = managerLogic

        self.table.selectionModel().selectionChanged.connect( self.rowSelectionChanged )
        self.widget.runAdditionalNodesPushButton.clicked.connect( self.addNodesClicked )

    ########################
    def addNodesClicked( self ):
        numNodes = self.widget.additionalNodesSpinBox.value()
        self.logic.runAdditionalNodes( numNodes )

    ########################
    def rowSelectionChanged( self, item1, item2 ):
        print item1.indexes()[ 0 ].row()

    ########################
    def __createWrappedProgressBar( self, red ):

        widget = QtGui.QWidget()
        widget.setFixedSize( 166, 22 )

        progressBar = QtGui.QProgressBar( widget )
        progressBar.setGeometry(7, 2, 159, 16)
        progressBar.setProperty("value", 0)

        if red:
            progressBar.setStyleSheet(" QProgressBar { border: 2px solid grey; border-radius: 0px; text-align: center; } QProgressBar::chunk {background-color: #dd3a36; width: 1px;}" )
        else:
            progressBar.setStyleSheet(" QProgressBar { border: 2px solid grey; border-radius: 0px; text-align: center; } QProgressBar::chunk {background-color: #3add36; width: 1px;}" )

        return widget, progressBar

    ########################
    def __addProgressBar( self, row, col, red = False ):
        w, p = self.__createWrappedProgressBar( red )
        self.table.setCellWidget( row, col, w )
        return p

    ########################
    def __createRow( self, nodeUid, nodeTime ):
        nextRow = self.table.rowCount()
        
        self.table.insertRow( nextRow )

        item0 = QtGui.QTableWidgetItem()
        item1 = QtGui.QTableWidgetItem()

        self.table.setItem( nextRow, 0, item0 )
        self.table.setItem( nextRow, 1, item1 )

        pRem = self.__addProgressBar( nextRow, 2, False )
        pLoc = self.__addProgressBar( nextRow, 3, True )

        assert nodeUid not in self.tableData

        return TableRowDataEntry( item0, item1, pRem, pLoc )

    ########################
    def __updateExistingRow( self, rowData, nodeUid, nodeTimestamp, progressRemote, progressLoc ):
        rowData.uid.setText( nodeUid )
        rowData.timestamp.setText( nodeTimestamp )
        rowData.remoteProgress.setProperty("value", int( 100.0 * progressRemote ) )
        rowData.localProgress.setProperty("value", int( 100.0 * progressLoc ) )

    ########################
    def __registerRowData( self, nodeUid, rowDataEntry ):
        self.tableData[ nodeUid ] = rowDataEntry

    ########################
    def isRegistered( self, nodeUid ):
        return nodeUid in self.tableData

    ########################
    def UpdateRowsState( self, nodeUid, nodeTimestamp, progressRemote, progressLocal ):
        if not self.isRegistered( nodeUid ):
            self.__registerRowData( nodeUid, self.__createRow( nodeUid, nodeTimestamp ) )

        self.__updateExistingRow( self.tableData[ nodeUid ], nodeUid, nodeTimestamp, progressRemote, progressLocal )

    ########################
    def __resetDetailedView( self ):
        self.widget.labelDetailedNode.setText( "Node (none)" )
        self.widget.labelDetailedRemoteTask.setText( "Active remote task (none)" )
        self.widget.labelDetailedLocalTask.setText( "Active local task (none)" )
        self.widget.remoteTaskProgressBar.setProperty("value", 0)
        self.widget.localTaskProgressBar.setProperty("value", 0)

    ########################
    def enableDetailedView( self, enableFlag ):
        if not enableFlag:
            self.__resetDetailedView()

        self.widget.frameDetailedNode.setEnabled( enableFlag )
