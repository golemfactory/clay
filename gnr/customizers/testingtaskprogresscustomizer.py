from customizer import Customizer


class TestingTaskProgressDialogCustomizer(Customizer):
    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.close)
        self.enable_abort_button(False)

    def show_message(self, msg):
        self.gui.ui.message.setText(msg)

    def enable_ok_button(self, enable):
        """
        Enable or disable 'ok' button
        :param enable: True if you want to enable button, false otherwise
        """
        self.gui.ui.okButton.setEnabled(enable)

    def enable_abort_button(self, enable):
        """
        Enable or disable 'abort' button
        :param enable: True if you want to enable button, false otherwise
        """
        self.gui.ui.abortButton.setEnabled(enable)

    def enable_close(self, enable):
        """
        Enable or disable closing of the window via button in the corner.
        Note! This also affects any other method of closing dialog.
        :param enable: True if you allow window to close, False otherwise
        """
        self.gui.window.enable_close(enable)
