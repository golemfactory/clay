from PyQt4 import QtCore, QtGui
from ui_manager import Ui_NodesManagerWidget
from taskdialog import TaskSpecDialog
from NodeTasksSpec import NodeTasksWidget
from progressbar import createWrappedProgressBar
import logging

logger = logging.getLogger(__name__)

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class NodeDataState:

    ########################
    def __init__( self, running, uid, timestamp, endpoint, numPeers, numTasks, lastMsg, ltsd, rcsd ):
        self.isRunning = running
        self.uid = uid
        self.timestamp = timestamp
        self.endpoint = endpoint
        self.numPeers = numPeers
        self.numTasks = numTasks
        self.lastMsg = lastMsg
        self.localTasksStateData = ltsd
        self.remoteChunksStateData = rcsd

#FIXME: add start local task button to manager (should trigger another local task for selected node)
#FIXME: rething deleting nodes which seem to be inactive
class TableRowDataEntry:

    ########################
    def __init__( self, uidItem, timestampItem, remoteChunksCount, localTasksCount ):
        self.uid = uidItem
        self.timestamp = timestampItem
        self.remoteChunksCount = remoteChunksCount
        self.localTasksCount = localTasksCount

class ManagerUiCustomizer(QtCore.QObject):

    ########################
    def __init__( self, widget, managerLogic ):
        super(ManagerUiCustomizer, self).__init__()

        self.widget = widget
        self.table = widget.nodeTableWidget
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.tableData = {}
        self.nodeDataStates = []
        self.uidRowMapping = {}
        self.logic = managerLogic
        self.detailedViewEnabled = False
        self.curActiveRowIdx = None
        self.curActiveRowUid = None

        self.table.selectionModel().selectionChanged.connect( self.rowSelectionChanged )
        self.widget.runAdditionalNodesPushButton.clicked.connect( self.addNodesClicked )
        self.widget.stopNodePushButton.clicked.connect( self.stopNodeClicked )
        self.widget.enqueueTaskButton.clicked.connect( self.enqueueTaskClicked )
        self.widget.terminateAllNodesPushButton.clicked.connect( self.terminateAllNodesClicked )
        self.table.cellDoubleClicked.connect( self.cellDoubleClicked )

        self.nodeTaskWidgets = {}

    ########################
    def addNodesClicked( self ):
        numNodes = self.widget.additionalNodesSpinBox.value()
        self.logic.runAdditionalNodes( numNodes )

    ########################
    def stopNodeClicked( self ):
        if self.curActiveRowIdx is not None and self.curActiveRowUid is not None:
            self.logic.terminateNode( self.curActiveRowUid )

    ########################
    def terminateAllNodesClicked( self ):
        self.logic.terminateAllNodes()

    ########################
    def enqueueTaskClicked( self ):
        dialog = TaskSpecDialog( self.table )
        if dialog.exec_():
            w = dialog.getWidth()
            h = dialog.getHeight()
            n = dialog.getNumSamplesPerPixel()
            p = dialog.getFileName()

            self.logic.enqueueNewTask( self.curActiveRowUid, w, h, n, p )

    ########################
    def rowSelectionChanged( self, item1, item2 ):
        if not self.detailedViewEnabled:
            self.detailedViewEnabled = True
            self.enableDetailedView( True )

        indices = item1.indexes()

        if len( indices ) > 0 and len( self.nodeDataStates ) > 0:
            idx = indices[ 0 ].row()
            
            if idx >= len( self.nodeDataStates ):
                idx = len( self.nodeDataStates ) - 1

            uid = self.nodeDataStates[ idx ].uid
            self.curActiveRowIdx = idx
            self.curActiveRowUid = uid

            #self.__updateDetailedNodeView( idx, self.nodeDataStates[ idx ] )
        else:
            self.detailedViewEnabled = False
            self.__resetDetailedView()
            self.enableDetailedView( False )

    def cellDoubleClicked( self, row, column ):

        w = NodeTasksWidget( None )
        w.setNodeUid( "Node UID: {}".format( self.curActiveRowUid ) )
        self.nodeTaskWidgets[ self.curActiveRowUid ] = w
        w.show()

    ########################
    def __createRow( self, nodeUid, nodeTime ):
        nextRow = self.table.rowCount()
        
        self.table.insertRow( nextRow )

        item0 = QtGui.QTableWidgetItem()
        item1 = QtGui.QTableWidgetItem()

        self.table.setItem( nextRow, 0, item0 )
        self.table.setItem( nextRow, 1, item1 )

        item2 = QtGui.QTableWidgetItem()
        item3 = QtGui.QTableWidgetItem()

        self.table.setItem( nextRow, 2, item2 )
        self.table.setItem( nextRow, 3, item3 )

        assert nodeUid not in self.tableData

        return TableRowDataEntry( item0, item1, item2, item3 )

    ########################
    def __updateExistingRowView( self, rowData, nodeUid, nodeTimestamp, remoteChunksCount, localTasksCount ):
        rowData.uid.setText( nodeUid )
        rowData.timestamp.setText( nodeTimestamp )
        rowData.remoteChunksCount.setText( str( remoteChunksCount ) )
        rowData.localTasksCount.setText( str( localTasksCount ) )

    ########################
    def __updateDetailedNodeView( self, idx, nodeDataState ):
        if self.detailedViewEnabled and self.curActiveRowIdx == idx:

            self.widget.endpointInput.setText( nodeDataState.endpoint )
            self.widget.noPeersInput.setText( nodeDataState.numPeers )
            self.widget.noTasksInput.setText( nodeDataState.numTasks )
            self.widget.lastMsgInput.setText( nodeDataState.lastMsg )

    ########################
    def __resetDetailedView( self ):
        self.widget.endpointInput.setText( "" )
        self.widget.noPeersInput.setText( "" )
        self.widget.noTasksInput.setText( "" )
        self.widget.lastMsgInput.setText( "" )

    ########################
    def __registerRowData( self, nodeUid, rowDataEntry, nodeDataState ):
        self.tableData[ nodeUid ] = rowDataEntry
        self.uidRowMapping[ nodeUid ] = len( self.nodeDataStates )
        self.nodeDataStates.append( nodeDataState )

    ########################
    def __removeRowAndDetailedData( self, idx, uid ):
        logger.debug( "Removing {} idx from {} total at {} uid".format( idx, len( self.tableData ), uid ) )
        self.nodeDataStates.pop( idx )
        del self.tableData[ uid ]
        self.table.removeRow( idx )

        self.uidRowMapping = {}
        for i, nds in enumerate( self.nodeDataStates ):
            self.uidRowMapping[ nds.uid ] = i

        curRow = self.table.currentRow()

        if curRow is not None and curRow >= 0:
            self.curActiveRowIdx = curRow
            self.curActiveRowUid = self.nodeDataStates[ curRow ].uid

    ########################
    def isRegistered( self, nodeUid ):
        return nodeUid in self.tableData

    ########################
    def enableDetailedView( self, enableFlag ):
        if not enableFlag:
            self.__resetDetailedView()

        self.widget.frameDetailedNode.setEnabled( enableFlag )

    ########################
    def UpdateNodePresentationState( self, nodeDataState ):
        #prerequisites
        if not self.isRegistered( nodeDataState.uid ):
            self.__registerRowData( nodeDataState.uid, self.__createRow( nodeDataState.uid, nodeDataState.timestamp ), nodeDataState )

        #update model
        idx = self.uidRowMapping[ nodeDataState.uid ]
        self.nodeDataStates[ idx ] = nodeDataState

        #update view
        if nodeDataState.isRunning:
            self.__updateExistingRowView( self.tableData[ nodeDataState.uid ], nodeDataState.uid, nodeDataState.timestamp, len( nodeDataState.remoteChunksStateData ), len( nodeDataState.localTasksStateData ) )        
            self.__updateDetailedNodeView( idx, nodeDataState )
        else:
            self.__removeRowAndDetailedData( idx, nodeDataState.uid )

        if nodeDataState.uid in self.nodeTaskWidgets:
            self.nodeTaskWidgets[ nodeDataState.uid ].updateNodeViewData( nodeDataState )
