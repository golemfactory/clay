from PyQt4.QtGui import QMainWindow, QPixmap, QMessageBox

from gen.ui_AppMainWindow import Ui_MainWindow

from mainwindow import MainWindow


class AppMainWindow(object):

    def __init__(self):
        self.window = MainWindow()
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self.window)
        self.ui.previewLabel.setPixmap(QPixmap("ui/nopreview.png"))

    def show(self):
        self.window.show()

