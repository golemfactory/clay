from PyQt4.QtGui import QTableWidgetItem, QProgressBar, QWidget, QVBoxLayout
from PyQt4.QtCore import Qt

class EnvTableElem:
    colItem = [ "idItem", "statusItem", "accept_tasksItem", "short_descriptionItem" ]

    ############################
    def __init__(self, id, status, short_description, acceptTask):
        self.id                     = id
        self.status                 = status
        self.short_description       = short_description
        self.accept_tasks            = acceptTask
        self.idItem                 = None
        self.statusItem             = None
        self.short_descriptionItem   = None
        self.accept_tasksItem        = None

        self.__buildRow()
        self.columnItemTranslation = { "idItem": self.__get_idItem,
                                       "statusItem": self.__get_statusItem,
                                       "accept_tasksItem": self.__getAcceptTasksItem,
                                       "short_descriptionItem": self.__getShortDescriptionItem }

   ############################
    def getColumnItem(self, col):
        if col < len(EnvTableElem.colItem):
            if EnvTableElem.colItem[ col ] in self.columnItemTranslation:
               return self.columnItemTranslation[ EnvTableElem.colItem [ col ] ]()

        assert False, "Wrong column index"

    ############################
    def changeAcceptTaks(self, state):
        self.accept_tasks = state


    ############################
    def __buildRow(self):

        self.idItem = QTableWidgetItem()
        self.idItem.setText(self.id)

        self.statusItem = QTableWidgetItem()
        self.statusItem.setText(self.status)

        self.short_descriptionItem = QTableWidgetItem()
        self.short_descriptionItem.setText(self.short_description)

        self.accept_tasksItem = QTableWidgetItem()
        self.accept_tasksItem.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        if self.accept_tasks:
            self.accept_tasksItem.setCheckState(Qt.Checked)
        else:
            self.accept_tasksItem.setCheckState(Qt.Unchecked)

    ############################
    def __get_idItem(self):
        return self.idItem

    ############################
    def __get_statusItem(self):
        return self.statusItem

    ############################
    def __getAcceptTasksItem(self):
        return self.accept_tasksItem

    ############################
    def __getShortDescriptionItem(self):
        return self.short_descriptionItem


