from PyQt4 import QtCore, QtGui
from ui_nodemanager import Ui_NodesManagerWidget

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

class UICustomizationService:

    def __init__( self, widget ):
        self.widget = widget
        self.table = widget.nodeTableWidget

    def __createWrappedProgressBar( self ):

        widget = QtGui.QWidget()
        widget.setFixedSize( 166, 22 )

        progressBar = QtGui.QProgressBar( widget )
        progressBar.setGeometry(7, 2, 159, 16)
        progressBar.setProperty("value", 24)

        return widget

    def addProgressBar( self, row, col ):
        self.table.setCellWidget( row, col, self.__createWrappedProgressBar() )

def widgetToCell( row, col, table ):


    widget = QtGui.QWidget()
    widget.setFixedSize( 166, 22 )

    #layout = QtGui.QHBoxLayout()
    #widget.setLayout( layout )

    progressBar = QtGui.QProgressBar( widget )
    progressBar.setGeometry(7, 2, 159, 16)
    #progressBar.setEnabled( False )
    progressBar.setProperty("value", 24)
    progressBar.setObjectName(_fromUtf8("progressBarOfDarkness"))

    table.setCellWidget( 0, 2, widget )
     