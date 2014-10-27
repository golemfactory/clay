from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout

class EnvTableElem:
    ############################
    def __init__( self, id, status, shortDescription ):
        self.id                     = id
        self.status                 = status
        self.shortDescription       = shortDescription
        self.idItem                 = None
        self.statusItem             = None
        self.shortDescriptionItem   = None
        self.__buildRow()

    ############################
    def __buildRow( self ):

        self.idItem = QTableWidgetItem()
        self.idItem.setText( self.id )

        self.statusItem = QTableWidgetItem()
        self.statusItem.setText( self.status )

        self.shortDescriptionItem = QTableWidgetItem()
        self.shortDescriptionItem.setText( self.shortDescription )

    ############################
    def getColumnItem( self, col ):
        if col == 0:
            return self.idItem
        if col == 1:
            return self.statusItem
        if col == 2:
            return self.shortDescriptionItem

        assert False, "Wrong column index"