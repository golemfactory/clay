from PyQt4.QtGui import QAction

from golem.task.TaskState import SubtaskStatus

class SubtaskContextMenuCustomizer:
    ##########################
    def __init__(self, ui, logic, subtask_id, subtaskStatus):
        self.ui             = ui
        self.logic          = logic
        self.subtask_id      = subtask_id
        self.subtaskStatus  = subtaskStatus

        self.__buildContextMenu()

    ##########################
    def __buildContextMenu(self):
        enabledActions = self.__getEnabledActions(self.subtaskStatus)
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
    def __getEnabledActions(self, subtaskStatus):
        enabled = {}

        if subtaskStatus == SubtaskStatus.starting:
            enabled [ "Restart" ] = True

        if subtaskStatus == SubtaskStatus.waiting:
            enabled[ "Restart" ] = False

        if subtaskStatus == SubtaskStatus.failure:
            enabled [ "Restart" ] = False

        if subtaskStatus == SubtaskStatus.finished:
            enabled [ "Restart" ] = True

        if subtaskStatus == SubtaskStatus.resent:
            enabled[ "Restart" ] = False

        return enabled

