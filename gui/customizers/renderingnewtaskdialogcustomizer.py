import os
import time

from PyQt4.QtCore import QString
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from golem.task.taskstate import TaskStatus

from apps.rendering.task.renderingtaskstate import RenderingTaskState, RenderingTaskDefinition

from gnr.customizers.newtaskdialogcustomizer import NewTaskDialogCustomizer

from timehelper import set_time_spin_boxes
from verificationparamshelper import read_advance_verification_params, set_verification_widgets_state, \
    load_verification_params, verification_random_changed

import logging

logger = logging.getLogger("gnr.gui")


class RenderingNewTaskDialogCustomizer(NewTaskDialogCustomizer):

    def __init__(self, gui, logic):
        NewTaskDialogCustomizer.__init__(self, gui, logic)
        self.logic.renderer_options = None
        self.gui.ui.taskNameLineEdit.setText(
            u"{}_{}".format(self.gui.ui.taskTypeComboBox.currentText(), time.strftime("%H:%M:%S_%Y-%m-%d")))

    def _setup_connections(self):
        NewTaskDialogCustomizer._setup_connections(self)
        self._setup_renderers_connections()
        self._setup_verification_connections()

    def _setup_task_type_connections(self):
        pass

    def _setup_renderers_connections(self):
        self.gui.ui.taskTypeComboBox.currentIndexChanged[QString].connect(
            lambda x: self.__renderer_combo_box_value_changed(x))

    def _setup_advance_new_task_connections(self):
        NewTaskDialogCustomizer._setup_advance_new_task_connections(self)
        self.gui.ui.testTaskButton.clicked.connect(self.__test_task_button_clicked)
        self.gui.ui.resetToDefaultButton.clicked.connect(self.__reset_to_default_button_clicked)
        self.__connect_with_task_settings_changed([self.gui.ui.fullTaskTimeoutSecSpinBox.valueChanged,
                                                   self.gui.ui.fullTaskTimeoutMinSpinBox.valueChanged,
                                                   self.gui.ui.fullTaskTimeoutHourSpinBox.valueChanged,
                                                   self.gui.ui.mainProgramFileLineEdit.textChanged,
                                                   self.gui.ui.verificationSizeXSpinBox.valueChanged,
                                                   self.gui.ui.verificationSizeYSpinBox.valueChanged,
                                                   self.gui.ui.verificationForAllRadioButton.toggled,
                                                   self.gui.ui.verificationForFirstRadioButton.toggled,
                                                   self.gui.ui.probabilityLineEdit.textChanged
                                                   ])

    def _setup_verification_connections(self):
        self.gui.ui.verificationRandomRadioButton.toggled.connect(self.__verification_random_changed)
        self.gui.ui.advanceVerificationCheckBox.stateChanged.connect(self.__advance_verification_changed)

    def _init(self):
        self._set_uid()
        self._set_max_price()
        self.gui.ui.resourceFilesLabel.setText("0")

        renderers = self.logic.get_renderers()
        dr = self.logic.get_default_renderer()
        self.logic.renderer_options = dr.renderer_options()

        for k in renderers:
            r = renderers[k]
            self.gui.ui.taskTypeComboBox.addItem(r.name)

        renderer_item = self.gui.ui.taskTypeComboBox.findText(dr.name)
        if renderer_item >= 0:
            self.gui.ui.taskTypeComboBox.setCurrentIndex(renderer_item)
        else:
            logger.error("Cannot load task, wrong default renderer")
        self.__renderer_combo_box_value_changed(dr.name)

        self.gui.ui.totalSpinBox.setRange(dr.defaults.min_subtasks, dr.defaults.max_subtasks)
        self.gui.ui.totalSpinBox.setValue(dr.defaults.default_subtasks)

        self.gui.ui.verificationSizeXSpinBox.setMaximum(dr.defaults.resolution[0])
        self.gui.ui.verificationSizeYSpinBox.setMaximum(dr.defaults.resolution[1])

    def _set_new_pessimistic_cost(self):
        NewTaskDialogCustomizer._set_new_pessimistic_cost(self)
        self.task_settings_changed()

    def _change_task_widget(self, name):
        for i in reversed(range(self.gui.ui.taskSpecificLayout.count())):
            self.gui.ui.taskSpecificLayout.itemAt(i).widget().setParent(None)
        task = self.logic.get_renderer(u"{}".format(name))
        self.task_customizer = task.dialog_customizer(task.dialog, self.logic)
        self.gui.ui.taskSpecificLayout.addWidget(task.dialog, 0, 0, 1, 1)

    def __update_renderer_options(self, name):
        r = self.logic.get_renderer(name)
        if r:
            self.logic.set_current_renderer(name)
            self.logic.renderer_options = r.renderer_options()
            self._change_task_widget(name)
            self.gui.ui.mainProgramFileLineEdit.setText(r.defaults.main_program_file)
            set_time_spin_boxes(self.gui, r.defaults.full_task_timeout, r.defaults.subtask_timeout)
            self.gui.ui.totalSpinBox.setRange(r.defaults.min_subtasks, r.defaults.max_subtasks)
            self.gui.ui.taskNameLineEdit.setText(u"{}_{}".format(
                self.gui.ui.taskTypeComboBox.currentText(), time.strftime("%H:%M:%S_%Y-%m-%d")))
            self._clear_resources()

        else:
            assert False, "Unreachable"

    def __reset_to_defaults(self):
        dr = self.__get_current_renderer()

        self.logic.renderer_options = dr.renderer_options()
        self.logic.set_current_renderer(dr.name)

        self.task_customizer.load_data()

        self.gui.ui.mainProgramFileLineEdit.setText(dr.defaults.main_program_file)

        set_time_spin_boxes(self.gui, dr.defaults.full_task_timeout, dr.defaults.subtask_timeout)

        self._clear_resources()

        self._change_finish_state(False)

        self.gui.ui.taskNameLineEdit.setText(
            u"{}_{}".format(self.gui.ui.taskTypeComboBox.currentText(), time.strftime("%H:%M:%S_%Y-%m-%d")))
        self.gui.ui.totalSpinBox.setRange(dr.defaults.min_subtasks, dr.defaults.max_subtasks)
        self.gui.ui.totalSpinBox.setValue(dr.defaults.default_subtasks)
        self.gui.ui.totalSpinBox.setEnabled(True)
        self.gui.ui.optimizeTotalCheckBox.setChecked(False)
        self._set_max_price()

    def _clear_resources(self):
        if self.add_task_resource_dialog:
            self.add_task_resource_dialog_customizer.resources = set()
            self.add_task_resource_dialog.ui.folderTreeView.model().addStartFiles([])
            self.add_task_resource_dialog.ui.folderTreeView.model().checks = {}
        self.gui.ui.resourceFilesLabel.setText("0")

    # SLOTS

    def __renderer_combo_box_value_changed(self, name):
        self.__update_renderer_options("{}".format(name))

    def task_settings_changed(self, name=None):
        self._change_finish_state(False)

    def _change_finish_state(self, state):
        self.gui.ui.finishButton.setEnabled(state)
        self.gui.ui.testTaskButton.setEnabled(not state)

    def _choose_main_program_file_button_clicked(self):

        dir_ = os.path.dirname(u"{}".format(self.gui.ui.mainProgramFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                                             "Choose main program file", dir_,
                                                             "Python (*.py *.Py *.PY *.pY)"))

        if file_name != '':
            self.gui.ui.mainProgramFileLineEdit.setText(file_name)
            self._change_finish_state(False)

    def _show_add_resource_dialog(self):
        NewTaskDialogCustomizer._show_add_resource_dialog(self)
        self._change_finish_state(False)

    def load_task_definition(self, task_definition):
        assert isinstance(task_definition, RenderingTaskDefinition)

        definition = deepcopy(task_definition)
        self.gui.ui.taskIdLabel.setText(self._generate_new_task_uid())

        self._load_basic_task_params(definition)
        self.task_customizer.load_task_definition(definition)
        self._load_renderer_params(definition)
        self._load_advance_task_params(definition)
        self._load_resources(definition)
        self._load_verification_params(definition)
        self._load_payment_params(definition)

    def _load_options(self, definition):
        pass

    def _load_task_type(self, definition):
        renderer_item = self.gui.ui.taskTypeComboBox.findText(definition.renderer)
        if renderer_item >= 0:
            self.gui.ui.taskTypeComboBox.setCurrentIndex(renderer_item)
        else:
            logger.error("Cannot load task, wrong renderer")
            return

    def _load_renderer_params(self, definition):
        self.logic.renderer_options = deepcopy(definition.renderer_options)

    def _load_basic_task_params(self, definition):
        r = self.logic.get_renderer(definition.renderer)
        self.gui.ui.totalSpinBox.setRange(r.defaults.min_subtasks, r.defaults.max_subtasks)
        self.gui.ui.taskNameLineEdit.setText(definition.task_name if definition.task_name else u"{}_{}".format(
            self.gui.ui.taskTypeComboBox.currentText(), time.strftime("%H:%M:%S_%Y-%m-%d")))
        NewTaskDialogCustomizer._load_basic_task_params(self, definition)

    def _load_resources(self, definition):
        definition.resources = definition.renderer_options.remove_from_resources(definition.resources)
        NewTaskDialogCustomizer._load_resources(self, definition)

    def _load_verification_params(self, definition):
        load_verification_params(self.gui, definition)

    def __set_verification_widgets_state(self, state):
        set_verification_widgets_state(self.gui, state)

    def __test_task_button_clicked(self):
        self.task_state = RenderingTaskState()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._query_task_definition()

        if not self.logic.run_test_task(self.task_state):
            logger.error("Task not tested properly")

    def test_task_computation_finished(self, success, est_mem):
        if success:
            self.task_state.definition.estimated_memory = est_mem
            self._change_finish_state(True)

    def _finish_button_clicked(self):
        self._add_current_task()
        self.load_task_definition(self.task_state.definition)

    def _cancel_button_clicked(self):
        self.__reset_to_defaults()
        NewTaskDialogCustomizer._cancel_button_clicked(self)

    def __reset_to_default_button_clicked(self):
        self.__reset_to_defaults()

    def __get_current_renderer(self):
        index = self.gui.ui.taskTypeComboBox.currentIndex()
        renderer_name = self.gui.ui.taskTypeComboBox.itemText(index)
        return self.logic.get_renderer(u"{}".format(renderer_name))

    def _query_task_definition(self):
        definition = RenderingTaskDefinition()
        self._read_basic_task_params(definition)
        self._read_renderer_params(definition)
        self._read_task_name(definition)
        self._read_advance_verification_params(definition)
        self._read_price_params(definition)

        return definition

    def _read_task_type(self):
        pass

    def _read_renderer_params(self, definition):
        definition.renderer = self.__get_current_renderer().name
        definition.renderer_options = deepcopy(self.logic.renderer_options)
        self.get_task_specific_options(definition)
        self.logic.renderer_options = definition.renderer_options

        if self.add_task_resource_dialog_customizer:
            definition.resources = self.logic.renderer_options.add_to_resources(definition.resources)
            definition.resources.add(os.path.normpath(definition.main_scene_file))
            self.logic.customizer.gui.ui.resourceFilesLabel.setText(u"{}".format(len(definition.resources)))

    def _read_advance_verification_params(self, definition):
        read_advance_verification_params(self.gui, definition)

    def _optimize_total_check_box_changed(self):
        NewTaskDialogCustomizer._optimize_total_check_box_changed(self)
        self.task_settings_changed()

    def _open_options(self):
        renderer_name = self.gui.ui.taskTypeComboBox.itemText(self.gui.ui.taskTypeComboBox.currentIndex())
        renderer = self.logic.get_renderer(u"{}".format(renderer_name))
        dialog = renderer.dialog
        dialog_customizer = renderer.dialog_customizer
        renderer_dialog = dialog(self.gui.window)
        dialog_customizer(renderer_dialog, self.logic, self)
        renderer_dialog.show()

    def get_task_specific_options(self, definition):
        self.task_customizer.get_task_specific_options(definition)

    def set_renderer_options(self, options):
        self.logic.renderer_options = options
        self.task_settings_changed()

    def get_renderer_options(self):
        return self.logic.renderer_options

    def __advance_verification_changed(self):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        self.__set_verification_widgets_state(state)
        self.task_settings_changed()

    def __verification_random_changed(self):
        verification_random_changed(self.gui)
        self.task_settings_changed()

    def __connect_with_task_settings_changed(self, list_gui_el):
        for gui_el in list_gui_el:
            gui_el.connect(self.task_settings_changed)
