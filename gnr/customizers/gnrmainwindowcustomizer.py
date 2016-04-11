import logging
import os
import cPickle
import appdirs

from PyQt4 import QtCore
from PyQt4.QtGui import QPalette, QFileDialog, QMessageBox, QMenu

from gnr.ui.dialog import PaymentsDialog, TaskDetailsDialog, SubtaskDetailsDialog, ChangeTaskDialog, StatusWindow, \
                          AboutWindow, ConfigurationDialog, EnvironmentsDialog, IdentityDialog, NewTaskDialog
from gnr.ui.tasktableelem import TaskTableElem

from gnr.customizers.customizer import Customizer
from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer
from gnr.customizers.taskcontexmenucustomizer import TaskContextMenuCustomizer
from gnr.customizers.taskdetailsdialogcustomizer import TaskDetailsDialogCustomizer
from gnr.customizers.subtaskdetailsdialogcustomizer import SubtaskDetailsDialogCustomizer
from gnr.customizers.changetaskdialogcustomizer import ChangeTaskDialogCustomizer
from gnr.customizers.statuswindowcustomizer import StatusWindowCustomizer
from gnr.customizers.aboutwindowcustomizer import AboutWindowCustomizer
from gnr.customizers.configurationdialogcustomizer import ConfigurationDialogCustomizer
from gnr.customizers.environmentsdialogcustomizer import EnvironmentsDialogCustomizer
from gnr.customizers.identitydialogcustomizer import IdentityDialogCustomizer
from gnr.customizers.paymentsdialogcustomizer import PaymentsDialogCustomizer

logger = logging.getLogger(__name__)


class GNRMainWindowCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.current_task_highlighted = None
        self.task_details_dialog = None
        self.task_details_dialog_customizer = None
        Customizer.__init__(self, gui, logic)
        self._set_error_label()

    def set_options(self, cfg_desc):
        self.gui.ui.appVer.setText(u"{} - {}".format(cfg_desc.app_name, cfg_desc.app_version))
        self.gui.ui.nodeNameLabel.setText(u"Id: {}".format(cfg_desc.node_name))

    # Add new task to golem client
    def enqueue_new_task(self, ui_new_task_info):
        self.logic.enqueue_new_task(ui_new_task_info)

    # Updates tasks information in gui
    def update_tasks(self, tasks):
        for i in range(self.gui.ui.taskTableWidget.rowCount()):
            task_id = self.gui.ui.taskTableWidget.item(i, 0).text()
            task_id = "{}".format(task_id)
            if task_id in tasks:
                self.gui.ui.taskTableWidget.item(i, 1).setText(tasks[task_id].task_state.status)
                progress_bar_in_box_layout = self.gui.ui.taskTableWidget.cellWidget(i, 2)
                layout = progress_bar_in_box_layout.layout()
                pb = layout.itemAt(0).widget()
                pb.setProperty("value", int(tasks[task_id].task_state.progress * 100.0))
                if self.task_details_dialog_customizer:
                    if self.task_details_dialog_customizer.gnr_task_state.definition.task_id == task_id:
                        self.task_details_dialog_customizer.update_view(tasks[task_id].task_state)

            else:
                assert False, "Update task for unknown task."

    # Add task information in gui
    def add_task(self, task):
        self._add_task(task.definition.task_id, task.status)

    def update_task_additional_info(self, t):
        self.current_task_highlighted = t

    def show_task_result(self, task_id):
        t = self.logic.get_task(task_id)
        if hasattr(t.definition, 'output_file') and os.path.isfile(t.definition.output_file):
            self.show_file(t.definition.output_file)
        elif hasattr(t.definition.options, 'output_file') and os.path.isfile(t.definition.options.output_file):
            self.show_file(t.definition.options.output_file)
        else:
            msg_box = QMessageBox()
            msg_box.setText("No output file defined.")
            msg_box.exec_()

    def remove_task(self, task_id):
        for row in range(0, self.gui.ui.taskTableWidget.rowCount()):
            if self.gui.ui.taskTableWidget.item(row, 0).text() == task_id:
                self.gui.ui.taskTableWidget.removeRow(row)
                return

    def show_new_task_dialog(self, task_id):
        ts = self.logic.get_task(task_id)
        if ts is not None:
            self._show_new_task_dialog(ts.definition)
        else:
            logger.error("Can't get task information for task {}".format(task_id))

    def show_details_dialog(self, task_id):
        ts = self.logic.get_task(task_id)
        self.task_details_dialog = TaskDetailsDialog(self.gui.window)
        self.task_details_dialog_customizer = TaskDetailsDialogCustomizer(self.task_details_dialog, self.logic, ts)
        self.task_details_dialog.show()

    def show_subtask_details_dialog(self, subtask):
        subtask_details_dialog = SubtaskDetailsDialog(self.gui.window)
        SubtaskDetailsDialogCustomizer(subtask_details_dialog, self.logic, subtask)
        subtask_details_dialog.show()

    def show_change_task_dialog(self, task_id):
        change_task_dialog = ChangeTaskDialog(self.gui.window)
        change_task_dialog_customizer = ChangeTaskDialogCustomizer(self.change_task_dialog, self.logic)
        ts = self.logic.get_task(task_id)
        change_task_dialog_customizer.load_task_definition(ts.definition)
        change_task_dialog.show()

    def change_page(self, current, previous):
        if not current:
            current = previous
        self.gui.ui.stackedWidget.setCurrentIndex(self.gui.ui.listWidget.row(current))


    def _setup_connections(self):
        self.gui.ui.listWidget.currentItemChanged.connect(self.change_page)
        self._setup_basic_task_connections()
        self._setup_basic_app_connections()

    def _setup_basic_task_connections(self):
        self.gui.ui.actionNew.triggered.connect(self._show_new_task_dialog_clicked)
        self.gui.ui.actionLoadTask.triggered.connect(self._load_task_button_clicked)
        QtCore.QObject.connect(self.gui.ui.taskTableWidget, QtCore.SIGNAL("cellClicked(int, int)"),
                               self._task_table_row_clicked)
        QtCore.QObject.connect(self.gui.ui.taskTableWidget, QtCore.SIGNAL("doubleClicked(const QModelIndex)"),
                               self._task_table_row_double_clicked)
        self.gui.ui.taskTableWidget.customContextMenuRequested.connect(self._context_menu_requested)

    def _setup_basic_app_connections(self):
        self.gui.ui.actionEdit.triggered.connect(self._show_configuration_dialog_clicked)
        self.gui.ui.actionStatus.triggered.connect(self._show_status_clicked)
        self.gui.ui.actionAbout.triggered.connect(self._show_about_clicked)
        self.gui.ui.actionPayments.triggered.connect(self._show_payments_clicked)
        self.gui.ui.actionEnvironments.triggered.connect(self._show_environments)
        self.gui.ui.actionIdentity.triggered.connect(self._show_identity_dialog)

    def _set_error_label(self):
        palette = QPalette()
        palette.setColor(QPalette.Foreground, QtCore.Qt.red)
        self.gui.ui.errorLabel.setPalette(palette)

    def _show_new_task_dialog(self, definition):
        self._set_new_task_dialog()
        self._set_new_task_dialog_customizer()
        self.new_task_dialog_customizer.load_task_definition(definition)
        self.new_task_dialog.show()

    def _show_new_task_dialog_clicked(self):
        self._set_new_task_dialog()
        self._set_new_task_dialog_customizer()
        self.new_task_dialog.show()

    def _set_new_task_dialog(self):
        self.new_task_dialog = NewTaskDialog(self.gui.window)

    def _set_new_task_dialog_customizer(self):
        self.new_task_dialog_customizer = NewTaskDialogCustomizer(self.new_task_dialog, self.logic)

    def _load_task_button_clicked(self):
        save_path = appdirs.user_data_dir("golem")
        dir_ = ""
        if save_path:
            save_dir = os.path.join(save_path, "save")
            if os.path.isdir(save_dir):
                dir_ = save_dir

        file_name = QFileDialog.getOpenFileName(self.gui.window,
                                                "Choose task file", dir_, "Golem Task (*.gt)")
        if os.path.exists(file_name):
            self._load_task(file_name)

    def _load_task(self, file_path):
        try:
            f = open(file_path, 'r')
            definition = cPickle.loads(f.read())
        except Exception as err:
            definition = None
            logger.error("Can't unpickle the file {}: {}".format(file_path, err))
            QMessageBox().critical(None, "Error", "This is not a proper gt file: {}".format(err))
        finally:
            f.close()

        if definition:
            self._show_new_task_dialog(definition)

    def _add_task(self, task_id, status):
        current_row_count = self.gui.ui.taskTableWidget.rowCount()
        self.gui.ui.taskTableWidget.insertRow(current_row_count)

        task_table_elem = TaskTableElem(task_id, status)

        for col in range(0, 2):
            self.gui.ui.taskTableWidget.setItem(current_row_count, col, task_table_elem.get_column_item(col))

        self.gui.ui.taskTableWidget.setCellWidget(current_row_count, 2, task_table_elem.progressBarInBoxLayoutWidget)

        self.gui.ui.taskTableWidget.setCurrentItem(self.gui.ui.taskTableWidget.item(current_row_count, 1))
        self.update_task_additional_info(self.logic.get_task(task_id))

    def _show_status_clicked(self):
        self.status_window = StatusWindow(self.gui.window)

        self.status_window_customizer = StatusWindowCustomizer(self.status_window, self.logic)
        self.status_window_customizer.get_status()
        self.status_window.show()

    def _show_about_clicked(self):
        about_window = AboutWindow(self.gui.window)
        AboutWindowCustomizer(about_window, self.logic)
        about_window.show()

    def _show_payments_clicked(self):
        payments_window = PaymentsDialog(self.gui.window)
        PaymentsDialogCustomizer(payments_window, self.logic)
        payments_window.show()

    def _show_configuration_dialog_clicked(self):
        self.configuration_dialog = ConfigurationDialog(self.gui.window)
        self.configuration_dialog_customizer = ConfigurationDialogCustomizer(self.configuration_dialog, self.logic)
        self.configuration_dialog.show()

    def _show_identity_dialog(self):
        identity_dialog = IdentityDialog(self.gui.window)
        identity_dialog_customizer = IdentityDialogCustomizer(identity_dialog, self.logic)
        identity_dialog.show()

    def _show_environments(self):
        self.environments_dialog = EnvironmentsDialog(self.gui.window)

        self.environments_dialog_customizer = EnvironmentsDialogCustomizer(self.environments_dialog, self.logic)
        self.environments_dialog.show()

    def _context_menu_requested(self, p):
        self.__show_task_context_menu(p)

    def _task_table_row_clicked(self, row, col):
        if row < self.gui.ui.taskTableWidget.rowCount():
            task_id = self.gui.ui.taskTableWidget.item(row, 0).text()
            task_id = "{}".format(task_id)
            t = self.logic.get_task(task_id)
            self.update_task_additional_info(t)

    def _task_table_row_double_clicked(self, m):
        row = m.row()
        task_id = "{}".format(self.gui.ui.taskTableWidget.item(row, 0).text())
        self.show_details_dialog(task_id)

    def __show_task_context_menu(self, p):

        if self.gui.ui.taskTableWidget.itemAt(p) is None:
            return
        row = self.gui.ui.taskTableWidget.itemAt(p).row()

        id_item = self.gui.ui.taskTableWidget.item(row, 0)
        task_id = "{}".format(id_item.text())
        gnr_task_state = self.logic.get_task(task_id)

        menu = QMenu()
        self.taskContextMenuCustomizer = TaskContextMenuCustomizer(menu, self.logic, gnr_task_state)
        menu.popup(self.gui.ui.taskTableWidget.viewport().mapToGlobal(p))
        menu.exec_()
