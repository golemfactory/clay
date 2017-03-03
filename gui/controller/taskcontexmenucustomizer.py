from PyQt5.QtWidgets import QAction

from golem.task.taskstate import TaskStatus


class TaskContextMenuCustomizer:
    def __init__(self, ui, logic, ts):
        self.ui = ui
        self.logic = logic
        self.task_desc = ts

        self.__build_context_menu()

    def __build_context_menu(self):

        enabled_actions = self.__get_enabled_actions(self.task_desc.task_state.status)

        self.__build_and_connect_action("Start Task", self.__start_task_triggered, enabled_actions)
        self.__build_and_connect_action("Pause", self.__pause_task_triggered, enabled_actions)
        self.__build_and_connect_action("Resume", self.__resume_task_triggered, enabled_actions)
        self.__build_and_connect_action("Clone Task", self.__clone_task_triggered, enabled_actions)
        self.__build_and_connect_action("Abort Task", self.__abort_task_triggered, enabled_actions)
        self.__build_and_connect_action("Restart", self.__restart_task_triggered, enabled_actions)
        self.__build_and_connect_action("Delete", self.__delete_task_triggered, enabled_actions)
        self.__build_and_connect_action("Change Timeouts", self.__change_task_triggered, enabled_actions)
        self.__build_and_connect_action("Show Details", self.__show_task_details_triggered, enabled_actions)
        self.__build_and_connect_action("Show Result", self.__show_result_triggered, enabled_actions)

    def __build_and_connect_action(self, name, triggered_func, enabled_actions):
        action = QAction(name, self.ui)

        action.setEnabled(enabled_actions[name])

        action.triggered.connect(triggered_func)
        self.ui.addAction(action)
        return action

        # SLOTS

    #
    def __abort_task_triggered(self):
        self.logic.abort_task(self.task_desc.definition.task_id)

    def __restart_task_triggered(self):
        self.logic.restart_task(self.task_desc.definition.task_id)

    def __delete_task_triggered(self):
        self.logic.delete_task(self.task_desc.definition.task_id)

    def __clone_task_triggered(self):
        self.logic.clone_task(self.task_desc.definition.task_id)

    def __start_task_triggered(self):
        self.logic.start_task(self.task_desc.definition.task_id)

    def __pause_task_triggered(self):
        self.logic.pause_task(self.task_desc.definition.task_id)

    def __resume_task_triggered(self):
        self.logic.resume_task(self.task_desc.definition.task_id)

    def __show_task_details_triggered(self):
        self.logic.show_task_details(self.task_desc.definition.task_id)

    def __change_task_triggered(self):
        self.logic.change_task(self.task_desc.definition.task_id)

    def __show_result_triggered(self):
        self.logic.show_task_result(self.task_desc.definition.task_id)

    @staticmethod
    def __get_enabled_actions(task_status):

        enabled = {}

        enabled["Clone Task"] = True
        enabled["Show Details"] = True
        enabled["Delete"] = True

        if task_status == TaskStatus.notStarted:
            enabled["Abort Task"] = True
            enabled["Restart"] = False
            enabled["Start Task"] = True
            enabled["Pause"] = False
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.sending:
            enabled["Abort Task"] = True
            enabled["Restart"] = False
            enabled["Start Task"] = True
            enabled["Pause"] = False
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.waiting:
            enabled["Abort Task"] = True
            enabled["Restart"] = True
            enabled["Start Task"] = False
            enabled["Pause"] = True
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.starting:
            enabled["Abort Task"] = True
            enabled["Restart"] = True
            enabled["Start Task"] = False
            enabled["Pause"] = True
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.computing:
            enabled["Abort Task"] = True
            enabled["Restart"] = True
            enabled["Start Task"] = False
            enabled["Pause"] = True
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.finished:
            enabled["Abort Task"] = False
            enabled["Restart"] = True
            enabled["Start Task"] = False
            enabled["Pause"] = False
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = True

        if task_status == TaskStatus.aborted:
            enabled["Abort Task"] = False
            enabled["Restart"] = False
            enabled["Start Task"] = False
            enabled["Pause"] = False
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.timeout:
            enabled["Abort Task"] = False
            enabled["Restart"] = True
            enabled["Start Task"] = False
            enabled["Pause"] = False
            enabled["Resume"] = False
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        if task_status == TaskStatus.paused:
            enabled["Abort Task"] = True
            enabled["Restart"] = True
            enabled["Start Task"] = False
            enabled["Pause"] = False
            enabled["Resume"] = True
            enabled["Change Timeouts"] = False
            enabled["Show Result"] = False

        return enabled
