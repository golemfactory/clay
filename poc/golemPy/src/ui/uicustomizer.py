from PyQt4 import QtCore, QtGui
from ui_nodemanager import Ui_NodesManagerWidget

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class NodeDataState:

    ########################
    def __init__( self, uid, timestamp, endpoint, numPeers, numTasks, lastMsg, chunkId, cpuPower, timeLeft, chunkProgress, chunkShortDescr, locTaskId, allocatedTasks, allocatedChunks, activeTasks, activeChunks, chunksLeft, locTaskProgress, locTaskShortDescr ):
        self.uid = uid
        self.timestamp = timestamp
        self.endpoint = endpoint
        self.numPeers = numPeers
        self.numTasks = numTasks
        self.lastMsg = lastMsg
        self.chunkId = chunkId
        self.cpuPower = cpuPower
        self.timeLeft = timeLeft
        self.chunkProgress = chunkProgress
        self.chunkShortDescr = chunkShortDescr
        self.locTaskId = locTaskId
        self.allocatedTasks = allocatedTasks
        self.allocatedChunks = allocatedChunks
        self.activeTasks = activeTasks
        self.activeChunks = activeChunks
        self.chunksLeft = chunksLeft
        self.locTaskProgress = locTaskProgress
        self.locTaskShortDescr = locTaskShortDescr

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

    ########################
    def addNodesClicked( self ):
        numNodes = self.widget.additionalNodesSpinBox.value()
        self.logic.runAdditionalNodes( numNodes )

    ########################
    def rowSelectionChanged( self, item1, item2 ):
        if not self.detailedViewEnabled:
            self.detailedViewEnabled = True
            self.enableDetailedView( True )

        idx = item1.indexes()[ 0 ].row()

        uid = self.nodeDataStates[ idx ].uid
        self.curActiveRowIdx = idx
        self.curActiveRowUid = uid

        self.__updateDetailedNodeView( idx, self.nodeDataStates[ idx ] )

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
    def __updateExistingRowView( self, rowData, nodeUid, nodeTimestamp, progressRemote, progressLoc ):
        rowData.uid.setText( nodeUid )
        rowData.timestamp.setText( nodeTimestamp )
        rowData.remoteProgress.setProperty("value", int( 100.0 * progressRemote ) )
        rowData.localProgress.setProperty("value", int( 100.0 * progressLoc ) )

    ########################
    def __updateDetailedNodeView( self, idx, nodeDataState ):
        if self.detailedViewEnabled and self.curActiveRowIdx == idx:
            
            self.widget.labelDetailedNode.setText( "Node ({})".format( nodeDataState.uid[:15] ) )
            
            if nodeDataState.chunkId and len( nodeDataState.chunkId ) > 0:
                self.widget.labelDetailedRemoteTask.setText( "Active remote task ({})".format( nodeDataState.chunkId[:15]) )
            else:
                self.widget.labelDetailedRemoteTask.setText( "Active remote task (none)" )

            if nodeDataState.locTaskId and len( nodeDataState.locTaskId ) > 0:
                self.widget.labelDetailedLocalTask.setText( "Active local task ({})".format( nodeDataState.locTaskId[:15] ) )
            else:
                self.widget.labelDetailedLocalTask.setText( "Active local task (none)" )

            self.widget.endpointInput.setText( nodeDataState.endpoint )
            self.widget.noPeersInput.setText( nodeDataState.numPeers )
            self.widget.noTasksInput.setText( nodeDataState.numTasks )
            self.widget.lastMsgInput.setText( nodeDataState.lastMsg )

            self.widget.chunkShortDescrInput.setText( nodeDataState.chunkShortDescr )
            self.widget.cpuPowerInput.setText( nodeDataState.cpuPower )
            self.widget.timeLeftInput.setText( nodeDataState.timeLeft )
            self.widget.activeChunkProgressBar.setProperty( "value", int( 100.0 * nodeDataState.chunkProgress ) )

            self.widget.locTaskShortDescrInput.setText( nodeDataState.locTaskShortDescr )
            self.widget.allocatedTasksInput.setText( nodeDataState.allocatedTasks )
            self.widget.allocatedChunksInput.setText( nodeDataState.allocatedChunks )
            self.widget.activeTasksInput.setText( nodeDataState.activeTasks )
            self.widget.activeChunksInput.setText( nodeDataState.activeChunks )
            self.widget.chunksLeftInput.setText( nodeDataState.chunksLeft )
            self.widget.localTaskProgressBar.setProperty( "value", int( 100.0 * nodeDataState.locTaskProgress ) )

    ########################
    def __resetDetailedView( self ):
        self.widget.labelDetailedNode.setText( "Node (none)" )
        self.widget.labelDetailedRemoteTask.setText( "Active remote task (none)" )
        self.widget.labelDetailedLocalTask.setText( "Active local task (none)" )
        self.widget.activeChunkProgressBar.setProperty("value", 0)
        self.widget.localTaskProgressBar.setProperty("value", 0)

    ########################
    def __registerRowData( self, nodeUid, rowDataEntry, nodeDataState ):
        self.tableData[ nodeUid ] = rowDataEntry
        self.uidRowMapping[ nodeUid ] = len( self.nodeDataStates )
        self.nodeDataStates.append( nodeDataState )

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
        self.__updateExistingRowView( self.tableData[ nodeDataState.uid ], nodeDataState.uid, nodeDataState.timestamp, nodeDataState.chunkProgress, nodeDataState.locTaskProgress )        
        self.__updateDetailedNodeView( idx, nodeDataState )
