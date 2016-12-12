from PyQt4.QtGui import QMainWindow, QMessageBox
from gui.view.gen.ui_AppMainWindow import Ui_MainWindow


class MainWindow(QMainWindow):

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Golem Message',
                                     "Are you sure you want to quit?", QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
            if hasattr(self, "logic_quit_func"):
                self.logic_quit_func()
            from twisted.internet import reactor
            if reactor.running:
                reactor.stop()
        else:
            event.ignore()


class GNRMainWindow:
    def __init__(self):
        self.window = MainWindow()
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self.window)

    def show(self):
        self.window.show()
