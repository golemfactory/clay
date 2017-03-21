from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMainWindow, QMessageBox


class MainWindow(QMainWindow):

    def closeEvent(self, event):

        msg_box = QMessageBox(QMessageBox.Question, 'Golem Message',
                              "Are you sure you want to quit?",
                              QMessageBox.Yes | QMessageBox.No, self)
        msg_box.setDefaultButton(QMessageBox.No)
        msg_box.setWindowModality(Qt.WindowModal)

        if msg_box.exec_() == QMessageBox.Yes:
            event.accept()
            if hasattr(self, "logic_quit_func"):
                self.logic_quit_func()
            from twisted.internet import reactor
            if reactor.running:
                reactor.stop()
        else:
            event.ignore()
