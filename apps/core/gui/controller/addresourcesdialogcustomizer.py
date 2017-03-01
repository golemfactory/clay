from PyQt5 import QtCore
from PyQt5.QtWidgets import QHeaderView

from gui.controller.showtaskresourcesdialogcustomizer import ShowTaskResourcesDialogCustomizer
from gui.view.checkabledirmodel import CheckableDirModel


class AddResourcesDialogCustomizer(ShowTaskResourcesDialogCustomizer):
    def __init__(self, gui, logic):
        self.resources = set()
        ShowTaskResourcesDialogCustomizer.__init__(self, gui, logic)

    def load_data(self):
        fs_model = CheckableDirModel()
        fs_model.setRootPath("")
        fs_model.setFilter(QtCore.QDir.AllDirs | QtCore.QDir.Files | QtCore.QDir.NoDotAndDotDot)

        self.gui.ui.folderTreeView.setModel(fs_model)

        header = self.gui.ui.folderTreeView.header()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in xrange(1, header.count()):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

    def _set_folder_tree(self, gui):
        self.folder_tree = gui.ui.folderTreeView

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.__ok_button_clicked)
        ShowTaskResourcesDialogCustomizer._setup_connections(self)

    def __ok_button_clicked(self):
        self.resources = self.gui.ui.folderTreeView.model().export_checked()
        self.logic.customizer.gui.ui.resourceFilesLabel.setText(u"{}".format(
            len(self.resources)))
        self.gui.window.close()
