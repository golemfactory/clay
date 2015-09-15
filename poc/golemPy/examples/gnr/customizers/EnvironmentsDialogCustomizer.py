from examples.gnr.ui.EnvironmentsDialog import EnvironmentsDialog
from examples.gnr.ui.EnvTableElem import EnvTableElem
from PyQt4 import QtCore
from PyQt4.Qt import Qt
from PyQt4.QtGui import QTableWidgetItem

import logging

logger = logging.getLogger(__name__)

class EnvironmentsDialogCustomizer:
    def __init__(self, gui, logic):

        assert isinstance(gui, EnvironmentsDialog)

        self.gui    = gui
        self.logic  = logic

        self.__init()
        self.__setup_connections()

    def __init(self):
        self.gui.ui.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.environments = self.logic.get_environments()
        for env in self.environments:
            current_row_count = self.gui.ui.tableWidget.rowCount()
            self.gui.ui.tableWidget.insertRow(current_row_count)

            env_table_elem = EnvTableElem(env.get_id(), self.__print_supported(env.supported()), env.short_description, env.is_accepted() )
            for col in range(0, 4):
                self.gui.ui.tableWidget.setItem(current_row_count, col, env_table_elem.getColumnItem(col))

    def __print_supported(self, val):
        if val:
            return "Supported"
        else:
            return "Not supported"

    def __setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.close)
        QtCore.QObject.connect(self.gui.ui.tableWidget, QtCore.SIGNAL("cellClicked(int, int)"), self.__task_table_row_clicked)

    def __task_table_row_clicked(self, row, col):
        if row < self.gui.ui.tableWidget.rowCount():
            env_id = self.gui.ui.tableWidget.item(row, EnvTableElem.colItem.index('id_item')).text()
            env = self.__get_env(env_id)
            if env:
                self.gui.ui.envTextBrowser.setText(env.description() )
                if col == EnvTableElem.colItem.index('accept_tasksItem'):
                    if self.gui.ui.tableWidget.item(row, col).check_state() == Qt.Unchecked and env.is_accepted():
                        self.logic.change_accept_tasks_for_environment(env_id, False)
                    elif self.gui.ui.tableWidget.item(row, col).check_state() == Qt.Checked and not env.is_accepted():
                        self.logic.change_accept_tasks_for_environment(env_id, True)

    def __get_env(self, id):
        for env in self.environments:
            if env.get_id() == id:
                return env
        return None