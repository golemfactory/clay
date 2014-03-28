from PyQt4 import QtCore, QtGui
from ui_nodemanager import Ui_NodesManagerWidget

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

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

        return widget

    def addProgressBar( self, row, col ):
        self.table.setCellWidget( row, col, self.__createWrappedProgressBar() )

    def appendRow( self, nodeUid, nodeTime ):
        nextRow = self.table.rowCount()
        
        self.table.insertRow( nextRow )

        item = QtGui.QTableWidgetItem()
        item.setText( nodeUid )
        self.table.setItem( nextRow, 0, item )

        item = QtGui.QTableWidgetItem()
        item.setText( nodeTime )
        self.table.setItem( nextRow, 1, item )

        self.addProgressBar( nextRow, 2 )
        self.addProgressBar( nextRow, 3 )
