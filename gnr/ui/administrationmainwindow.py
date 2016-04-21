from PyQt4.QtGui import QMainWindow, QPixmap, QMessageBox
from gen.ui_AdministratorMainWindow import Ui_AdministrationMainWindow


class MainWindow(QMainWindow):
    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Golem Message',
                                     "Are you sure you want to quit?", QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
            from twisted.internet import reactor
            if reactor.running:
                reactor.stop()
        else:
            event.ignore()


class AdministrationMainWindow:
    def __init__(self):
        self.window = MainWindow()
        self.ui = Ui_AdministrationMainWindow()

        self.ui.setupUi(self.window)
        self.ui.previewLabel.setPixmap(QPixmap("ui/nopreview.png"))

    def show(self):
        self.window.show()
