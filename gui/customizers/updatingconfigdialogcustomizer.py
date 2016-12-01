from customizer import Customizer


class UpdatingConfigDialogCustomizer(Customizer):
    def show_message(self, msg):
        self.gui.ui.message.setText(msg)

    def close(self):
        self.gui.close()
