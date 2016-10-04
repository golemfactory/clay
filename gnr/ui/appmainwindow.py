from os import path

from PyQt4.QtGui import QPixmap, QFrame, QHeaderView

from golem.core.common import get_golem_path

from gen.ui_AppMainWindow import Ui_MainWindow
from mainwindow import MainWindow


class AppMainWindow(object):

    def __init__(self):
        self.window = MainWindow()
        self.ui = Ui_MainWindow()

        self.ui.setupUi(self.window)

        table = self.ui.taskTableWidget
        header = table.horizontalHeader()
        header.setResizeMode(QHeaderView.ResizeToContents)

        self.ui.previewLabel.setFrameStyle(QFrame.NoFrame)
        self.ui.previewLabel.setPixmap(QPixmap(path.join(get_golem_path(), "gnr", "ui", "nopreview.png")))

        self.__new_task_buttons = [
                self.ui.showAdvanceNewTaskButton,
                self.ui.addResourceButton,
                self.ui.saveButton,
                self.ui.loadButton,
                self.ui.taskTypeComboBox,
            ]
        self.__recount_buttons = [
                self.ui.recountBlenderButton,
                self.ui.recountButton,
                self.ui.recountLuxButton,
                self.ui.settingsOkButton,
                self.ui.settingsCancelButton,
            ]
        self.__style_sheet = "color: black"

    def show(self):
        self.window.show()

    def setEnabled(self, tab_name, enable):
        """
        Enable or disable buttons on the 'New task' or 'Provider' tab
        :param tab_name: Tab name. Available values: 'new_task' and 'recount'
        :param enable: enable if True, disable otherwise
        """
        tab_name = tab_name.lower()

        if tab_name == 'new_task':
            self.__set_enabled(self.__new_task_buttons, enable)
            if enable and self.__style_sheet is not None:
                self.ui.startTaskButton.setStyleSheet(self.__style_sheet)
        elif tab_name == 'settings':
            self.ui.settingsOkButton.setEnabled(enable)
            self.ui.settingsCancelButton.setEnabled(enable)
        elif tab_name == 'recount':
            self.__set_enabled(self.__recount_buttons, enable)

    def __set_enabled(self, elements, enable):
        """
        Enable or disable buttons
        :param elements: UI elements to be enabled or disabled
        :param enable: enable if True, disable otherwise
        """
        for element in elements:
            element.setEnabled(enable)
            if enable and self.__style_sheet is not None:
                element.setStyleSheet(self.__style_sheet)
