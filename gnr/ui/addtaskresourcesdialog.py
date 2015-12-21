from PyQt4 import QtCore
from PyQt4.QtGui import QDialog
from gen.ui_AddTaskResourcesDialog import Ui_AddTaskResourcesDialog
from checkabledirmodel import CheckableDirModel


class AddTaskResourcesDialog:
    def __init__(self, parent):
        self.window = QDialog(parent)
        self.ui = Ui_AddTaskResourcesDialog()

        self.ui.setupUi(self.window)
        self.__init_folder_tree_view()
        self.__setup_connections()

    def show(self):
        self.window.show()

    def __init_folder_tree_view(self):
        fs_model = CheckableDirModel()
        fs_model.setRootPath("")
        fs_model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot)

        self.ui.folderTreeView.setModel(fs_model)
        self.ui.folderTreeView.setColumnWidth(0, self.ui.folderTreeView.columnWidth(0) * 2)

    def __setup_connections(self):
        QtCore.QObject.connect(self.ui.folderTreeView
                               , QtCore.SIGNAL("expanded (const QModelIndex)")
                               , self.__tree_view_expanded)

        QtCore.QObject.connect(self.ui.folderTreeView
                               , QtCore.SIGNAL("collapsed (const QModelIndex)")
                               , self.__tree_view_collapsed)

    def __tree_view_expanded(self, index):
        self.ui.folderTreeView.resizeColumnToContents(0)

    def __tree_view_collapsed(self, index):
        self.ui.folderTreeView.resizeColumnToContents(0)
