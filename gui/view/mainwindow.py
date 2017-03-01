from PyQt5.QtWidgets import QMainWindow, QMessageBox
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