from gnr.customizers.customizer import Customizer


class NodeNameDialogCustomizer(Customizer):
    def __init__(self, gui, logic, cfg_desc):
        super(NodeNameDialogCustomizer, self).__init__(gui, logic)
        self.cfg_desc = cfg_desc

    def load_data(self):
        pass

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(lambda: self._save_node_name())

    def _save_node_name(self):
        self.cfg_desc.node_name = u"{}".format(self.gui.ui.nodeNameLineEdit.text())
        if self.cfg_desc.node_name == "":
            self.show_error_window("Empty name")
        else:
            self.logic.change_config(self.cfg_desc)
            self.gui.window.close()
