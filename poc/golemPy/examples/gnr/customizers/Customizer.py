class Customizer(object):

    def __init__(self, gui, logic):
        self.gui = gui
        self.logic = logic

        self._setup_connections()

    def _setup_connections(self):
        pass

    def load_config(self):
        pass

    @staticmethod
    def _show_error_window(text):
        from PyQt4.QtGui import QMessageBox
        ms_box = QMessageBox(QMessageBox.Critical, "Error", text)
        ms_box.exec_()
        ms_box.show()