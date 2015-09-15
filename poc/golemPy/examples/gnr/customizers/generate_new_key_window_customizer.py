#from Customizer import Customizer
import threading


class GenerateNewKeyWindowCustomizer():
    def __init__(self, gui, parent):
        self.gui = gui
        self.parent = parent
        self.thread = None

        self.set_label()

    def set_label(self):
        self.gui.ui.name_label.setText("Generating key...")

    def set_params(self, difficulty):
        self.generate_key(self.parent.keys_auth, difficulty)

    def generate_key(self, keys_auth, difficulty):
        self.thread = threading.Thread(target=self._generate_keys_func, args=(keys_auth, difficulty))
        self.thread.start()

    def _generate_keys_func(self, keys_auth, difficulty):
        keys_auth.generate_new(difficulty, "BLA")
        self.parent.set_labels()
        self.gui.window.close()
