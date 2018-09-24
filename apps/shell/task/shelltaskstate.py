import os
import tempfile
from copy import deepcopy

from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.shell.shellenvironment import ShellTaskEnvironment
from golem.core.common import get_golem_path
from golem.resource.dirmanager import symlink_or_copy, list_dir_recursive


class ShellTaskDefaults(TaskDefaults):
    """ Suggested default values for shell task"""

    def __init__(self):
        super(ShellTaskDefaults, self).__init__()
        self.shared_data_files = []
        self.default_subtasks = 1

class ShellTaskDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.task_type = 'SHELL'
        self.shared_data_files = []

        if defaults:
            self.set_defaults(defaults)

    def add_to_resources(self):
        super().add_to_resources()

        # TODO create temp in task directory
        # but for now TaskDefinition doesn't know root_path. Issue #2427
        # task_root_path = ""
        # self.tmp_dir = DirManager().get_task_temporary_dir(self.task_id, True)

    # TODO maybe move it to the CoreTask? Issue #2428
    def set_defaults(self, defaults: ShellTaskDefaults):
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.total_subtasks = defaults.default_subtasks

class ShellTaskOptions(Options):
    def __init__(self):
        super(ShellTaskOptions, self).__init__()
        self.environment = ShellTaskEnvironment()