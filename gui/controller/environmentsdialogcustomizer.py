from twisted.internet.defer import inlineCallbacks

from gui.controller.customizer import Customizer

from gui.view.envtableelem import EnvTableElem
from PyQt4 import QtCore
from PyQt4.Qt import Qt
import logging

logger = logging.getLogger("gui")


class EnvironmentsDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.environments = set()
        Customizer.__init__(self, gui, logic)

    @inlineCallbacks
    def load_data(self):
        self.gui.ui.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.environments = yield self.logic.get_environments()
        for env in self.environments:
            current_row_count = self.gui.ui.tableWidget.rowCount()
            self.gui.ui.tableWidget.insertRow(current_row_count)

            env_table_elem = EnvTableElem(env.get_id(), self.__print_supported(env.supported()), env.short_description,
                                          env.is_accepted())
            for col in range(0, 4):
                self.gui.ui.tableWidget.setItem(current_row_count, col, env_table_elem.get_column_item(col))

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.close)
        QtCore.QObject.connect(self.gui.ui.tableWidget, QtCore.SIGNAL("cellClicked(int, int)"),
                               self.__task_table_row_clicked)

    @staticmethod
    def __print_supported(val):
        if val:
            return "Supported"
        else:
            return "Not supported"

    def __task_table_row_clicked(self, row, col):
        if row < self.gui.ui.tableWidget.rowCount():
            env_id = self.gui.ui.tableWidget.item(row, EnvTableElem.colItem.index('id_item')).text()
            env = self.__get_env(env_id)
            if env:
                self.gui.ui.envTextBrowser.setText(env.description())
                if col == EnvTableElem.colItem.index('accept_tasks_item'):
                    if self.gui.ui.tableWidget.item(row, col).checkState() == Qt.Unchecked and env.is_accepted():
                        self.logic.disable_environment(env_id)
                    elif self.gui.ui.tableWidget.item(row, col).checkState() == Qt.Checked and not env.is_accepted():
                        self.logic.enable_environment(env_id)

    def __get_env(self, id_):
        for env in self.environments:
            if env.get_id() == id_:
                return env
        return None
