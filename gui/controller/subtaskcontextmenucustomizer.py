from PyQt5.QtWidgets import QAction
from golem.task.taskstate import SubtaskStatus


class SubtaskContextMenuCustomizer:
    def __init__(self, ui, logic, subtask_id, subtask_status):
        self.ui = ui
        self.logic = logic
        self.subtask_id = subtask_id
        self.subtask_status = subtask_status

        self.__build_context_menu()

    def __build_context_menu(self):
        enabled_actions = self.__get_enabled_actions(self.subtask_status)
        self.__build_and_connect_action("Restart", self.__restart_subtask, enabled_actions)

    def __build_and_connect_action(self, name, triggered_func, enabled_actions):
        action = QAction(name, self.ui)

        action.setEnabled(enabled_actions[name])

        action.triggered.connect(triggered_func)
        self.ui.addAction(action)
        return action

    def __restart_subtask(self):
        self.logic.restart_subtask(self.subtask_id)

    def __get_enabled_actions(self, subtask_status):
        enabled = {}

        if subtask_status == SubtaskStatus.starting:
            enabled["Restart"] = True

        if subtask_status == SubtaskStatus.downloading:
            enabled["Restart"] = False

        if subtask_status == SubtaskStatus.failure:
            enabled["Restart"] = False

        if subtask_status == SubtaskStatus.finished:
            enabled["Restart"] = True

        if subtask_status == SubtaskStatus.resent:
            enabled["Restart"] = False

        if subtask_status == SubtaskStatus.restarted:
            enabled["Restart"] = False

        return enabled
