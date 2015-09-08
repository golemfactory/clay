from PyQt4.QtGui import QAction

from golem.task.TaskState import SubtaskStatus

class SubtaskContextMenuCustomizer:
    ##########################
    def __init__(self, ui, logic, subtask_id, subtask_status):
        self.ui             = ui
        self.logic          = logic
        self.subtask_id      = subtask_id
        self.subtask_status = subtask_status

        self.__buildContextMenu()

    ##########################
    def __buildContextMenu(self):
        enabledActions = self.__getEnabledActions(self.subtask_status)
        self.__buildAndConnectAction("Restart", self.__restartSubtask, enabledActions)

    ##########################
    def __buildAndConnectAction(self, name, triggeredFunc, enabledActions):
        action = QAction(name, self.ui)

        action.setEnabled(enabledActions[ name ])

        action.triggered.connect(triggeredFunc)
        self.ui.addAction(action)
        return action

    ##########################
    def __restartSubtask(self):
        self.logic.restartSubtask(self.subtask_id)

    ##########################
    def __getEnabledActions(self, subtask_status):
        enabled = {}

        if subtask_status== SubtaskStatus.starting:
            enabled [ "Restart" ] = True

        if subtask_status== SubtaskStatus.waiting:
            enabled[ "Restart" ] = False

        if subtask_status== SubtaskStatus.failure:
            enabled [ "Restart" ] = False

        if subtask_status== SubtaskStatus.finished:
            enabled [ "Restart" ] = True

        if subtask_status== SubtaskStatus.resent:
            enabled[ "Restart" ] = False

        return enabled

