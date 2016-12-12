from PyQt4 import QtCore

from customizer import Customizer


class ShowTaskResourcesDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self._set_folder_tree(gui)
        Customizer.__init__(self, gui, logic)

    def _set_folder_tree(self, gui):
        self.folder_tree = gui.ui.folderTreeView

    def _setup_connections(self):
        QtCore.QObject.connect(self.folder_tree
                               , QtCore.SIGNAL("expanded (const QModelIndex)")
                               , self.__tree_view_expanded)

        QtCore.QObject.connect(self.folder_tree
                               , QtCore.SIGNAL("collapsed (const QModelIndex)")
                               , self.__tree_view_collapsed)

    def __tree_view_expanded(self, index):
        self.folder_tree.resizeColumnToContents(0)

    def __tree_view_collapsed(self, index):
        self.folder_tree.resizeColumnToContents(0)