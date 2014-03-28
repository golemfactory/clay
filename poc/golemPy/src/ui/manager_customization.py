from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

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
     