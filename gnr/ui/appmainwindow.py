from os import path

from PyQt4.QtGui import QPixmap, QFrame

from golem.core.common import get_golem_path

from gen.ui_AppMainWindow import Ui_MainWindow
from mainwindow import MainWindow


class AppMainWindow(object):

    def __init__(self):
        self.window = MainWindow()
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self.window)
        self.ui.previewLabel.setFrameStyle(QFrame.NoFrame)
        self.ui.previewLabel.setPixmap(QPixmap(path.join(get_golem_path(), "gnr", "ui", "nopreview.png")))

    def show(self):
        self.window.show()

    def setEnabled(self, tab_name, enable):
        """
        Enable or disable buttons on the 'New task' or 'Provider' tab
        :param tab_name: Tab name. Available values: 'new_task' and 'recount'
        :param enable: enable if True, disable otherwise
        """
        if tab_name.lower() == 'new_task':
            self.ui.testTaskButton.setEnabled(enable)
            self.ui.showAdvanceNewTaskButton.setEnabled(enable)
            self.ui.addResourceButton.setEnabled(enable)
            self.ui.saveButton.setEnabled(enable)
            self.ui.loadButton.setEnabled(enable)
            self.ui.taskTypeComboBox.setEnabled(enable)
        elif tab_name.lower() == 'recount':
            self.ui.recountBlenderButton.setEnabled(enable)
            self.ui.recountButton.setEnabled(enable)
            self.ui.recountLuxButton.setEnabled(enable)
            self.ui.settingsOkButton.setEnabled(enable)
            self.ui.settingsCancelButton.setEnabled(enable)
