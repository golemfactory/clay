import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from examples.gnr.customizers.NewTaskDialogCustomizer import NewTaskDialogCustomizer

from AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from examples.gnr.RenderingTaskState import RenderingTaskState, RenderingTaskDefinition, \
    AdvanceRenderingVerificationOptions
from golem.task.TaskState import TaskStatus
from TimeHelper import setTimeSpinBoxes, getTimeValues
from VerificationParamsHelper import readAdvanceVerificationParams, setVerificationWidgetsState, loadVerificationParams, \
    verificationRandomChanged

import logging

logger = logging.getLogger(__name__)


class RenderingNewTaskDialogCustomizer(NewTaskDialogCustomizer):
    #############################
    def _setup_connections(self):
        NewTaskDialogCustomizer._setup_connections(self)
        self._setup_renderers_connections()
        self._setup_output_connections()
        self._setup_verification_connections()

    #############################
    def _setup_task_type_connections(self):
        pass

    #############################
    def _setup_renderers_connections(self):
        QtCore.QObject.connect(self.gui.ui.rendererComboBox, QtCore.SIGNAL("currentIndexChanged(const QString)"),
                               self.__renderer_combo_box_value_changed)
        self.gui.ui.chooseMainSceneFileButton.clicked.connect(self._chooseMainSceneFileButtonClicked)

    #############################
    def _setup_output_connections(self):
        self.gui.ui.chooseOutputFileButton.clicked.connect(self.__chooseOutputFileButtonClicked)
        QtCore.QObject.connect(self.gui.ui.outputResXSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__res_x_changed)
        QtCore.QObject.connect(self.gui.ui.outputResYSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__res_y_changed)

    #############################
    def _setup_advance_new_task_connections(self):
        NewTaskDialogCustomizer._setup_advance_new_task_connections(self)
        self.gui.ui.testTaskButton.clicked.connect(self.__testTaskButtonClicked)
        self.gui.ui.resetToDefaultButton.clicked.connect(self.__resetToDefaultButtonClicked)

        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutHourSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutMinSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.fullTaskTimeoutSecSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeHourSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeMinSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.minSubtaskTimeSecSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutHourSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutMinSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.subtaskTimeoutSecSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.mainProgramFileLineEdit, QtCore.SIGNAL("textChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.mainSceneFileLineEdit, QtCore.SIGNAL("textChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.outputFormatsComboBox, QtCore.SIGNAL("currentIndexChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.outputFileLineEdit, QtCore.SIGNAL("textChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.totalSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.verificationSizeXSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.verificationSizeYSpinBox, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.verificationForAllRadioButton, QtCore.SIGNAL("toggled(bool)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.verificationForFirstRadioButton, QtCore.SIGNAL("toggled(bool)"),
                               self.__task_settings_changed)
        QtCore.QObject.connect(self.gui.ui.probabilityLineEdit, QtCore.SIGNAL("valueChanged(const QString)"),
                               self.__task_settings_changed)

    #############################
    def _setup_verification_connections(self):
        QtCore.QObject.connect(self.gui.ui.verificationRandomRadioButton, QtCore.SIGNAL("toggled(bool)"),
                               self.__verification_random_changed)
        QtCore.QObject.connect(self.gui.ui.advanceVerificationCheckBox, QtCore.SIGNAL("stateChanged(int)"),
                               self.__advance_verification_changed)

    #############################
    def _init(self):
        self._setUid()

        renderers = self.logic.get_renderers()
        dr = self.logic.get_default_renderer()
        self.renderer_options = dr.renderer_options()

        for k in renderers:
            r = renderers[k]
            self.gui.ui.rendererComboBox.addItem(r.name)

        renderer_item = self.gui.ui.rendererComboBox.findText(dr.name)
        if renderer_item >= 0:
            self.gui.ui.rendererComboBox.setCurrentIndex(renderer_item)
        else:
            logger.error("Cannot load task, wrong default renderer")

        self.gui.ui.totalSpinBox.setRange(dr.defaults.min_subtasks, dr.defaults.max_subtasks)
        self.gui.ui.totalSpinBox.setValue(dr.defaults.default_subtasks)

        self.gui.ui.outputResXSpinBox.setValue(dr.defaults.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue(dr.defaults.resolution[1])
        self.gui.ui.verificationSizeXSpinBox.setMaximum(dr.defaults.resolution[0])
        self.gui.ui.verificationSizeYSpinBox.setMaximum(dr.defaults.resolution[1])

    #############################
    def _chooseMainSceneFileButtonClicked(self):
        scene_file_ext = self.logic.get_current_renderer().scene_file_ext

        outputFileTypes = " ".join([u"*.{}".format(ext) for ext in scene_file_ext])
        filter = u"Scene files ({})".format(outputFileTypes)

        dir = os.path.dirname(u"{}".format(self.gui.ui.mainSceneFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                                             "Choose main scene file", dir, filter))

        if file_name != '':
            self.gui.ui.mainSceneFileLineEdit.setText(file_name)

    #############################
    def __updateRendererOptions(self, name):
        r = self.logic.get_renderer(name)

        if r:
            self.logic.set_current_renderer(name)
            self.renderer_options = r.renderer_options()

            self.gui.ui.outputFormatsComboBox.clear()
            self.gui.ui.outputFormatsComboBox.addItems(r.output_formats)

            for i, output_format in enumerate(r.output_formats):
                if output_format == r.defaults.output_format:
                    self.gui.ui.outputFormatsComboBox.setCurrentIndex(i)

            self.gui.ui.mainProgramFileLineEdit.setText(r.defaults.main_program_file)

            setTimeSpinBoxes(self.gui, r.defaults.full_task_timeout, r.defaults.subtask_timeout,
                             r.defaults.min_subtask_time)

            self.gui.ui.totalSpinBox.setRange(r.defaults.min_subtasks, r.defaults.max_subtasks)

        else:
            assert False, "Unreachable"

    #############################
    def __reset_to_defaults(self):
        dr = self.__get_current_renderer()

        self.renderer_options = dr.renderer_options()
        self.logic.set_current_renderer(dr.name)

        self.gui.ui.outputFormatsComboBox.clear()
        self.gui.ui.outputFormatsComboBox.addItems(dr.output_formats)

        for i, output_format in enumerate(dr.output_formats):
            if output_format == dr.defaults.output_format:
                self.gui.ui.outputFormatsComboBox.setCurrentIndex(i)

        self.gui.ui.mainProgramFileLineEdit.setText(dr.defaults.main_program_file)

        setTimeSpinBoxes(self.gui, dr.defaults.full_task_timeout, dr.defaults.subtask_timeout,
                         dr.defaults.min_subtask_time)

        self.gui.ui.outputFileLineEdit.clear()

        self.gui.ui.outputResXSpinBox.setValue(dr.defaults.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue(dr.defaults.resolution[1])

        self.gui.ui.mainSceneFileLineEdit.clear()

        if self.addTaskResourceDialog:
            self.addTaskResourcesDialogCustomizer.resources = set()
            self.addTaskResourceDialog.ui.folderTreeView.model().addStartFiles([])
            self.addTaskResourceDialog.ui.folderTreeView.model().checks = {}

        self._changeFinishState(False)

        self.gui.ui.totalSpinBox.setRange(dr.defaults.min_subtasks, dr.defaults.max_subtasks)
        self.gui.ui.totalSpinBox.setValue(dr.defaults.default_subtasks)
        self.gui.ui.totalSpinBox.setEnabled(True)
        self.gui.ui.optimizeTotalCheckBox.setChecked(False)

    # SLOTS
    def __task_table_row_clicked(self, row):
        if row < self.gui.ui.taskTableWidget.rowCount():
            task_id = self.gui.ui.taskTableWidget.item(row, 0).text()
            task_id = "{}".format(task_id)
            self.update_task_additional_info(task_id)

    def __show_new_task_dialog_clicked(self):
        renderers = self.logic.get_renderers()

        self.__setupNewTaskDialogConnections(self.gui.ui)

        self.gui.ui.taskIdLabel.setText(self._generateNewTaskUID())

        for k in renderers:
            r = renderers[k]
            self.gui.ui.rendererComboBox.addItem(r.name)

    def __renderer_combo_box_value_changed(self, name):
        self.__updateRendererOptions("{}".format(name))

    def __task_settings_changed(self, name=None):
        self._changeFinishState(False)

    #############################
    def __chooseOutputFileButtonClicked(self):

        outputFileType = u"{}".format(self.gui.ui.outputFormatsComboBox.currentText())
        filter = u"{} (*.{})".format(outputFileType, outputFileType)

        dir = os.path.dirname(u"{}".format(self.gui.ui.outputFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getSaveFileName(self.gui.window,
                                                             "Choose output file", dir, filter))

        if file_name != '':
            self.gui.ui.outputFileLineEdit.setText(file_name)
            self._changeFinishState(False)

    def _changeFinishState(self, state):
        self.gui.ui.finishButton.setEnabled(state)
        self.gui.ui.testTaskButton.setEnabled(not state)

    #############################
    def _chooseMainProgramFileButtonClicked(self):

        dir = os.path.dirname(u"{}".format(self.gui.ui.mainProgramFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
                                                             "Choose main program file", dir, "Python (*.py)"))

        if file_name != '':
            self.gui.ui.mainProgramFileLineEdit.setText(file_name)
            self._changeFinishState(False)

    ############################
    def _showAddResourcesDialog(self):
        NewTaskDialogCustomizer._showAddResourcesDialog(self)
        self._changeFinishState(False)

    ############################
    def load_task_definition(self, task_definition):
        assert isinstance(task_definition, RenderingTaskDefinition)

        definition = deepcopy(task_definition)
        self.gui.ui.taskIdLabel.setText(self._generateNewTaskUID())

        self._loadBasicTaskParams(definition)
        self._loadRendererParams(definition)
        self._loadAdvanceTaskParams(definition)
        self._loadResources(definition)
        self._loadVerificationParams(definition)

    ########################
    def _loadOptions(self, definition):
        pass

    ############################
    def _load_task_type(self, definition):
        renderer_item = self.gui.ui.rendererComboBox.findText(definition.renderer)
        if renderer_item >= 0:
            self.gui.ui.rendererComboBox.setCurrentIndex(renderer_item)
        else:
            logger.error("Cannot load task, wrong renderer")
            return

    ############################
    def _loadRendererParams(self, definition):
        self.renderer_options = deepcopy(definition.renderer_options)

        self.gui.ui.outputResXSpinBox.setValue(definition.resolution[0])
        self.gui.ui.outputResYSpinBox.setValue(definition.resolution[1])
        self.gui.ui.outputFileLineEdit.setText(definition.output_file)

        output_format_item = self.gui.ui.outputFormatsComboBox.findText(definition.output_format)

        if output_format_item >= 0:
            self.gui.ui.outputFormatsComboBox.setCurrentIndex(output_format_item)
        else:
            logger.error("Cannot load task, wrong output format")
            return

        if os.path.normpath(definition.main_scene_file) in definition.resources:
            definition.resources.remove(os.path.normpath(definition.main_scene_file))
        definition.resources = definition.renderer_options.remove_from_resources(definition.resources)

    ############################
    def _loadBasicTaskParms(self, definition):
        r = self.logic.get_renderer(definition.renderer)
        self.gui.ui.totalSpinBox.setRange(r.defaults.min_subtasks, r.defaults.max_subtasks)
        NewTaskDialogCustomizer._loadBasicTaskParams(definition)

    ############################
    def _loadResources(self, definition):
        if os.path.normpath(definition.main_scene_file) in definition.resources:
            definition.resources.remove(os.path.normpath(definition.main_scene_file))
        definition.resources = definition.renderer_options.remove_from_resources(definition.resources)

        NewTaskDialogCustomizer._loadResources(self, definition)

        self.gui.ui.mainSceneFileLineEdit.setText(definition.main_scene_file)

    ############################
    def _loadVerificationParams(self, definition):
        loadVerificationParams(self.gui, definition)

    ############################
    def __setVerificationWidgetsState(self, state):
        setVerificationWidgetsState(self.gui, state)

    ############################
    def __testTaskButtonClicked(self):
        self.task_state = RenderingTaskState()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._queryTaskDefinition()

        if not self.logic.runTestTask(self.task_state):
            logger.error("Task not tested properly")

    #############################
    def test_taskComputationFinished(self, success, est_mem):
        if success:
            self.task_state.definition.estimated_memory = est_mem
            self._changeFinishState(True)

    #############################
    def _finishButtonClicked(self):
        self._addCurrentTask()

    #############################
    def _cancelButtonClicked(self):
        self.__reset_to_defaults()
        NewTaskDialogCustomizer._cancelButtonClicked(self)

    #############################
    def __resetToDefaultButtonClicked(self):
        self.__reset_to_defaults()

    #############################
    def __get_current_renderer(self):
        index = self.gui.ui.rendererComboBox.currentIndex()
        rendererName = self.gui.ui.rendererComboBox.itemText(index)
        return self.logic.get_renderer(u"{}".format(rendererName))

    #############################
    def _queryTaskDefinition(self):
        definition = RenderingTaskDefinition()
        definition = self._readBasicTaskParams(definition)
        definition = self._read_renderer_params(definition)
        definition = self._readAdvanceVerificationParams(definition)

        return definition

    #############################
    def _readTaskType(self):
        pass

    #############################
    def _read_renderer_params(self, definition):
        definition.renderer = self.__get_current_renderer().name
        definition.renderer_options = deepcopy(self.renderer_options)
        definition.resolution = [self.gui.ui.outputResXSpinBox.value(), self.gui.ui.outputResYSpinBox.value()]
        definition.output_file = u"{}".format(self.gui.ui.outputFileLineEdit.text())
        definition.output_format = u"{}".format(
            self.gui.ui.outputFormatsComboBox.itemText(self.gui.ui.outputFormatsComboBox.currentIndex()))

        if self.addTaskResourcesDialogCustomizer:
            definition.resources = self.renderer_options.add_to_resources(definition.resources)

            definition.main_scene_file = u"{}".format(self.gui.ui.mainSceneFileLineEdit.text())
            definition.resources.add(os.path.normpath(definition.main_scene_file))
        return definition

    #############################
    def _readAdvanceVerificationParams(self, definition):
        return readAdvanceVerificationParams(self.gui, definition)

    #############################
    def _optimizeTotalCheckBoxChanged(self):
        NewTaskDialogCustomizer._optimizeTotalCheckBoxChanged(self)
        self.__task_settings_changed()

    #############################
    def _openOptions(self):
        rendererName = self.gui.ui.rendererComboBox.itemText(self.gui.ui.rendererComboBox.currentIndex())
        renderer = self.logic.get_renderer(u"{}".format(rendererName))
        dialog = renderer.dialog
        dialog_customizer = renderer.dialog_customizer
        rendererDialog = dialog(self.gui.window)
        rendererDialogCustomizer = dialog_customizer(rendererDialog, self.logic, self)
        rendererDialog.show()

    def set_renderer_options(self, options):
        self.renderer_options = options
        self.__task_settings_changed()

    def get_renderer_options(self):
        return self.renderer_options

    def __advance_verification_changed(self):
        state = self.gui.ui.advanceVerificationCheckBox.isChecked()
        self.__setVerificationWidgetsState(state)
        self.__task_settings_changed()

    def __res_x_changed(self):
        self.gui.ui.verificationSizeXSpinBox.setMaximum(self.gui.ui.outputResXSpinBox.value())
        self.__task_settings_changed()

    def __res_y_changed(self):
        self.gui.ui.verificationSizeYSpinBox.setMaximum(self.gui.ui.outputResYSpinBox.value())
        self.__task_settings_changed()

    def __verification_random_changed(self):
        verificationRandomChanged(self.gui)
        self.__task_settings_changed()
