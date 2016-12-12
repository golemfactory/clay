import threading


class GenerateNewKeyWindowCustomizer(object):
    def __init__(self, gui, parent):
        self.gui = gui
        self.parent = parent
        self.thread = None
        self.set_label()

    def set_label(self):
        self.gui.ui.name_label.setText("Generating key...")

    def generate_key(self, difficulty):
        keys_auth = self.parent.keys_auth
        self.thread = threading.Thread(target=self._generate_keys_func, args=(keys_auth, difficulty))
        self.thread.start()

    def _generate_keys_func(self, keys_auth, difficulty):
        keys_auth.generate_new(difficulty)
        self.parent.keys_changed()
        self.gui.window.close()
