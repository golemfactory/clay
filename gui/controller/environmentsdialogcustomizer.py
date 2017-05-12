from twisted.internet.defer import inlineCallbacks

from gui.controller.customizer import Customizer

from gui.view.envtableelem import EnvTableElem
from PyQt5.Qt import Qt
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

            env_supported = 'Supported' if env['supported'] else 'Not supported'
            env_table_elem = EnvTableElem(env['id'],
                                          env_supported,
                                          env['description'],
                                          env['accepted'])
            for col in range(0, 4):
                self.gui.ui.tableWidget.setItem(current_row_count, col, env_table_elem.get_column_item(col))

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.close)
        self.gui.ui.tableWidget.cellClicked.connect(self.__task_table_row_clicked)

    def __task_table_row_clicked(self, row, col):
        if row < self.gui.ui.tableWidget.rowCount():
            env_id = self.gui.ui.tableWidget.item(row, EnvTableElem.colItem.index('id_item')).text()
            env = self.__get_env(env_id)
            if env:
                self.gui.ui.envTextBrowser.setText(env['description'])
                if col == EnvTableElem.colItem.index('accept_tasks_item'):
                    if self.gui.ui.tableWidget.item(row, col).checkState() == Qt.Unchecked and env['accepted']:
                        self.logic.disable_environment(env_id)
                    elif self.gui.ui.tableWidget.item(row, col).checkState() == Qt.Checked and not env['accepted']:
                        self.logic.enable_environment(env_id)

    def __get_env(self, id_):
        for env in self.environments:
            if env['id'] == id_:
                return env
        return None
