from __future__ import division
import logging
import os
import time

from copy import deepcopy

from ethereum.utils import denoms
from PyQt4.QtCore import QString
from PyQt4.QtGui import QFileDialog
from twisted.internet.defer import inlineCallbacks

from golem.task.taskstate import TaskStatus

from apps.rendering.task.renderingtaskstate import RenderingTaskState

from gnr.ui.dialog import AddTaskResourcesDialog
from gnr.customizers.addresourcesdialogcustomizer import AddResourcesDialogCustomizer
from gnr.gnrtaskstate import GNRTaskDefinition
from gnr.customizers.timehelper import set_time_spin_boxes, get_time_values, get_subtask_hours
from gnr.customizers.customizer import Customizer
from gnr.customizers.common import get_save_dir

logger = logging.getLogger("gnr.gui")


class NewTaskDialogCustomizer(Customizer):

    SHOW_ADVANCE_BUTTON_MESSAGE = ["Show advanced settings", "Hide advanced settings"]

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
        self.gui.ui.advanceNewTaskWidget.hide()
        self.gui.ui.showAdvanceNewTaskButton.setText(self.SHOW_ADVANCE_BUTTON_MESSAGE[0])
        self._init()

    def _setup_connections(self):
        self._setup_task_type_connections()
        self._setup_basic_new_task_connections()
        self._setup_advance_new_task_connections()
        self._setup_options_connections()
        self._setup_payment_connections()

    def _setup_task_type_connections(self):
        self.gui.ui.taskTypeComboBox.currentIndexChanged[QString].connect(self._task_type_value_changed)

    def _setup_basic_new_task_connections(self):
        self.gui.ui.saveButton.clicked.connect(self._save_task_button_clicked)
        self.gui.ui.addResourceButton.clicked.connect(self._show_add_resource_dialog)
        self.gui.ui.finishButton.clicked.connect(self._finish_button_clicked)

    def _setup_advance_new_task_connections(self):
        self.gui.ui.showAdvanceNewTaskButton.clicked.connect(self._advance_settings_button_clicked)
        self.gui.ui.optimizeTotalCheckBox.stateChanged.connect(self._optimize_total_check_box_changed)
        self.gui.ui.subtaskTimeoutHourSpinBox.valueChanged.connect(self._set_new_pessimistic_cost)
        self.gui.ui.subtaskTimeoutMinSpinBox.valueChanged.connect(self._set_new_pessimistic_cost)
        self.gui.ui.subtaskTimeoutSecSpinBox.valueChanged.connect(self._set_new_pessimistic_cost)
        self.gui.ui.totalSpinBox.valueChanged.connect(self._set_new_pessimistic_cost)
        self.gui.ui.chooseMainProgramFileButton.clicked.connect(self._choose_main_program_file_button_clicked)

    def _setup_options_connections(self):
        pass

    def _setup_payment_connections(self):
        self.gui.ui.taskMaxPriceLineEdit.textChanged.connect(self._set_new_pessimistic_cost)

    def _set_uid(self):
        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())

    def _init(self):
        self._set_uid()
        self._set_max_price()
        self.gui.ui.resourceFilesLabel.setText("0")
        task_types = self.logic.get_task_types()
        for t in task_types.values():
            self.gui.ui.taskTypeComboBox.addItem(t.name)

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

    def _save_task_button_clicked(self):
        save_dir = get_save_dir()
        file_name = QFileDialog.getSaveFileName(self.gui.window,
                                                "Choose save file", save_dir, "Golem Task (*.gt)")

        if file_name != "":
            self._save_task(file_name)

    def _save_task(self, file_path):
        definition = self._query_task_definition()
        self.logic.save_task(definition, file_path)

    def load_task_definition(self, task_definition):
        assert isinstance(task_definition, GNRTaskDefinition)

        definition = deepcopy(task_definition)
        definition.resources = {os.path.normpath(res) for res in definition.resources}
        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())
        self._load_basic_task_params(definition)
        self._load_advance_task_params(definition)
        self._load_resources(definition)
        self._load_payment_params(definition)

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

        # TODO Better model management would be nice
        self.add_task_resource_dialog_customizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        self.gui.ui.resourceFilesLabel.setText(u"{}".format(len(self.add_task_resource_dialog_customizer.resources)))
        # for res in definition.resources:
        #     model.setData(model.index(res), QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)

    def _load_basic_task_params(self, definition):
        self._load_task_type(definition)
        self.save_setting('main_scene_path', os.path.dirname(definition.main_scene_file))
        self.save_setting('output_file_path', os.path.dirname(definition.output_file), sync=True)
        set_time_spin_boxes(self.gui, definition.full_task_timeout, definition.subtask_timeout)
        self.gui.ui.mainProgramFileLineEdit.setText(definition.main_program_file)
        self.gui.ui.totalSpinBox.setValue(definition.total_subtasks)
        self.gui.ui.taskNameLineEdit.setText(definition.task_name if definition.task_name else u"{}_{}".format(
            self.gui.ui.taskTypeComboBox.currentText(), time.strftime("%H:%M:%S_%Y-%m-%d")))

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

    def _load_payment_params(self, definition):
        price = definition.max_price / denoms.ether
        self.gui.ui.taskMaxPriceLineEdit.setText(u"{}".format(price))
        self._set_new_pessimistic_cost()

    def _finish_button_clicked(self):
        self.task_state = RenderingTaskState()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._query_task_definition()
        self._add_current_task()

    def _add_current_task(self):
        self.logic.add_tasks([deepcopy(self.task_state)])

    def _choose_main_program_file_button_clicked(self):

        dir_ = os.path.dirname(u"{}".format(self.gui.ui.mainProgramFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                                             "Choose main program file",
                                                             dir_,
                                                             "Python (*.py)"))

        if file_name != "":
            self.gui.ui.mainProgramFileLineEdit.setText(file_name)

    @staticmethod
    def _generate_new_task_uid():
        import uuid
        return "{}".format(uuid.uuid4())

    def _query_task_definition(self):
        definition = GNRTaskDefinition()
        self._read_basic_task_params(definition)
        self._read_task_type(definition)
        self._read_price_params(definition)
        self._read_task_name(definition)
        definition.options = self.options
        return definition

    def _read_basic_task_params(self, definition):
        definition.task_id = u"{}".format(self.gui.ui.taskIdLabel.text())
        definition.full_task_timeout, definition.subtask_timeout = get_time_values(self.gui)
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

    def _optimize_total_check_box_changed(self):
        self.gui.ui.totalSpinBox.setEnabled(not self.gui.ui.optimizeTotalCheckBox.isChecked())
        self._set_new_pessimistic_cost()

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

    def _set_new_pessimistic_cost(self):
        try:
            price = float(self.gui.ui.taskMaxPriceLineEdit.text())
            if self.gui.ui.optimizeTotalCheckBox.isChecked():
                self.gui.ui.pessimisticCostLabel.setText("unknown")
            else:
                time_ = get_subtask_hours(self.gui) * float(self.gui.ui.totalSpinBox.value())
                cost = price * time_
                self.gui.ui.pessimisticCostLabel.setText(u"{:.6f} ETH".format(cost))
        except ValueError:
            self.gui.ui.pessimisticCostLabel.setText("unknown")

    def _advance_settings_button_clicked(self):
        self.gui.ui.advanceNewTaskWidget.setVisible(not self.gui.ui.advanceNewTaskWidget.isVisible())
        self.gui.ui.showAdvanceNewTaskButton.setText(
            self.SHOW_ADVANCE_BUTTON_MESSAGE[self.gui.ui.advanceNewTaskWidget.isVisible()])
