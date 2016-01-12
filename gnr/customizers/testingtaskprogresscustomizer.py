from customizer import Customizer


class TestingTaskProgressDialogCustomizer(Customizer):
    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.close)

    def show_message(self, msg):
        self.gui.ui.message.setText(msg)