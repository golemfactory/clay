from os import path

from PyQt4.QtGui import QPixmap

from golem.core.common import get_golem_path

from gen.ui_AppMainWindow import Ui_MainWindow
from mainwindow import MainWindow


class AppMainWindow(object):

    def __init__(self):
        self.window = MainWindow()
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self.window)
        self.ui.previewLabel.setPixmap(QPixmap(path.join(get_golem_path(), "gnr", "ui", "nopreview.png")))

    def show(self):
        self.window.show()

