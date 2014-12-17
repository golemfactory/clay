from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout
from PyQt4.QtCore import Qt

class EnvTableElem:
    colItem = [ "idItem", "statusItem", "acceptTasksItem", "shortDescriptionItem" ]

    ############################
    def __init__( self, id, status, shortDescription, acceptTask ):
        self.id                     = id
        self.status                 = status
        self.shortDescription       = shortDescription
        self.acceptTasks            = acceptTask
        self.idItem                 = None
        self.statusItem             = None
        self.shortDescriptionItem   = None
        self.acceptTasksItem        = None

        self.__buildRow()
        self.columnItemTranslation = { "idItem": self.__getIdItem,
                                       "statusItem": self.__getStatusItem,
                                       "acceptTasksItem": self.__getAcceptTasksItem,
                                       "shortDescriptionItem": self.__getShortDescriptionItem }

   ############################
    def getColumnItem( self, col ):
        if col < len( EnvTableElem.colItem ):
            if EnvTableElem.colItem[ col ] in self.columnItemTranslation:
               return self.columnItemTranslation[ EnvTableElem.colItem [ col ] ]()

        assert False, "Wrong column index"

    ############################
    def changeAcceptTaks( self, state ):
        self.acceptTasks = state


    ############################
    def __buildRow( self ):

        self.idItem = QTableWidgetItem()
        self.idItem.setText( self.id )

        self.statusItem = QTableWidgetItem()
        self.statusItem.setText( self.status )

        self.shortDescriptionItem = QTableWidgetItem()
        self.shortDescriptionItem.setText( self.shortDescription )

        self.acceptTasksItem = QTableWidgetItem()
        self.acceptTasksItem.setFlags( Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable )
        if self.acceptTasks:
            self.acceptTasksItem.setCheckState( Qt.Checked )
        else:
            self.acceptTasksItem.setCheckState( Qt.Unchecked )

    ############################
    def __getIdItem( self ):
        return self.idItem

    ############################
    def __getStatusItem( self ):
        return self.statusItem

    ############################
    def __getAcceptTasksItem( self ):
        return self.acceptTasksItem

    ############################
    def __getShortDescriptionItem( self ):
        return self.shortDescriptionItem


