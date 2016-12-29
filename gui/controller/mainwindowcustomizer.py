from __future__ import division
import datetime
import jsonpickle as json
import logging
import os
import time
from threading import Lock

from ethereum.utils import denoms
from PyQt4.QtCore import QObject, SIGNAL, Qt, QTimer
from PyQt4.QtGui import QFileDialog, QIcon, QPalette, QPixmap, QTreeWidgetItem, QMenu, QMessageBox
from twisted.internet.defer import inlineCallbacks

from golem.core.variables import APP_NAME, APP_VERSION
from golem.task.taskstate import TaskStatus

from apps.core.gui.controller.newtaskdialogcustomizer import NewTaskDialogCustomizer
from apps.core.task.gnrtaskstate import TaskDesc
from apps.rendering.gui.controller.renderingnewtaskdialogcustomizer import RenderingNewTaskDialogCustomizer

from gui.controller.customizer import Customizer
from gui.controller.common import get_save_dir
from gui.controller.nodenamedialogcustomizer import NodeNameDialogCustomizer
from gui.controller.taskcontexmenucustomizer import TaskContextMenuCustomizer
from gui.controller.taskdetailsdialogcustomizer import TaskDetailsDialogCustomizer
from gui.controller.subtaskdetailsdialogcustomizer import SubtaskDetailsDialogCustomizer
from gui.controller.changetaskdialogcustomizer import ChangeTaskDialogCustomizer
from gui.controller.configurationdialogcustomizer import ConfigurationDialogCustomizer
from gui.controller.environmentsdialogcustomizer import EnvironmentsDialogCustomizer
from gui.controller.identitydialogcustomizer import IdentityDialogCustomizer
from gui.controller.memoryhelper import resource_size_to_display, translate_resource_index
from gui.controller.paymentsdialogcustomizer import PaymentsDialogCustomizer
from gui.controller.previewcontroller import PreviewController
from gui.controller.showtaskresourcesdialogcustomizer import ShowTaskResourcesDialogCustomizer
from gui.guidirmanager import get_icons_list
from gui.view.dialog import PaymentsDialog, TaskDetailsDialog, SubtaskDetailsDialog, ChangeTaskDialog, \
    EnvironmentsDialog, IdentityDialog, NodeNameDialog, ShowTaskResourcesDialog
from gui.view.tasktableelem import TaskTableElem, ItemMap

logger = logging.getLogger("gui")


def insert_item(root, path_table):
    assert isinstance(root, QTreeWidgetItem)

    if len(path_table) > 0:
        for i in range(root.childCount()):
            if path_table[0] == "{}".format(root.child(i).text(0)):
                insert_item(root.child(i), path_table[1:])
                return

        new_child = QTreeWidgetItem([path_table[0]])
        root.addChild(new_child)
        insert_item(new_child, path_table[1:])


