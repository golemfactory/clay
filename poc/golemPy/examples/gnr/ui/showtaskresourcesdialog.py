from PyQt4 import QtCore
from PyQt4.QtGui import QDialog, QFileSystemModel

from gen.ui_ShowTaskResourcesDialog import Ui_ShowTaskResourceDialog

class ShowTaskResourcesDialog:
    #######################
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_ShowTaskResourceDialog()
        self.ui.setupUi(self.window)

        self.__setup_connections()

    ###################
    def show(self):
        self.window.show()

    ###################
    def __setup_connections(self):
        QtCore.QObject.connect(self.ui.folderTreeWidget
                        , QtCore.SIGNAL("expanded (const QModelIndex)")
                        , self.__tree_view_expanded)

        QtCore.QObject.connect(self.ui.folderTreeWidget
                        , QtCore.SIGNAL("collapsed (const QModelIndex)")
                        , self.__tree_view_collapsed)

    # SLOTS
    ############################
    def __tree_view_expanded(self, index):
        self.ui.folderTreeWidget.resizeColumnToContents(0)

    ############################
    def __tree_view_collapsed(self, index):
        self.ui.folderTreeWidget.resizeColumnToContents(0)
