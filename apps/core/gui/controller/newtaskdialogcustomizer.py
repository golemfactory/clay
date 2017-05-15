from __future__ import division
import logging
import os
import time

from copy import deepcopy

from ethereum.utils import denoms
from PyQt5.QtWidgets import QFileDialog
from twisted.internet.defer import inlineCallbacks

from golem.task.taskstate import TaskStatus

from apps.core.gui.controller.addresourcesdialogcustomizer import AddResourcesDialogCustomizer
from apps.core.gui.verificationparamshelper import (
    load_verification_params, set_verification_widgets_state,
    verification_random_changed, read_advanced_verification_params)
from apps.core.task.coretaskstate import TaskDefinition, TaskDesc

from gui.controller.timehelper import set_time_spin_boxes, get_time_values, get_subtask_hours
from gui.controller.customizer import Customizer
from gui.controller.common import get_save_dir
from gui.view.dialog import AddTaskResourcesDialog

logger = logging.getLogger("apps.core")


class NewTaskDialogCustomizer(Customizer):

    SHOW_ADVANCE_BUTTON_MESSAGE = ["Show advanced settings", "Hide advanced settings"]

    def __init__(self, gui, logic):
        self.add_task_resource_dialog = None
        self.task_state = None
        self.add_task_resource_dialog_customizer = None
        self.task_customizer = None  # Controller for task specific options

        Customizer.__init__(self, gui, logic)
        self.add_task_resource_dialog = self._get_add_resource_dialog()
        self.add_task_resource_dialog_customizer = \
            AddResourcesDialogCustomizer(self.add_task_resource_dialog, logic)

    def load_data(self):
        self._set_uid()
        self.gui.ui.advanceNewTaskWidget.hide()
        self.gui.ui.showAdvanceNewTaskButton.setText(self.SHOW_ADVANCE_BUTTON_MESSAGE[0])
        self._init()

    def _setup_connections(self):
        self._setup_task_type_connections()
        self._setup_basic_new_task_connections()
        self._setup_advance_new_task_connections()
        self._setup_payment_connections()
        self._setup_verification_connections()

    def _setup_task_type_connections(self):
        self.gui.ui.taskTypeComboBox.currentIndexChanged[str].connect(self._task_type_value_changed)

    def _setup_basic_new_task_connections(self):
        self.gui.ui.saveButton.clicked.connect(self._save_task_button_clicked)
        self.gui.ui.addResourceButton.clicked.connect(
            self._show_add_resource_dialog)
        self.gui.ui.finishButton.clicked.connect(self._finish_button_clicked)
        self.gui.ui.savePresetButton.clicked.connect(
            self._save_preset_button_clicked)

    def _setup_advance_new_task_connections(self):
        self.gui.ui.showAdvanceNewTaskButton.clicked.connect(
            self._advance_settings_button_clicked)
        self.gui.ui.optimizeTotalCheckBox.stateChanged.connect(
            self._optimize_total_check_box_changed)
        self.gui.ui.subtaskTimeoutHourSpinBox.valueChanged.connect(
            self._set_new_pessimistic_cost)
        self.gui.ui.subtaskTimeoutMinSpinBox.valueChanged.connect(
            self._set_new_pessimistic_cost)
        self.gui.ui.subtaskTimeoutSecSpinBox.valueChanged.connect(
            self._set_new_pessimistic_cost)
        self.gui.ui.totalSpinBox.valueChanged.connect(
            self._set_new_pessimistic_cost)
        self.gui.ui.testTaskButton.clicked.connect(
            self.__test_task_button_clicked)
        self.gui.ui.resetToDefaultButton.clicked.connect(
            self.__reset_to_defaults)

    def _setup_payment_connections(self):
        self.gui.ui.taskMaxPriceLineEdit.textChanged.connect(
            self._set_new_pessimistic_cost)

    def _set_uid(self):
        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())

    # FIXME Remove verification connections
    def _setup_verification_connections(self):
        self.gui.ui.verificationRandomRadioButton.toggled.connect(
            self.__verification_random_changed)
        self.gui.ui.advanceVerificationCheckBox.stateChanged.connect(
            self.__advanced_verification_changed)

    def _init(self):
        self._set_uid()
        self._set_max_price()

        self.gui.ui.resourceFilesLabel.setText("0")
        task_types = self.logic.get_task_types()
        for t in task_types.values():
            self.gui.ui.taskTypeComboBox.addItem(t.name)

        default_task = self.logic.get_default_task_type()
        self.logic.options = default_task.options()
        task_item = self.gui.ui.taskTypeComboBox.findText(default_task.name)
        if task_item >= 0:
            self.gui.ui.taskTypeComboBox.setCurrentIndex(task_item)
        else:
            logger.error("Cannot load task, wrong task type {}".format(default_task.name))
        self._set_name()

        self._task_type_value_changed(default_task.name)

        self.gui.ui.totalSpinBox.setRange(default_task.defaults.min_subtasks,
                                          default_task.defaults.max_subtasks)
        self.gui.ui.totalSpinBox.setValue(
            default_task.defaults.default_subtasks)

    def _set_name(self):
        self.gui.ui.taskNameLineEdit.setText(self._generate_name(self.gui.ui.taskTypeComboBox.currentText()))

    def _generate_name(self, task_type):
        return u"{}_{}".format(task_type, time.strftime("%H:%M:%S_%Y-%m-%d"))

    @inlineCallbacks
    def _set_max_price(self):
        max_price = yield self.logic.get_max_price()
        max_price = max_price / denoms.ether
        self.gui.ui.taskMaxPriceLineEdit.setText(u"{:.6f}".format(max_price))
        self._set_new_pessimistic_cost()

    def _show_add_resource_dialog(self):
        if not self.add_task_resource_dialog:
            self.add_task_resource_dialog = self._get_add_resource_dialog()
            self.add_task_resource_dialog_customizer = AddResourcesDialogCustomizer(self.add_task_resource_dialog,
                                                                                    self.logic)

        self.add_task_resource_dialog.show()
        self._change_finish_state(False)

    def _save_task_button_clicked(self):
        save_dir = get_save_dir()
        file_name, _ = QFileDialog.getSaveFileName(self.gui.window,
                                                   "Choose save file", save_dir, "Golem Task (*.gt)")

        if file_name:
            self._save_task(file_name)

    def _save_task(self, file_path):
        definition = self._query_task_definition()
        self.logic.save_task(definition, file_path)

    def _save_preset_button_clicked(self):
        definition = self._query_task_definition()
        self.logic.save_task_preset(definition)

    def load_task_definition(self, task_definition):
        if not isinstance(task_definition, TaskDefinition):
            raise TypeError(
                "Incorrect task definition type: {}. "
                "Should be TaskDefinition".format(type(task_definition)))

        definition = deepcopy(task_definition)
        self.logic.options = deepcopy(definition.options)
        definition.resources = {os.path.normpath(res)
                                for res in definition.resources}
        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())
        self._load_basic_task_params(definition)
        self.task_customizer.load_task_definition(definition)
        self._load_advance_task_params(definition)
        self._load_resources(definition)
        load_verification_params(self.gui, definition)  # FIXME
        self._load_payment_params(definition)

    def set_options(self, options):
        self.logic.options = options

    def task_settings_changed(self):
        self._change_finish_state(False)

    def test_task_computation_finished(self, success, est_mem):
        if success:
            self.task_state.definition.estimated_memory = est_mem
            self._change_finish_state(True)

    def get_task_specific_options(self, definition):
        self.task_customizer.get_task_specific_options(definition)

    def _load_resources(self, definition):
        definition.remove_from_resources()
        self.add_task_resource_dialog = self._get_add_resource_dialog()
        self.add_task_resource_dialog_customizer = \
            AddResourcesDialogCustomizer(self.add_task_resource_dialog,
                                         self.logic)
        self.add_task_resource_dialog_customizer.resources = \
            definition.resources

        model = self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.model()

        common_prefix = os.path.commonprefix(definition.resources)
        self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.setExpanded(model.index(common_prefix), True)

        for res in definition.resources:
            path_head, path_tail = os.path.split(res)
            while path_head != '' and path_tail != '':
                self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.setExpanded(model.index(path_head), True)
                path_head, path_tail = os.path.split(path_head)

        # TODO Better model management would be nice
        self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        self.gui.ui.resourceFilesLabel.setText(u"{}".format(len(self.add_task_resource_dialog_customizer.resources)))

    def _load_basic_task_params(self, definition):
        self._load_task_type(definition)
        set_time_spin_boxes(self.gui, definition.full_task_timeout,
                            definition.subtask_timeout)
        self.gui.ui.totalSpinBox.setValue(definition.total_subtasks)
        task_type = self.logic.get_task_type(definition.task_type)
        self.gui.ui.totalSpinBox.setRange(task_type.defaults.min_subtasks,
                                          task_type.defaults.max_subtasks)
        if definition.task_name:
            self.gui.ui.taskNameLineEdit.setText(definition.task_name)
        else:
            self._set_name()

        self._load_options(definition)

    def _load_options(self, definition):
        self.logic.options = deepcopy(definition.options)

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

    def _load_payment_params(self, definition):
        price = int(definition.max_price) / denoms.ether
        self.gui.ui.taskMaxPriceLineEdit.setText(u"{}".format(price))
        self._set_new_pessimistic_cost()

    def _finish_button_clicked(self):
        self.task_state = TaskDesc()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._query_task_definition()
        self._add_current_task()
        self.load_task_definition(self.task_state.definition)

    def _add_current_task(self):
        self.logic.add_tasks([deepcopy(self.task_state)])

    @staticmethod
    def _generate_new_task_uid():
        import uuid
        return "{}".format(uuid.uuid4())

    def get_current_task_type(self):
        task_name = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        return self.logic.get_task_type(task_name)

    def _query_task_definition(self):
        task_type = self.get_current_task_type()
        definition = task_type.definition()
        self._read_task_type(definition)
        self._read_basic_task_params(definition)
        self._read_price_params(definition)
        self._read_task_name(definition)
        self.get_task_specific_options(definition)
        self.logic.options = definition.options
        self._read_resource_params(definition)
        self._read_advanced_verification_params(definition)  # FIMXE

        return definition

    def _read_basic_task_params(self, definition):
        definition.task_id = u"{}".format(self.gui.ui.taskIdLabel.text())
        definition.full_task_timeout, definition.subtask_timeout = get_time_values(self.gui)
        task_type = self.logic.get_task_type(definition.task_type)
        definition.main_program_file = task_type.defaults.main_program_file
        definition.optimize_total = self.gui.ui.optimizeTotalCheckBox.isChecked()
        if definition.optimize_total:
            definition.total_subtasks = 0
        else:
            definition.total_subtasks = self.gui.ui.totalSpinBox.value()

        if self.add_task_resource_dialog_customizer is not None:
            definition.resources = self.add_task_resource_dialog_customizer.resources
        else:
            definition.resources = set()

    def _read_task_type(self, definition):
        definition.task_type = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())

    def _read_task_name(self, definition):
        definition.task_name = u"{}".format(self.gui.ui.taskNameLineEdit.text())

    def _read_price_params(self, definition):
        try:
            price_ether = float(self.gui.ui.taskMaxPriceLineEdit.text())
            definition.max_price = int(price_ether * denoms.ether)
        except ValueError:
            logger.warning("Wrong price value")

    def _read_advanced_verification_params(self, definition):
        read_advanced_verification_params(self.gui, definition)

    def _read_resource_params(self, definition):
        definition.add_to_resources()
        self.logic.customizer.gui.ui.resourceFilesLabel.setText(
                u"{}".format(len(definition.resources)))

    def _optimize_total_check_box_changed(self):
        self.gui.ui.totalSpinBox.setEnabled(not self.gui.ui.optimizeTotalCheckBox.isChecked())
        self._set_new_pessimistic_cost()

    def _open_options(self):
        task_name = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        task = self.logic.get_task_type(task_name)
        dialog = task.dialog
        dialog_controller = task.dialog_controller
        task_dialog = dialog(self.gui.window)
        dialog_controller(task_dialog, self.logic, self)
        task_dialog.show()

    def _task_type_value_changed(self, name):
        task_name = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        task = self.logic.get_task_type(task_name)
        self.logic.options = deepcopy(task.options)
        self._update_options("{}".format(name))

    def _get_add_resource_dialog(self):
        return AddTaskResourcesDialog(self.gui.window)

    def _set_new_pessimistic_cost(self):
        try:
            price = float(self.gui.ui.taskMaxPriceLineEdit.text())
            if self.gui.ui.optimizeTotalCheckBox.isChecked():
                self.gui.ui.pessimisticCostLabel.setText("unknown")
            else:
                time_ = get_subtask_hours(self.gui) * float(self.gui.ui.totalSpinBox.value())
                cost = price * time_
                self.gui.ui.pessimisticCostLabel.setText(u"{:.6f} GNT".format(cost))
        except ValueError:
            self.gui.ui.pessimisticCostLabel.setText("unknown")

    def _advance_settings_button_clicked(self):
        self.gui.ui.advanceNewTaskWidget.setVisible(not self.gui.ui.advanceNewTaskWidget.isVisible())
        self.gui.ui.showAdvanceNewTaskButton.setText(
            self.SHOW_ADVANCE_BUTTON_MESSAGE[self.gui.ui.advanceNewTaskWidget.isVisible()])

    def _update_options(self, name):
        task_type = self.logic.get_task_type(name)
        self.logic.set_current_task_type(name)
        self.logic.options = task_type.options()
        self._change_task_widget(name)
        set_time_spin_boxes(self.gui, task_type.defaults.full_task_timeout, task_type.defaults.subtask_timeout)
        self.gui.ui.totalSpinBox.setRange(task_type.defaults.min_subtasks, task_type.defaults.max_subtasks)
        self._set_name()
        self._clear_resources()

    def _change_task_widget(self, name):
        for i in reversed(range(self.gui.ui.taskSpecificLayout.count())):
            self.gui.ui.taskSpecificLayout.itemAt(i).widget().setParent(None)
        task = self.logic.get_task_type(u"{}".format(name))
        self.task_customizer = task.dialog_controller(task.dialog, self.logic)
        self.gui.ui.taskSpecificLayout.addWidget(task.dialog, 0, 0, 1, 1)

    def _clear_resources(self):
        if self.add_task_resource_dialog:
            self.add_task_resource_dialog_customizer.resources = set()
            self.add_task_resource_dialog.ui.folderTreeView.model().addStartFiles([])
            self.add_task_resource_dialog.ui.folderTreeView.model().checks = {}
        self.gui.ui.resourceFilesLabel.setText("0")

    def _change_finish_state(self, state):
        self.gui.ui.finishButton.setEnabled(state)
        self.gui.ui.testTaskButton.setEnabled(not state)

    def __test_task_button_clicked(self):
        self.task_state = TaskDesc()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._query_task_definition()

        if not self.logic.run_test_task(self.task_state):
            logger.error("Task not tested properly")

    def __reset_to_defaults(self):
        task_type = self.__get_current_task_type()

        self.logic.options = task_type.options()
        self.logic.set_current_task_type(task_type.name)

        self.task_customizer.load_data()

        set_time_spin_boxes(self.gui, task_type.defaults.full_task_timeout, task_type.defaults.subtask_timeout)

        self._clear_resources()

        self._change_finish_state(False)

        self._set_name()
        self.gui.ui.totalSpinBox.setRange(task_type.defaults.min_subtasks, task_type.defaults.max_subtasks)
        self.gui.ui.totalSpinBox.setValue(task_type.defaults.default_subtasks)
        self.gui.ui.totalSpinBox.setEnabled(True)
        self.gui.ui.optimizeTotalCheckBox.setChecked(False)
        self._set_max_price()

    def __get_current_task_type(self):
        index = self.gui.ui.taskTypeComboBox.currentIndex()
        task_type = self.gui.ui.taskTypeComboBox.itemText(index)
        return self.logic.get_task_type(u"{}".format(task_type))

    def __advanced_verification_changed(self):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        set_verification_widgets_state(self.gui, state)

    def __verification_random_changed(self):
        verification_random_changed(self.gui)
