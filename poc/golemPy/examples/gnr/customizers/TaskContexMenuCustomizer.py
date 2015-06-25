from PyQt4.QtGui import QAction

from golem.task.TaskState import TaskStatus

class TaskContextMenuCustomizer:
    ##########################
    def __init__(self, ui, logic, ts):
        self.ui         = ui
        self.logic      = logic
        self.gnrTaskState  = ts

        self.__buildContextMenu()

    ##########################
    def __buildContextMenu(self):

        enabledActions = self.__getEnabledActions(self.gnrTaskState.taskState.status)

        self.__buildAndConnectAction("Abort Task",      self.__abortTaskTriggered,         enabledActions)
        self.__buildAndConnectAction("Restart",         self.__restartTaskTriggered,       enabledActions)
        self.__buildAndConnectAction("Delete",          self.__deleteTaskTriggered,        enabledActions)
        self.__buildAndConnectAction("New Task",        self.__newTaskTriggered,           enabledActions)
        self.__buildAndConnectAction("Start Task",      self.__startTaskTriggered,         enabledActions)
        self.__buildAndConnectAction("Pause",           self.__pauseTaskTriggered,         enabledActions)
        self.__buildAndConnectAction("Resume",          self.__resumeTaskTriggered,        enabledActions)
        self.__buildAndConnectAction("Change Timeouts", self.__changeTaskTriggered,        enabledActions)
        self.__buildAndConnectAction("Show Details",    self.__showTaskDetailsTriggered,   enabledActions)
        self.__buildAndConnectAction("Show Result",     self.__showResultTriggered,        enabledActions)

    ##########################
    def __buildAndConnectAction(self, name, triggeredFunc, enabledActions):
        action = QAction(name, self.ui)

        action.setEnabled(enabledActions[ name ])

        action.triggered.connect(triggeredFunc)
        self.ui.addAction(action)
        return action        

    # SLOTS
    ###########################
    def __abortTaskTriggered(self):
        self.logic.abortTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __restartTaskTriggered(self):
        self.logic.restartTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __deleteTaskTriggered(self):
        self.logic.deleteTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __newTaskTriggered(self):
        self.logic.showNewTaskDialog(self.gnrTaskState.definition.taskId)

    ###########################
    def __startTaskTriggered(self):
        self.logic.startTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __pauseTaskTriggered(self):
        self.logic.pauseTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __resumeTaskTriggered(self):
        self.logic.resumeTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __showTaskDetailsTriggered(self):
        self.logic.showTaskDetails(self.gnrTaskState.definition.taskId)

    ###########################
    def __changeTaskTriggered(self):
        self.logic.changeTask(self.gnrTaskState.definition.taskId)

    ###########################
    def __showResultTriggered(self):
        self.logic.showTaskResult(self.gnrTaskState.definition.taskId)

    #######################
    ##########################
    def __getEnabledActions(self, taskStatus):

        enabled = {}

        enabled[ "New Task" ]       = True
        enabled[ "Show Details" ]   = True
        enabled[ "Delete" ]         = True

        if taskStatus == TaskStatus.notStarted:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = False         
            enabled[ "Start Task" ]     = True
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if taskStatus == TaskStatus.sending:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = False
            enabled[ "Start Task" ]     = True
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if taskStatus == TaskStatus.waiting:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = True
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if taskStatus == TaskStatus.starting:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = True
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if taskStatus == TaskStatus.computing:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = True
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False
            
        if taskStatus == TaskStatus.finished:
            enabled[ "Abort Task"]      = False
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = False
            enabled[ "Show Result" ]   = True

        if taskStatus == TaskStatus.aborted:
            enabled[ "Abort Task"]      = False
            enabled[ "Restart"]         = False
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = False
            enabled[ "Show Result" ]   = False

        if taskStatus == TaskStatus.failure:
            enabled[ "Abort Task"]      = False
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = False
            enabled[ "Show Result" ]   = False

        if taskStatus == TaskStatus.paused:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = True
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        assert len(enabled) == 10

        return enabled