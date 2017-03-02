from customizer import Customizer


class ShowTaskResourcesDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self._set_folder_tree(gui)
        Customizer.__init__(self, gui, logic)

    def _set_folder_tree(self, gui):
        self.folder_tree = gui.ui.folderTreeView

    def _setup_connections(self):
        self.folder_tree.expanded.connect(self.__tree_view_expanded)
        self.folder_tree.collapsed.connect(self.__tree_view_collapsed)

    def __tree_view_expanded(self, index):
        self.folder_tree.resizeColumnToContents(0)

    def __tree_view_collapsed(self, index):
        self.folder_tree.resizeColumnToContents(0)