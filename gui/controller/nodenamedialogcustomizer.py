from gui.controller.customizer import Customizer


class NodeNameDialogCustomizer(Customizer):
    def __init__(self, gui, logic, node_name):
        super(NodeNameDialogCustomizer, self).__init__(gui, logic)
        self.node_name = node_name

    def load_data(self):
        pass

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(lambda: self._save_node_name())

    def _save_node_name(self):
        self.node_name = u"{}".format(self.gui.ui.nodeNameLineEdit.text())
        if not self.node_name:
            self.show_error_window(u"Empty name")
        else:
            self.logic.change_node_name(self.node_name)
            self.gui.window.close()
