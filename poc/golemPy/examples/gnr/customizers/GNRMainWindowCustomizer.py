import logging
import os
import cPickle as pickle

from PyQt4 import QtCore
from PyQt4.QtGui import QPalette, QFileDialog, QMessageBox, QMenu

logger = logging.getLogger(__name__)

from examples.gnr.ui.NewTaskDialog import NewTaskDialog
from examples.gnr.ui.TaskTableElem import TaskTableElem
from examples.gnr.ui.TaskDetailsDialog import TaskDetailsDialog
from examples.gnr.ui.SubtaskDetailsDialog import SubtaskDetailsDialog
from examples.gnr.ui.ChangeTaskDialog import ChangeTaskDialog
from examples.gnr.ui.StatusWindow import StatusWindow
from examples.gnr.ui.AboutWindow import AboutWindow
from examples.gnr.ui.ConfigurationDialog import ConfigurationDialog
from examples.gnr.ui.EnvironmentsDialog import EnvironmentsDialog

from examples.gnr.customizers.NewTaskDialogCustomizer import NewTaskDialogCustomizer
from examples.gnr.customizers.TaskContexMenuCustomizer import TaskContextMenuCustomizer
from examples.gnr.customizers.TaskDetailsDialogCustomizer import TaskDetailsDialogCustomizer
from examples.gnr.customizers.SubtaskDetailsDialogCustomizer import SubtaskDetailsDialogCustomizer
from examples.gnr.customizers.ChangeTaskDialogCustomizer import ChangeTaskDialogCustomizer
from examples.gnr.customizers.StatusWindowCustomizer import StatusWindowCustomizer
from examples.gnr.customizers.AboutWindowCustomizer import AboutWindowCustomizer
from examples.gnr.customizers.ConfigurationDialogCustomizer import ConfigurationDialogCustomizer
from examples.gnr.customizers.EnvironmentsDialogCustomizer import EnvironmentsDialogCustomizer

from golem.core.simpleexccmd import is_windows, exec_cmd

