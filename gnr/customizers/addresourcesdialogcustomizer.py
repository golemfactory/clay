from PyQt4 import QtCore

from gnr.customizers.customizer import Customizer
from gnr.ui.checkabledirmodel import CheckableDirModel


class AddResourcesDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.resources = set()
        Customizer.__init__(self, gui, logic)

    def load_data(self):
        fs_model = CheckableDirModel()
        fs_model.setRootPath("")
        fs_model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot)

        self.gui.ui.folderTreeView.setModel(fs_model)
        self.gui.ui.folderTreeView.setColumnWidth(0, self.gui.ui.folderTreeView.columnWidth(0) * 2)

    def _setup_connections(self):
        QtCore.QObject.connect(self.gui.ui.folderTreeView
                               , QtCore.SIGNAL("expanded (const QModelIndex)")
                               , self.__tree_view_expanded)

        QtCore.QObject.connect(self.gui.ui.folderTreeView
                               , QtCore.SIGNAL("collapsed (const QModelIndex)")
                               , self.__tree_view_collapsed)
        self.gui.ui.okButton.clicked.connect(self.__ok_button_clicked)

    def __tree_view_expanded(self, index):
        self.gui.ui.folderTreeView.resizeColumnToContents(0)

    def __tree_view_collapsed(self, index):
        self.gui.ui.folderTreeView.resizeColumnToContents(0)

    def __ok_button_clicked(self):
        self.resources = self.gui.ui.folderTreeView.model().export_checked()
        self.gui.window.close()
