import os
from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog
from copy import deepcopy

from examples.gnr.ui.AddTaskResourcesDialog import AddTaskResourcesDialog

from examples.gnr.customizers.AddResourcesDialogCustomizer import AddResourcesDialogCustomizer
from examples.gnr.RenderingTaskState import RenderingTaskState
from examples.gnr.GNRTaskState import GNRTaskDefinition
from golem.task.TaskState import TaskStatus
from examples.gnr.customizers.TimeHelper import setTimeSpinBoxes, getTimeValues

import logging

logger = logging.getLogger(__name__)

class NewTaskDialogCustomizer:
    #############################
    def __init__(self, gui, logic):

        self.gui    = gui
        self.logic  = logic
        self.options = None

        self.addTaskResourceDialog      = None
        self.task_state                  = None
        self.addTaskResourcesDialogCustomizer = None

        self._setup_connections()
        self._setUid()
        self._init()

    #############################
    def _setup_connections(self):
        self._setup_task_type_connections()
        self._setupBasicNewTaskConnections()
        self._setup_advance_new_task_connections()
        self._setupOptionsConnections()

    def _setup_task_type_connections(self):
        QtCore.QObject.connect(self.gui.ui.taskTypeComboBox, QtCore.SIGNAL("currentIndexChanged(const QString)"), self._taskTypeValueChanged)

    #############################
    def _setupBasicNewTaskConnections(self):
        self.gui.ui.saveButton.clicked.connect(self._saveTaskButtonClicked)
        self.gui.ui.chooseMainProgramFileButton.clicked.connect(self._chooseMainProgramFileButtonClicked)
        self.gui.ui.addResourceButton.clicked.connect(self._showAddResourcesDialog)
        self.gui.ui.finishButton.clicked.connect(self._finishButtonClicked)
        self.gui.ui.cancelButton.clicked.connect(self._cancelButtonClicked)

    #############################
    def _setup_advance_new_task_connections(self):
        QtCore.QObject.connect(self.gui.ui.optimizeTotalCheckBox, QtCore.SIGNAL("stateChanged(int) "), self._optimizeTotalCheckBoxChanged)

    #############################
    def _setupOptionsConnections(self):
        self.gui.ui.optionsButton.clicked.connect(self._openOptions)

    #############################
    def _setUid(self):
        self.gui.ui.taskIdLabel.setText(self._generateNewTaskUID())

    #############################
    def _init(self):
        self._setUid()

        task_types = self.logic.get_task_types()
        for t in task_types.values():
            self.gui.ui.taskTypeComboBox.addItem(t.name)

    #############################
    def _chooseMainProgramFileButtonClicked(self):

        dir = os.path.dirname(u"{}".format(self.gui.ui.mainProgramFileLineEdit.text()))

        file_name = u"{}".format(QFileDialog.getOpenFileName(self.gui.window,
            "Choose main program file", dir, "Python (*.py)"))

        if file_name != '':
            self.gui.ui.mainProgramFileLineEdit.setText(file_name)

    ############################
    def _showAddResourcesDialog(self):
        if not self.addTaskResourceDialog:
            self.addTaskResourceDialog = AddTaskResourcesDialog(self.gui.window)
            self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer(self.addTaskResourceDialog, self.logic)

        self.addTaskResourceDialog.show()

    ############################
    def _saveTaskButtonClicked(self):
        file_name = QFileDialog.getSaveFileName(self.gui.window,
            "Choose save file", "", "Golem Task (*.gt)")

        if file_name != '':
            self._saveTask(file_name)

    ############################
    def _saveTask(self, file_path):
        definition = self._queryTaskDefinition()
        self.logic.saveTask(definition, file_path)

    ############################
    def load_task_definition(self, task_definition):
        assert isinstance(task_definition, GNRTaskDefinition)

        definition = deepcopy(task_definition)

        self.gui.ui.taskIdLabel.setText(self._generateNewTaskUID())
        self._loadBasicTaskParams(definition)
        self._loadAdvanceTaskParams(definition)
        self._loadResources(definition)

    #############################
    def setOptions(self, options):
        self.options = options

    #############################
    def _loadResources(self, definition):
        self.addTaskResourceDialog = AddTaskResourcesDialog(self.gui.window)
        self.addTaskResourcesDialogCustomizer = AddResourcesDialogCustomizer(self.addTaskResourceDialog, self.logic)
        self.addTaskResourcesDialogCustomizer.resources = definition.resources

        model = self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model()

        commonPrefix = os.path.commonprefix(definition.resources)
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.setExpanded(model.index(commonPrefix), True)

        for res in definition.resources:
            pathHead, pathTail = os.path.split(res)
            while pathHead != '' and pathTail != '':
                self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.setExpanded(model.index(pathHead), True)
                pathHead, pathTail = os.path.split(pathHead)

        # TODO
        self.addTaskResourcesDialogCustomizer.gui.ui.folderTreeView.model().addStartFiles(definition.resources)
        # for res in definition.resources:
        #     model.setData(model.index(res), QtCore.Qt.Checked, QtCore.Qt.CheckStateRole)

    #############################
    def _loadBasicTaskParams(self, definition):
        self._load_task_type(definition)
        setTimeSpinBoxes(self.gui, definition.full_task_timeout, definition.subtask_timeout, definition.min_subtask_time)
        self.gui.ui.mainProgramFileLineEdit.setText(definition.main_program_file)
        self.gui.ui.totalSpinBox.setValue(definition.total_subtasks)

        if os.path.normpath(definition.main_program_file) in definition.resources:
            definition.resources.remove(os.path.normpath(definition.main_program_file))


        self._loadOptions(definition)


    ############################
    def _loadOptions(self, definition):
        self.options = deepcopy(definition.options)

    ############################
    def _load_task_type(self, definition):
        try:
            task_typeItem = self.gui.ui.taskTypeComboBox.findText(definition.task_type)
            if task_typeItem >= 0:
                self.gui.ui.taskTypeComboBox.setCurrentIndex(task_typeItem)
            else:
                logger.error("Cannot load task, unknown task type")
                return
        except Exception, err:
            logger.error("Wrong task type {}".format(str(err)))
            return

    #############################
    def _loadAdvanceTaskParams(self, definition):
        self.gui.ui.totalSpinBox.setEnabled(not definition.optimize_total)
        self.gui.ui.optimizeTotalCheckBox.setChecked(definition.optimize_total)

    #############################
    def _finishButtonClicked(self):
        self.task_state = RenderingTaskState()
        self.task_state.status = TaskStatus.notStarted
        self.task_state.definition = self._queryTaskDefinition()
        self._addCurrentTask()

    #############################
    def _addCurrentTask(self):
        self.logic.add_tasks([ self.task_state ])
        self.gui.window.close()

    #############################
    def _cancelButtonClicked(self):
        self.gui.window.close()

    #############################
    def _generateNewTaskUID(self):
        import uuid
        return "{}".format(uuid.uuid4())

    #############################
    def _queryTaskDefinition(self):
        definition = GNRTaskDefinition()
        definition = self._readBasicTaskParams(definition)
        definition = self._readTaskType(definition)
        definition.options = self.options
        return definition

    #############################
    def _readBasicTaskParams(self, definition):
        definition.task_id = u"{}".format(self.gui.ui.taskIdLabel.text())
        definition.full_task_timeout, definition.subtask_timeout, definition.min_subtask_time = getTimeValues(self.gui)
        definition.main_program_file = u"{}".format(self.gui.ui.mainProgramFileLineEdit.text())
        definition.optimize_total = self.gui.ui.optimizeTotalCheckBox.isChecked()
        if definition.optimize_total:
            definition.total_subtasks = 0
        else:
            definition.total_subtasks = self.gui.ui.totalSpinBox.value()

        if self.addTaskResourcesDialogCustomizer is not None:
            definition.resources = self.addTaskResourcesDialogCustomizer.resources
        else:
            definition.resources = set()

        definition.resources.add(os.path.normpath(definition.main_program_file))

        return definition

    #############################
    def _readTaskType(self, definition):
        definition.task_type = u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        return definition

    #############################
    def _optimizeTotalCheckBoxChanged(self):
        self.gui.ui.totalSpinBox.setEnabled(not self.gui.ui.optimizeTotalCheckBox.isChecked())

    #############################
    def _openOptions(self):
        taskName =  u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        task = self.logic.get_task_type(taskName)
        dialog = task.dialog
        dialog_customizer = task.dialog_customizer
        if dialog is not None and dialog_customizer is not None:
            taskDialog = dialog (self.gui.window)
            taskDialogCustomizer = dialog_customizer(taskDialog, self.logic, self)
            taskDialog.show()
        else:
            self.gui.ui.optionsButton.setEnabled(False)

    def _taskTypeValueChanged(self, name):
        taskName =  u"{}".format(self.gui.ui.taskTypeComboBox.currentText())
        task = self.logic.get_task_type(taskName)
        self.gui.ui.optionsButton.setEnabled(task.dialog is not None and task.dialog_customizer is not None)
        self.options = deepcopy(task.options)
