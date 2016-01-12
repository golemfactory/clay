from PyQt4 import QtCore

from gnr.customizers.showtaskresourcesdialogcustomizer import ShowTaskResourcesDialogCustomizer
from gnr.ui.checkabledirmodel import CheckableDirModel


class AddResourcesDialogCustomizer(ShowTaskResourcesDialogCustomizer):
    def __init__(self, gui, logic):
        self.resources = set()
        ShowTaskResourcesDialogCustomizer.__init__(self, gui, logic)

    def load_data(self):
        fs_model = CheckableDirModel()
        fs_model.setRootPath("")
        fs_model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot)

        self.gui.ui.folderTreeView.setModel(fs_model)
        self.gui.ui.folderTreeView.setColumnWidth(0, self.gui.ui.folderTreeView.columnWidth(0) * 2)

    def _set_folder_tree(self, gui):
        self.folder_tree = gui.ui.folderTreeView

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.__ok_button_clicked)
        ShowTaskResourcesDialogCustomizer._setup_connections(self)

    def __ok_button_clicked(self):
        self.resources = self.gui.ui.folderTreeView.model().export_checked()
        self.gui.window.close()
