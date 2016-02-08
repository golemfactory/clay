import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from gnr.ui.dialog import AddTaskResourcesDialog
from gnr.customizers.addresourcesdialogcustomizer import AddResourcesDialogCustomizer
from gnr.renderingtaskstate import RenderingTaskState
from gnr.gnrtaskstate import GNRTaskDefinition
from golem.task.taskstate import TaskStatus
from gnr.customizers.timehelper import set_time_spin_boxes, get_time_values
from gnr.customizers.customizer import Customizer

import logging

logger = logging.getLogger(__name__)


class NewTaskDialogCustomizer(Customizer):
    def __init__(self, gui, logic):
        self.options = None
        self.add_task_resource_dialog = None
        self.task_state = None
        self.add_task_resource_dialog_customizer = None

        Customizer.__init__(self, gui, logic)
        self.add_task_resource_dialog = self._get_add_resource_dialog()
        self.add_task_resource_dialog_customizer = AddResourcesDialogCustomizer(self.add_task_resource_dialog,
                                                                                logic)

    def load_data(self):
        self._set_uid()
        self._init()

    def _setup_connections(self):
        self._setup_task_type_connections()
        self._setup_basic_new_task_connections()
        self._setup_advance_new_task_connections()
        self._setup_options_connections()

    def _setup_task_type_connections(self):
        QtCore.QObject.connect(self.gui.ui.taskTypeComboBox, QtCore.SIGNAL("currentIndexChanged(const QString)"),
                               self._task_type_value_changed)

    def _setup_basic_new_task_connections(self):
        self.gui.ui.saveButton.clicked.connect(self._save_task_button_clicked)
        self.gui.ui.chooseMainProgramFileButton.clicked.connect(self._choose_main_program_file_button_clicked)
        self.gui.ui.addResourceButton.clicked.connect(self._show_add_resource_dialog)
        self.gui.ui.finishButton.clicked.connect(self._finish_button_clicked)
        self.gui.ui.cancelButton.clicked.connect(self._cancel_button_clicked)

    def _setup_advance_new_task_connections(self):
        QtCore.QObject.connect(self.gui.ui.optimizeTotalCheckBox, QtCore.SIGNAL("stateChanged(int) "),
                               self._optimize_total_check_box_changed)

    def _setup_options_connections(self):
        self.gui.ui.optionsButton.clicked.connect(self._open_options)

    def _set_uid(self):
        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())

    def _init(self):
        self._set_uid()

        task_types = self.logic.get_task_types()
        for t in task_types.values():
            self.gui.ui.taskTypeComboBox.addItem(t.name)

    def _choose_main_program_file_button_clicked(self):

        dir_ = os.path.dirname(u"{}".format(self.gui.ui.mainProgramFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                                             "Choose main program file", dir_, "Python (*.py)"))

        if file_name != "":
            self.gui.ui.mainProgramFileLineEdit.setText(file_name)

    def _show_add_resource_dialog(self):
        if not self.add_task_resource_dialog:
            self.add_task_resource_dialog = self._get_add_resource_dialog()
            self.add_task_resource_dialog_customizer = AddResourcesDialogCustomizer(self.add_task_resource_dialog,
                                                                                    self.logic)

        self.add_task_resource_dialog.show()

    def _save_task_button_clicked(self):
        file_name = QFileDialog.getSaveFileName(self.gui.window,
                                                "Choose save file", "", "Golem Task (*.gt)")

        if file_name != "":
            self._save_task(file_name)

    def _save_task(self, file_path):
        definition = self._query_task_definition()
        self.logic.save_task(definition, file_path)

    def load_task_definition(self, task_definition):
        assert isinstance(task_definition, GNRTaskDefinition)

        definition = deepcopy(task_definition)

        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())
        self._load_basic_task_params(definition)
        self._load_advance_task_params(definition)
        self._load_resources(definition)

    def set_options(self, options):
        self.options = options

    def _load_resources(self, definition):
        self.add_task_resource_dialog = self._get_add_resource_dialog()
        self.add_task_resource_dialog_customizer = AddResourcesDialogCustomizer(self.add_task_resource_dialog, self.logic)
        self.add_task_resource_dialog_customizer.resources = definition.resources

        model = self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.model()

        common_prefix = os.path.commonprefix(definition.resources)
        self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.setExpanded(model.index(common_prefix), True)

        for res in definition.resources:
            path_head, path_tail = os.path.split(res)
            while path_head != '' and path_tail != '':
                self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.setExpanded(model.index(path_head), True)
                path_head, path_tail = os.path.split(path_head)

        # TODO
        self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        # for res in definition.resources:
        #     model.setData(model.index(res), QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)

    def _load_basic_task_params(self, definition):
        self._load_task_type(definition)
        set_time_spin_boxes(self.gui, definition.full_task_timeout, definition.subtask_timeout,
                         definition.min_subtask_time)
        self.gui.ui.mainProgramFileLineEdit.setText(definition.main_program_file)
        self.gui.ui.totalSpinBox.setValue(definition.total_subtasks)

        if os.path.normpath(definition.main_program_file) in definition.resources:
            definition.resources.remove(os.path.normpath(definition.main_program_file))

        self._load_options(definition)

    def _load_options(self, definition):
        self.options = deepcopy(definition.options)

    def _load_task_type(self, definition):
        try:
            task_type_item = self.gui.ui.taskTypeComboBox.findText(definition.task_type)
            if task_type_item >= 0:
                self.gui.ui.taskTypeComboBox.setCurrentIndex(task_type_item)
            else:
                logger.error("Cannot load task, unknown task type")
                return
        except Exception as err:
            logger.error("Wrong task type {}".format(err))
            return

    def _load_advance_task_params(self, definition):
        self.gui.ui.totalSpinBox.setEnabled(not definition.optimize_total)
        self.gui.ui.optimizeTotalCheckBox.setChecked(definition.optimize_total)

    def _finish_button_clicked(self):
        self.task_state = RenderingTaskState()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._query_task_definition()
        self._add_current_task()

    def _add_current_task(self):
        self.logic.add_tasks([self.task_state])
        self.gui.window.close()

    def _cancel_button_clicked(self):
        self.gui.window.close()

    @staticmethod
    def _generate_new_task_uid():
        import uuid
        return "{}".format(uuid.uuid4())

    def _query_task_definition(self):
        definition = GNRTaskDefinition()
        definition = self._read_basic_task_params(definition)
        definition = self._read_task_type(definition)
        definition.options = self.options
        return definition

    def _read_basic_task_params(self, definition):
        definition.task_id = u"{}".format(self.gui.ui.taskIdLabel.text())
        definition.full_task_timeout, definition.subtask_timeout, definition.min_subtask_time = get_time_values(self.gui)
        definition.main_program_file = u"{}".format(self.gui.ui.mainProgramFileLineEdit.text())
        definition.optimize_total = self.gui.ui.optimizeTotalCheckBox.isChecked()
        if definition.optimize_total:
            definition.total_subtasks = 0
        else:
            definition.total_subtasks = self.gui.ui.totalSpinBox.value()

        if self.add_task_resource_dialog_customizer is not None:
            definition.resources = self.add_task_resource_dialog_customizer.resources
        else:
            definition.resources = set()

        definition.resources.add(os.path.normpath(definition.main_program_file))

        return definition

    def _read_task_type(self, definition):
        definition.task_type = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        return definition

    def _optimize_total_check_box_changed(self):
        self.gui.ui.totalSpinBox.setEnabled(not self.gui.ui.optimizeTotalCheckBox.isChecked())

    def _open_options(self):
        task_name = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        task = self.logic.get_task_type(task_name)
        dialog = task.dialog
        dialog_customizer = task.dialog_customizer
        if dialog is not None and dialog_customizer is not None:
            task_dialog = dialog(self.gui.window)
            dialog_customizer(task_dialog, self.logic, self)
            task_dialog.show()
        else:
            self.gui.ui.optionsButton.setEnabled(False)

    def _task_type_value_changed(self, name):
        task_name = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        task = self.logic.get_task_type(task_name)
        self.gui.ui.optionsButton.setEnabled(task.dialog is not None and task.dialog_customizer is not None)
        self.options = deepcopy(task.options)

    def _get_add_resource_dialog(self):
        return AddTaskResourcesDialog(self.gui.window)