from PyQt4.QtGui import QMessageBox, QFileDialog
from twisted.internet.defer import inlineCallbacks

from gui.view.dialog import SaveKeysDialog, GeneratingKeyWindow
from customizer import Customizer
from generatenewkeywindowcustomizer import GenerateNewKeyWindowCustomizer

GENERATE_NEW_WARNING = u"Are you sure that you want to generate new keys? If you don't save" \
                       u"your current keys you may loose your reputation in the network.\n " \
                       u"You should also take into account that it may take a lot of time to generate" \
                       u"key with high difficulty - application will be ."

LOAD_NEW_WARNING = u"Are you sure that you want to load new keys? If you don't save your current keys you" \
                   u"may loose your reputation in the network."


class IdentityDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.changed = False
        Customizer.__init__(self, gui, logic)
        # FIXME: this button is bound to a deprecated key pair generation method
        self.gui.ui.generate_new_button.setEnabled(False)

    def load_data(self):
        self.set_labels()

    @inlineCallbacks
    def set_labels(self):
        key_id = yield self.logic.get_key_id()
        difficulty = yield self.logic.get_difficulty()
        self.gui.ui.key_id_label.setText(u"Key id: {}".format(key_id))
        self.gui.ui.difficulty_label.setText(u"Difficulty: {}".format(difficulty))

    def keys_changed(self):
        self.set_labels()
        self.changed = True

    @inlineCallbacks
    def _load_from_file(self):
        reply = QMessageBox.warning(self.gui.window, "Warning!", LOAD_NEW_WARNING, QMessageBox.Yes | QMessageBox.No,
                                    defaultButton=QMessageBox.No)
        if reply == QMessageBox.No:
            return

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                 "Choose private key file"))

        result = yield self.logic.load_keys_from_file(file_name)
        if result:
            self.keys_changed()
        else:
            IdentityDialogCustomizer.show_error_window(u"Can't load key from given file")

    def _save_in_file(self):
        save_keys_dialog = SaveKeysDialog(self.gui.window)
        SaveKeysDialogCustomizer(save_keys_dialog, self)
        save_keys_dialog.show()

    def _generate_new_clicked(self):
        try:
            difficulty = int(self.gui.ui.difficulty_spin_box.text())
        except ValueError:
            IdentityDialogCustomizer.show_error_window(u"Difficulty must be an integer [0-255]")
            return

        reply = QMessageBox.warning(self.gui.window, "Warning!", GENERATE_NEW_WARNING, QMessageBox.Yes | QMessageBox.No,
                                    defaultButton=QMessageBox.No)
        if reply == QMessageBox.No:
            return

        self._generate_keys(difficulty)

    def _generate_keys(self, difficulty):
        window = GeneratingKeyWindow(self.gui.window)
        window_customizer = GenerateNewKeyWindowCustomizer(window, self)
        window.show()
        window_customizer.generate_key(difficulty)

    def _setup_connections(self):
        self.gui.ui.ok_button.clicked.connect(lambda: self._close())
        self.gui.ui.generate_new_button.clicked.connect(lambda: self._generate_new_clicked())
        self.gui.ui.load_from_file_button.clicked.connect(lambda: self._load_from_file())
        self.gui.ui.save_in_file_button.clicked.connect(lambda: self._save_in_file())

    def _close(self):
        if self.changed:
            self.logic.key_changed()
        self.gui.window.close()


class SaveKeysDialogCustomizer(Customizer):
    def _setup_connections(self):
        self.gui.ui.ok_button.clicked.connect(lambda: self._save_keys())
        self.gui.ui.cancel_button.clicked.connect(self.gui.window.close)
        self.gui.ui.private_key_button.clicked.connect(lambda: self._choose_private_key_file())
        self.gui.ui.public_key_button.clicked.connect(lambda: self._choose_public_key_file())

    def _choose_private_key_file(self):
        file_path = u"{}".format(self.gui.ui.private_key_line_edit.text())
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                 "Choose private key file", file_path))
        if file_name != "":
            self.gui.ui.private_key_line_edit.setText(u"{}".format(file_name))

    def _choose_public_key_file(self):
        file_path = u"{}".format(self.gui.ui.public_key_line_edit.text())
        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                 "Choose private key file", file_path))
        if file_name != "":
            self.gui.ui.public_key_line_edit.setText(u"{}".format(file_name))

    @inlineCallbacks
    def _save_keys(self):
        private_key_path = u"{}".format(self.gui.ui.private_key_line_edit.text())
        public_key_path = u"{}".format(self.gui.ui.public_key_line_edit.text())
        res = yield self.logic.save_keys_to_files(private_key_path, public_key_path)
        if res:
            self.gui.window.close()
        else:
            self.show_error_window(u"Can't save keys in given files")
