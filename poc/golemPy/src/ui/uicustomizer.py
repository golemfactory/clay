from PyQt4 import QtCore, QtGui
from ui_nodemanager import Ui_NodesManagerWidget

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class TableRowDataEntry:

    ########################
    def __init__( self, uidItem, timestampItem, remoteProgressBar, localProgressBar ):
        self.uid = uidItem
        self.timestamp = timestampItem
        self.remoteProgress = remoteProgressBar
        self.localProgress = localProgressBar

class ManagerUiCustomizer:

    ########################
    def __init__( self, widget ):
        self.widget = widget
        self.table = widget.nodeTableWidget
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.tableData = {}

    ########################
    def __createWrappedProgressBar( self ):

        widget = QtGui.QWidget()
        widget.setFixedSize( 166, 22 )

        progressBar = QtGui.QProgressBar( widget )
        progressBar.setGeometry(7, 2, 159, 16)
        progressBar.setProperty("value", 0)

        return widget, progressBar

    ########################
    def __addProgressBar( self, row, col ):
        w, p = self.__createWrappedProgressBar()
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

        pRem = self.__addProgressBar( nextRow, 2 )
        pLoc = self.__addProgressBar( nextRow, 3 )

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
