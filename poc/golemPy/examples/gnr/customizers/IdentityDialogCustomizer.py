from PyQt4.QtGui import QMessageBox

from examples.gnr.ui.generating_key_window import GeneratingKeyWindow
from Customizer import Customizer
from generate_new_key_window_customizer import GenerateNewKeyWindowCustomizer

GENERATE_NEW_WARNING = u"Are you sure that you want to generate new keys? If you don't save" \
                       u"your current keys you may loose your reputation in the network? \n " \
                       u"You should also take into account that it may take a lot of time to generate" \
                       u"key with high difficulty - application will be ."


class IdentityDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.keys_auth = None
        Customizer.__init__(self, gui, logic)

    def load_config(self):
        self.keys_auth = self.logic.get_keys_auth()
        self.set_labels()

    def set_labels(self):
        self.gui.ui.key_id_label.setText(u"Key id: {}".format(self.keys_auth.get_key_id()))
        self.gui.ui.difficulty_label.setText(u"Difficulty: {}".format(self.keys_auth.get_difficulty()))

    def _generate_new_clicked(self):
        try:
            difficulty = int(self.gui.ui.difficulty_spin_box.text())
        except ValueError:
            IdentityDialogCustomizer._show_error_window("Difficulty must be an integer [0-255]")
            return

        reply = QMessageBox.warning(self.gui.window, "Warning!", GENERATE_NEW_WARNING, QMessageBox.Yes | QMessageBox.No,
                                    defaultButton=QMessageBox.No)
        if reply == QMessageBox.Yes:
            window = GeneratingKeyWindow(self.gui.window)
            window_customizer = GenerateNewKeyWindowCustomizer(window, self)
            window.show()
            window_customizer.set_params(difficulty)
           # ms_box = QMessageBox(QMessageBox.Information, "Info", "Generating key...", QMessageBox.NoButton)
           # ms_box.exec_()
            #ms_box.setText("Generating key...")
            #ms_box.show()


    def _generate_new(self):
        try:
            difficulty = int(self.gui.ui.difficulty_spin_box.text())
        except ValueError:
            IdentityDialogCustomizer._show_error_window("Difficulty must be an integer [0-255]")
            return
        self.keys_auth.generate_new(difficulty, "BLA")
        self.set_labels()

    def _setup_connections(self):
        self.gui.ui.ok_button.clicked.connect(self.gui.window.close)
        self.gui.ui.generate_new_button.clicked.connect(lambda: self._generate_new_clicked())