class MainWindowCustomizer(Customizer):
    def __init__(self, gui, logic):
        Customizer.__init__(self, gui, logic)

        self.current_task_highlighted = None
        self.preview_controller = PreviewController(self.gui, self.logic, self)

        self.task_details_dialog = None
        self.task_details_dialog_customizer = None
        self.new_task_dialog_customizer = None
        self.configuration_dialog_customizer = None
        self.change_task_dialog = None
        self.show_task_resources_dialog = None
        self.show_task_resources_dialog_customizer = None
        self._set_icons()
        self._set_error_label()
        self.gui.ui.listWidget.setCurrentItem(self.gui.ui.listWidget.item(1))
        self.lock = Lock()
        self.timer = QTimer()
        self.timer.start(1000)
        self.timer.timeout.connect(self.update_time)

    def init_config(self):
        self.configuration_dialog_customizer = ConfigurationDialogCustomizer(self.gui, self.logic)
        self._set_new_task_dialog_customizer()

    def set_options(self, cfg_desc, id_, eth_address, description):
        # Footer options
        self.gui.ui.appVer.setText(u"{} ({})".format(APP_NAME, APP_VERSION))

        # Account options
        self.gui.ui.golemIdLabel.setText(u"{}".format(id_))
        self.gui.ui.golemIdLabel.setCursorPosition(0)
        self.gui.ui.ethAddressLabel.setText(u"{}".format(eth_address))
        self.gui.ui.descriptionTextEdit.clear()
        self.gui.ui.descriptionTextEdit.appendPlainText(u"{}".format(description))

        self.set_name(cfg_desc.node_name)

    def set_name(self, node_name):
        # Status options
        self.gui.ui.nodeNameLabel.setText(u"{}".format(node_name))
        self.gui.ui.nameLabel.setText(u"{}".format(node_name))
        self.gui.ui.nodeNameLineEdit.setText(u"{}".format(node_name))

    # Add new task to golem client
    def enqueue_new_task(self, ui_new_task_info):
        self.logic.enqueue_new_task(ui_new_task_info)

    # Updates tasks information in gui
    def update_tasks(self, tasks):
        for i in range(self.gui.ui.taskTableWidget.rowCount()):
            task_id = u"{}".format(self.gui.ui.taskTableWidget.item(i, ItemMap.Id).text())
            task = tasks.get(task_id)
            if task:
                self.gui.ui.taskTableWidget.item(i, ItemMap.Status).setText(task.task_state.status)
                progress_bar_in_box_layout = self.gui.ui.taskTableWidget.cellWidget(i, ItemMap.Progress)
                layout = progress_bar_in_box_layout.layout()
                pb = layout.itemAt(0).widget()
                pb.setProperty("value", int(task.task_state.progress * 100.0))
                if self.task_details_dialog_customizer:
                    if self.task_details_dialog_customizer.gnr_task_state.definition.task_id == task_id:
                        self.task_details_dialog_customizer.update_view(task.task_state)
                if task.task_state.status not in [TaskStatus.starting, TaskStatus.notStarted]:
                    self.__update_payment(task_id, i)
            else:
                assert False, "Update task for unknown task."

    @inlineCallbacks
    def __update_payment(self, task_id, i):
        price = yield self.logic.get_cost_for_task_id(task_id)
        if price:
            self.gui.ui.taskTableWidget.item(i, ItemMap.Cost).setText("{0:.6f}".format(price / denoms.ether))

    def update_time(self):
        with self.lock:
            for i in range(self.gui.ui.taskTableWidget.rowCount()):
                status = self.gui.ui.taskTableWidget.item(i, ItemMap.Status).text()
                if status in [TaskStatus.computing, TaskStatus.waiting]:
                    l = self.gui.ui.taskTableWidget.item(i, ItemMap.Time).text().split(':')
                    time_ = int(l[0]) * 3600 + int(l[1]) * 60 + int(l[2]) + 1
                    m, s = divmod(time_, 60)
                    h, m = divmod(m, 60)
                    self.gui.ui.taskTableWidget.item(i, ItemMap.Time).setText(
                        ("%02d:%02d:%02d" % (h, m, s)))

    # Add task information in gui
    def add_task(self, task):
        self._add_task(task.definition.task_id, task.status, task.definition.task_name)

    def update_task_additional_info(self, t):
        assert isinstance(t, TaskDesc)

        self.current_task_highlighted = t
        self.gui.ui.startTaskButton.setEnabled(t.task_state.status == TaskStatus.notStarted)

        self.__set_time_params(t)
        self.__set_memory_params(t)

        self.preview_controller.set_preview(t)

    def show_task_result(self, task_id):
        t = self.logic.get_task(task_id)
        num = self.gui.ui.previewsSlider.value() - 1
        if t.has_multiple_outputs(num + 1):
            file_ = t.task_state.outputs[num]
        else:
            file_ = t.definition.output_file
        if os.path.isfile(file_):
            self.show_file(file_)
        else:
            self.show_error_window(u"{} is not a file".format(file_))

    def remove_task(self, task_id):
        for row in range(0, self.gui.ui.taskTableWidget.rowCount()):
            if self.gui.ui.taskTableWidget.item(row, ItemMap.Id).text() == task_id:
                self.gui.ui.taskTableWidget.removeRow(row)
                return

    def clone_task(self, task_id):
        ts = self.logic.get_task(task_id)
        if ts is not None:
            self._load_new_task_from_definition(ts.definition)
            self.gui.ui.listWidget.setCurrentItem(self.gui.ui.listWidget.item(0))
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
        self.change_task_dialog = ChangeTaskDialog(self.gui.window)
        change_task_dialog_customizer = ChangeTaskDialogCustomizer(self.change_task_dialog, self.logic)
        ts = self.logic.get_task(task_id)
        change_task_dialog_customizer.load_task_definition(ts.definition)
        self.change_task_dialog.show()

    def change_page(self, current, previous):
        if not current:
            current = previous
        self.gui.ui.stackedWidget.setCurrentIndex(self.gui.ui.listWidget.row(current))

    def prompt_node_name(self, node_name):
        node_name_dialog = NodeNameDialog(self.gui.window)
        NodeNameDialogCustomizer(node_name_dialog, self.logic, node_name)
        node_name_dialog.show()

    def _setup_connections(self):
        self._setup_task_connections()
        self._setup_app_connections()

    def _setup_task_connections(self):
        self.gui.ui.loadButton.clicked.connect(self._load_task_button_clicked)
        selection_model = self.gui.ui.taskTableWidget.selectionModel()
        selection_model.selectionChanged.connect(self._task_table_item_changed)
        self.gui.ui.taskTableWidget.cellClicked.connect(self._task_table_row_clicked)
        self.gui.ui.taskTableWidget.doubleClicked.connect(self._task_table_row_double_clicked)
        self.gui.ui.taskTableWidget.customContextMenuRequested.connect(self._context_menu_requested)
        self.gui.ui.startTaskButton.clicked.connect(self._start_task_button_clicked)
        QObject.connect(self.gui.ui.outputFile, SIGNAL("mouseReleaseEvent(int, int, QMouseEvent)"),
                        self.__open_output_file)
        self.gui.ui.showResourceButton.clicked.connect(self._show_task_resource_clicked)

    def _setup_app_connections(self):
        self.gui.ui.listWidget.currentItemChanged.connect(self.change_page)
        self.gui.ui.paymentsButton.clicked.connect(self._show_payments_clicked)
        self.gui.ui.environmentsButton.clicked.connect(self._show_environments)
        self.gui.ui.identityButton.clicked.connect(self._show_identity_dialog)
        self.gui.ui.editDescriptionButton.clicked.connect(self._edit_description)
        self.gui.ui.saveDescriptionButton.clicked.connect(self._save_description)

    def _set_error_label(self):
        palette = QPalette()
        palette.setColor(QPalette.Foreground, Qt.red)
        self.gui.ui.errorLabel.setPalette(palette)

    def _load_new_task_from_definition(self, definition):
        self.new_task_dialog_customizer.load_task_definition(definition)

    def _set_new_task_dialog_customizer(self):
        # FIXME Remove RenderingNewTaskDialogCustomizer
        self.new_task_dialog_customizer = RenderingNewTaskDialogCustomizer(self.gui, self.logic)

    def _load_task_button_clicked(self):
        save_dir = get_save_dir()
        file_name = QFileDialog.getOpenFileName(self.gui.window,
                                                "Choose task file", save_dir,
                                                "Golem Task (*.gt)")
        if os.path.exists(file_name):
            self._load_task(file_name)

    def _load_task(self, file_path):
        try:
            f = open(file_path, 'r')
            definition = json.loads(f.read())
        except Exception as err:
            definition = None
            logger.error("Can't loads the file {}: {}".format(file_path, err))
            QMessageBox().critical(None, "Error", "This is not a proper gt file: {}".format(err))
        finally:
            f.close()

        if definition:
            self._load_new_task_from_definition(definition)

    def _start_task_button_clicked(self):
        if self.current_task_highlighted is None:
            return
        self.gui.ui.startTaskButton.setEnabled(False)
        self.logic.start_task(self.current_task_highlighted.definition.task_id)

    def _add_task(self, task_id, status, task_name):
        current_row_count = self.gui.ui.taskTableWidget.rowCount()
        self.gui.ui.taskTableWidget.insertRow(current_row_count)

        task_table_elem = TaskTableElem(task_id, status, task_name)
        for col in range(ItemMap.count()):
            if col != ItemMap.Progress:
                self.gui.ui.taskTableWidget.setItem(
                    current_row_count, col, task_table_elem.get_column_item(col))

        self.gui.ui.taskTableWidget.setCellWidget(
            current_row_count, ItemMap.Progress, task_table_elem.progressBarInBoxLayoutWidget)

        self.gui.ui.taskTableWidget.setCurrentItem(self.gui.ui.taskTableWidget.item(current_row_count, ItemMap.Status))
        self.update_task_additional_info(self.logic.get_task(task_id))

    def _show_payments_clicked(self):
        payments_window = PaymentsDialog(self.gui.window)
        PaymentsDialogCustomizer(payments_window, self.logic)
        payments_window.show()

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

    def _task_table_row_clicked(self, row, *_):
        if row < self.gui.ui.taskTableWidget.rowCount():
            task_id = self.gui.ui.taskTableWidget.item(row, ItemMap.Id).text()
            task_id = "{}".format(task_id)
            t = self.logic.get_task(task_id)
            self.update_task_additional_info(t)

    def _task_table_item_changed(self):
        try:
            index = self.gui.ui.taskTableWidget.selectedIndexes()[0]
        except IndexError:
            return
        if index:
            self._task_table_row_clicked(index.row(), 0)

    def _task_table_row_double_clicked(self, m):
        row = m.row()
        task_id = "{}".format(self.gui.ui.taskTableWidget.item(row, ItemMap.Id).text())
        self.show_details_dialog(task_id)

    def _edit_description(self):
        self.gui.ui.editDescriptionButton.setEnabled(False)
        self.gui.ui.saveDescriptionButton.setEnabled(True)
        self.gui.ui.descriptionTextEdit.setEnabled(True)

    def _save_description(self):
        self.gui.ui.editDescriptionButton.setEnabled(True)
        self.gui.ui.saveDescriptionButton.setEnabled(False)
        self.gui.ui.descriptionTextEdit.setEnabled(False)
        self.logic.change_description(u"{}".format(self.gui.ui.descriptionTextEdit.toPlainText()))

    def _set_icons(self):
        icons = get_icons_list()
        for i, icon_path in enumerate(icons):
            item = self.gui.ui.listWidget.item(i)
            icon = QIcon()
            icon.addPixmap(QPixmap(icon_path), QIcon.Normal, QIcon.Off)
            item.setIcon(icon)

    def _set_show_task_resource_dialog(self):
        self.show_task_resources_dialog = ShowTaskResourcesDialog(self.gui.window)
        self.show_task_resources_dialog_customizer = ShowTaskResourcesDialogCustomizer(self.show_task_resources_dialog,
                                                                                       self)

    def _show_task_resource_clicked(self):

        if self.current_task_highlighted:
            res = [os.path.abspath(r) for r in self.current_task_highlighted.definition.resources]
            res.sort()
            self._set_show_task_resource_dialog()

            item = QTreeWidgetItem(["Resources"])
            self.show_task_resources_dialog.ui.folderTreeView.insertTopLevelItem(0, item)
            self.show_task_resources_dialog.ui.closeButton.clicked.connect(self.__show_task_res_close_button_clicked)

            for r in res:
                after_split = r.split("\\")
                insert_item(item, after_split)

            self.show_task_resources_dialog.ui.mainSceneFileLabel.setText(
                self.current_task_highlighted.definition.main_scene_file)
            self.show_task_resources_dialog.ui.folderTreeView.expandAll()

            self.show_task_resources_dialog.show()

    def __show_task_context_menu(self, p):

        if self.gui.ui.taskTableWidget.itemAt(p) is None:
            return
        row = self.gui.ui.taskTableWidget.itemAt(p).row()

        id_item = self.gui.ui.taskTableWidget.item(row, ItemMap.Id)
        task_id = "{}".format(id_item.text())
        gnr_task_state = self.logic.get_task(task_id)

        menu = QMenu()
        self.taskContextMenuCustomizer = TaskContextMenuCustomizer(menu, self.logic, gnr_task_state)
        menu.popup(self.gui.ui.taskTableWidget.viewport().mapToGlobal(p))
        menu.exec_()

    def __show_task_res_close_button_clicked(self):
        self.show_task_resources_dialog.window.close()

    def __open_output_file(self):
        file_ = self.gui.ui.outputFile.text()
        if os.path.isfile(file_):
            self.show_file(file_)

    def __set_time_params(self, t):
        self.gui.ui.subtaskTimeout.setText("{} minutes".format(int(t.definition.subtask_timeout / 60.0)))
        self.gui.ui.fullTaskTimeout.setText(str(datetime.timedelta(seconds=t.definition.full_task_timeout)))
        if t.task_state.time_started != 0.0:
            lt = time.localtime(t.task_state.time_started)
            time_string = time.strftime("%Y.%m.%d  %H:%M:%S", lt)
            self.gui.ui.timeStarted.setText(time_string)

    def __set_memory_params(self, t):
        mem, index = resource_size_to_display(t.definition.estimated_memory / 1024)
        self.gui.ui.estimatedMemoryLabel.setText("{} {}".format(mem, translate_resource_index(index)))

