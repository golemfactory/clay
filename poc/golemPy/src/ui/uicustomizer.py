from PyQt4 import QtCore, QtGui
from ui_nodemanager import Ui_NodesManagerWidget

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class TableDataEntry:

    def __init__( self, uidItem, timestampItem, remoteProgressBar, localProgressBar ):
        self.uid = uidItem
        self.timestamp = timestampItem
        self.remoteProgress = remoteProgressBar
        self.localProgress = localProgressBar

class ManagerUiCustomizer:

    def __init__( self, widget ):
        self.widget = widget
        self.table = widget.nodeTableWidget
        
        self.tableData = {}

    def __createWrappedProgressBar( self ):

        widget = QtGui.QWidget()
        widget.setFixedSize( 166, 22 )

        progressBar = QtGui.QProgressBar( widget )
        progressBar.setGeometry(7, 2, 159, 16)
        progressBar.setProperty("value", 24)

        return widget, progressBar

    def addProgressBar( self, row, col ):
        w, p = self.__createWrappedProgressBar()
        self.table.setCellWidget( row, col, w )
        return p

    def appendRow( self, nodeUid, nodeTime ):
        nextRow = self.table.rowCount()
        
        self.table.insertRow( nextRow )

        item0 = QtGui.QTableWidgetItem()
        item0.setText( nodeUid )
        self.table.setItem( nextRow, 0, item0 )

        item1 = QtGui.QTableWidgetItem()
        item1.setText( nodeTime )
        self.table.setItem( nextRow, 1, item1 )

        pRem = self.addProgressBar( nextRow, 2 )
        pLoc = self.addProgressBar( nextRow, 3 )

        assert nodeUid not in self.tableData

        self.tableData[ nodeUid ] = TableDataEntry( item0, item1, pRem, pLoc )
