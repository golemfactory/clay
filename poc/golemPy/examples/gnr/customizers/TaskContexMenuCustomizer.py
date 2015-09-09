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

        enabledActions = self.__getEnabledActions(self.gnrTaskState.task_state.status)

        self.__buildAndConnectAction("Abort Task",      self.__abort_taskTriggered,         enabledActions)
        self.__buildAndConnectAction("Restart",         self.__restart_taskTriggered,       enabledActions)
        self.__buildAndConnectAction("Delete",          self.__delete_taskTriggered,        enabledActions)
        self.__buildAndConnectAction("New Task",        self.__newTaskTriggered,           enabledActions)
        self.__buildAndConnectAction("Start Task",      self.__start_taskTriggered,         enabledActions)
        self.__buildAndConnectAction("Pause",           self.__pause_taskTriggered,         enabledActions)
        self.__buildAndConnectAction("Resume",          self.__resume_taskTriggered,        enabledActions)
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
    def __abort_taskTriggered(self):
        self.logic.abort_task(self.gnrTaskState.definition.task_id)

    ###########################
    def __restart_taskTriggered(self):
        self.logic.restart_task(self.gnrTaskState.definition.task_id)

    ###########################
    def __delete_taskTriggered(self):
        self.logic.delete_task(self.gnrTaskState.definition.task_id)

    ###########################
    def __newTaskTriggered(self):
        self.logic.showNewTaskDialog(self.gnrTaskState.definition.task_id)

    ###########################
    def __start_taskTriggered(self):
        self.logic.start_task(self.gnrTaskState.definition.task_id)

    ###########################
    def __pause_taskTriggered(self):
        self.logic.pause_task(self.gnrTaskState.definition.task_id)

    ###########################
    def __resume_taskTriggered(self):
        self.logic.resume_task(self.gnrTaskState.definition.task_id)

    ###########################
    def __showTaskDetailsTriggered(self):
        self.logic.showTaskDetails(self.gnrTaskState.definition.task_id)

    ###########################
    def __changeTaskTriggered(self):
        self.logic.changeTask(self.gnrTaskState.definition.task_id)

    ###########################
    def __showResultTriggered(self):
        self.logic.showTaskResult(self.gnrTaskState.definition.task_id)

    #######################
    ##########################
    def __getEnabledActions(self, task_status):

        enabled = {}

        enabled[ "New Task" ]       = True
        enabled[ "Show Details" ]   = True
        enabled[ "Delete" ]         = True

        if task_status == TaskStatus.notStarted:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = False         
            enabled[ "Start Task" ]     = True
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if task_status == TaskStatus.sending:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = False
            enabled[ "Start Task" ]     = True
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if task_status == TaskStatus.waiting:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = True
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if task_status == TaskStatus.starting:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = True
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        if task_status == TaskStatus.computing:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = True
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False
            
        if task_status == TaskStatus.finished:
            enabled[ "Abort Task"]      = False
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = False
            enabled[ "Show Result" ]   = True

        if task_status == TaskStatus.aborted:
            enabled[ "Abort Task"]      = False
            enabled[ "Restart"]         = False
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = False
            enabled[ "Show Result" ]   = False

        if task_status == TaskStatus.failure:
            enabled[ "Abort Task"]      = False
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = False
            enabled["Change Timeouts"]  = False
            enabled[ "Show Result" ]   = False

        if task_status == TaskStatus.paused:
            enabled[ "Abort Task"]      = True
            enabled[ "Restart"]         = True
            enabled[ "Start Task" ]     = False
            enabled[ "Pause" ]          = False
            enabled[ "Resume"]          = True
            enabled["Change Timeouts"]  = True
            enabled[ "Show Result" ]   = False

        assert len(enabled) == 10

        return enabled