from Customizer import Customizer


class IdentityDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.keys_auth = None
        Customizer.__init__(self, gui, logic)

    def load_config(self):
        self.keys_auth = self.logic.get_keys_auth()
        self.gui.ui.key_id_label.setText(u"Key id: {}".format(self.keys_auth.get_key_id()))
        self.gui.ui.difficulty_label.setText(u"Difficulty: {}".format(self.keys_auth.get_difficulty()))

    def _setup_connections(self):
        self.gui.ui.ok_button.clicked.connect(self.gui.window.close)
