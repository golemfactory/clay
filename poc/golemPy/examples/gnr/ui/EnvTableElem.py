from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout

class EnvTableElem:
    ############################
    def __init__( self, id, status ):
        self.id                 = id
        self.status             = status
        self.idItem             = None
        self.statusItem         = None
        self.__buildRow()

    ############################
    def __buildRow( self ):

        self.idItem = QTableWidgetItem()
        self.idItem.setText( self.id )

        self.statusItem = QTableWidgetItem()
        self.statusItem.setText( self.status )

    ############################
    def getColumnItem( self, col ):
        if col == 0:
            return self.idItem
        if col == 1:
            return self.statusItem

        assert False, "Wrong column index"