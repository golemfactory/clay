from PyQt4.QtGui import QFileDialog

from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog
import os

class AddResourcesDialogCustomizer:
    ############################
    def __init__(self, gui, logic):

        assert isinstance(gui, AddTaskResourcesDialog)

        self.gui        = gui
        self.logic      = logic

        self.resources  = set()

        self.__setup_connections()

    #############################
    def __setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.__okButtonClicked)

    #############################
    def __okButtonClicked(self):
        self.resources = self.gui.ui.folderTreeView.model().export_checked()
        self.gui.window.close()