class GNRMainWindowCustomizer:
    ############################
    def __init__(self, gui, logic):

        self.gui    = gui
        self.logic  = logic

        self.currentTaskHighlighted         = None
        self.taskDetailsDialog              = None
        self.taskDetailsDialogCustomizer    = None
        self.lastDefinition = None

        self._setupConnections()

        self._setErrorLabel()

    #############################
    def _setupConnections(self):
        self._setupBasicTaskConnections()
        self._setupBasicAppConnections()

    #############################
    def _setupBasicTaskConnections(self):
        self.gui.ui.actionNew.triggered.connect(self._showNewTaskDialogClicked)
        self.gui.ui.actionLoadTask.triggered.connect(self._loadTaskButtonClicked)
        QtCore.QObject.connect(self.gui.ui.taskTableWidget, QtCore.SIGNAL("cellClicked(int, int)"), self._taskTableRowClicked)
        QtCore.QObject.connect(self.gui.ui.taskTableWidget, QtCore.SIGNAL("doubleClicked(const QModelIndex)"), self._taskTableRowDoubleClicked)
        self.gui.ui.taskTableWidget.customContextMenuRequested.connect(self._contexMenuRequested)

    #############################
    def _setupBasicAppConnections(self):
        self.gui.ui.actionEdit.triggered.connect(self._showConfigurationDialogClicked)
        self.gui.ui.actionStatus.triggered.connect(self._showStatusClicked)
        self.gui.ui.actionAbout.triggered.connect(self._showAboutClicked)
        self.gui.ui.actionEnvironments.triggered.connect(self._showEnvironments)

    ############################
    def _setErrorLabel(self):
        palette = QPalette()
        palette.setColor(QPalette.Foreground, QtCore.Qt.red)
        self.gui.ui.errorLabel.setPalette(palette)

    ############################
    # Add new task to golem client
    def enqueue_new_task(self, uiNewTaskInfo):
        self.logic.enqueue_new_task(uiNewTaskInfo)

    ############################
    # Updates tasks information in gui
    def updateTasks(self, tasks):
        for i in range(self.gui.ui.taskTableWidget.rowCount()):
            task_id = self.gui.ui.taskTableWidget.item(i, 0).text()
            task_id = "{}".format(task_id)
            if task_id in tasks:
                self.gui.ui.taskTableWidget.item(i, 1).setText(tasks[ task_id ].task_state.status)
                progressBarInBoxLayout = self.gui.ui.taskTableWidget.cellWidget(i, 2)
                layout = progressBarInBoxLayout.layout()
                pb = layout.itemAt(0).widget()
                pb.setProperty("value", int(tasks[ task_id ].task_state.progress * 100.0))
                if self.taskDetailsDialogCustomizer:
                    if self.taskDetailsDialogCustomizer.gnrTaskState.definition.task_id == task_id:
                        self.taskDetailsDialogCustomizer.updateView(tasks[ task_id ].task_state)

            else:
                assert False, "Update task for unknown task."

    ############################
    # Add task information in gui
    def addTask(self, task):
        self._addTask(task.definition.task_id, task.status)

    ############################
    def updateTaskAdditionalInfo(self, t):
        self.currentTaskHighlighted = t

    #############################
    def showTaskResult(self, task_id):
        t = self.logic.get_task(task_id)
        if hasattr(t.definition, 'output_file') and os.path.isfile(t.definition.output_file):
            self._showFile(t.definition.output_file)
        elif hasattr(t.definition.options, 'output_file') and os.path.isfile(t.definition.options.output_file):
            self._showFile(t.definition.options.output_file)
        else:
            msgBox = QMessageBox()
            msgBox.setText("No output file defined.")
            msgBox.exec_()

    ############################
    def _showFile(self, file_name):
        if is_windows():
            os.startfile(file_name)
        else:
            opener = "see"
            exec_cmd([opener, file_name ], wait=False)


    ############################
    def _addTask(self, task_id, status):
        currentRowCount = self.gui.ui.taskTableWidget.rowCount()
        self.gui.ui.taskTableWidget.insertRow(currentRowCount)

        taskTableElem = TaskTableElem(task_id, status)

        for col in range(0, 2): self.gui.ui.taskTableWidget.setItem(currentRowCount, col, taskTableElem.getColumnItem(col))

        self.gui.ui.taskTableWidget.setCellWidget(currentRowCount, 2, taskTableElem.progressBarInBoxLayoutWidget)

        self.gui.ui.taskTableWidget.setCurrentItem(self.gui.ui.taskTableWidget.item(currentRowCount, 1))
        self.updateTaskAdditionalInfo(self.logic.get_task(task_id))

    ############################
    def remove_task(self, task_id):
        for row in range(0, self.gui.ui.taskTableWidget.rowCount()):
            if self.gui.ui.taskTableWidget.item(row, 0).text() == task_id:
                self.gui.ui.taskTableWidget.removeRow(row)
                return

   #############################
    def _showNewTaskDialog(self, definition):
        self._setNewTaskDialog()
        self._setNewTaskDialogCustomizer()
        self.newTaskDialogCustomizer.loadTaskDefinition(definition)
        self.newTaskDialog.show()

   #############################
    def _showNewTaskDialogClicked(self):
        self._setNewTaskDialog()
        self._setNewTaskDialogCustomizer()
        self.newTaskDialog.show()

    #############################
    def showNewTaskDialog(self, task_id):
        ts = self.logic.get_task(task_id)
        if ts is not None:
            self._showNewTaskDialog(ts.definition)
        else:
            logger.error("Can't get taski information for task {}".format(task_id))

    ############################
    def _setNewTaskDialog(self):
        self.newTaskDialog = NewTaskDialog(self.gui.window)

    ############################
    def _setNewTaskDialogCustomizer(self):
        self.newTaskDialogCustomizer = NewTaskDialogCustomizer(self.newTaskDialog, self.logic)


    ############################
    def _loadTaskButtonClicked(self):
        golemPath = os.environ.get('GOLEM')
        dir = ""
        if golemPath:
            saveDir = os.path.join(golemPath, "save")
            if os.path.isdir(saveDir):
                dir = saveDir

        file_name = QFileDialog.getOpenFileName(self.gui.window,
            "Choose task file", dir, "Golem Task (*.gt)")
        if os.path.exists(file_name):
            self._loadTask(file_name)

   ############################
    def _loadTask(self, filePath):
        f = open(filePath, 'r')
        try:
            definition = pickle.loads(f.read())
        except Exception, e:
            definition = None
            logger.error("Can't unpickle the file {}: {}".format(filePath, str(e)))
            QMessageBox().critical(None, "Error", "This is not a proper gt file")
        finally:
            f.close()

        if definition:
            self._showNewTaskDialog(definition)

    ############################
    def __showTaskContextMenu(self, p):

        if self.gui.ui.taskTableWidget.itemAt(p) is None:
            return
        row = self.gui.ui.taskTableWidget.itemAt(p).row()

        idItem = self.gui.ui.taskTableWidget.item(row, 0)
        task_id = "{}".format(idItem.text())
        gnrTaskState = self.logic.get_task(task_id)

        menu = QMenu()
        self.taskContextMenuCustomizer =  TaskContextMenuCustomizer(menu, self.logic, gnrTaskState)
        menu.popup(self.gui.ui.taskTableWidget.viewport().mapToGlobal(p))
        menu.exec_()

    ##########################
    def _contexMenuRequested(self, p):
        self.__showTaskContextMenu(p)

    #############################
    def _taskTableRowClicked(self, row, col):
        if row < self.gui.ui.taskTableWidget.rowCount():
            task_id = self.gui.ui.taskTableWidget.item(row, 0).text()
            task_id = "{}".format(task_id)
            t = self.logic.get_task(task_id)
            self.updateTaskAdditionalInfo(t)

    #############################
    def _taskTableRowDoubleClicked(self, m):
        row = m.row()
        task_id = "{}".format(self.gui.ui.taskTableWidget.item(row, 0).text())
        self.showDetailsDialog(task_id)

    #############################
    def showDetailsDialog(self, task_id):
        ts = self.logic.get_task(task_id)
        self.taskDetailsDialog = TaskDetailsDialog(self.gui.window)
        self.taskDetailsDialogCustomizer = TaskDetailsDialogCustomizer(self.taskDetailsDialog, self.logic, ts)
        self.taskDetailsDialog.show()

    #############################
    def showSubtaskDetailsDialog(self, subtask):
        subtaskDetailsDialog = SubtaskDetailsDialog(self.gui.window)
        subtaskDetailsDialogCustomizer = SubtaskDetailsDialogCustomizer(subtaskDetailsDialog, self.logic, subtask)
        subtaskDetailsDialog.show()

   #############################
    def showChangeTaskDialog(self, task_id):
        self.changeTaskDialog = ChangeTaskDialog(self.gui.window)
        self.changeTaskDialogCustomizer = ChangeTaskDialogCustomizer(self.changeTaskDialog, self.logic)
        ts = self.logic.get_task(task_id)
        self.changeTaskDialogCustomizer.loadTaskDefinition(ts.definition)
        self.changeTaskDialog.show()

    #############################
    def _showStatusClicked(self):
        self.statusWindow = StatusWindow(self.gui.window)

        self.statusWindowCustomizer = StatusWindowCustomizer(self.statusWindow, self.logic)
        self.statusWindowCustomizer.get_status()
        self.statusWindow.show()

    #############################
    def _showAboutClicked(self):
        aboutWindow = AboutWindow(self.gui.window)
        aboutWindowCustomizer = AboutWindowCustomizer(aboutWindow, self.logic)
        aboutWindow.show()

     #############################
    def _showConfigurationDialogClicked(self):
        self.configurationDialog = ConfigurationDialog(self.gui.window)
        self.configurationDialogCustomizer = ConfigurationDialogCustomizer(self.configurationDialog, self.logic)
        self.configurationDialogCustomizer.load_config()
        self.configurationDialog.show()

    #############################
    def _showEnvironments (self):
        self.environmentsDialog = EnvironmentsDialog(self.gui.window)

        self.environmentsDialogCustomizer = EnvironmentsDialogCustomizer(self.environmentsDialog, self.logic)
        self.environmentsDialog.show()
