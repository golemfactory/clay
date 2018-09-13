from copy import deepcopy

from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.runf.runfenvironment import RunFEnvironment


class RunFDefaults(TaskDefaults):
    def __init__(self):
        super().__init__()
        self.options = RunFOptions()
        self.min_subtasks = 1
        self.max_subtasks = 1000
        self.default_subtasks = 10


class RunFDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        super().__init__()
        self.options = RunFOptions()
        self.task_type = "RUNF"

        if defaults:
            self.set_defaults(defaults)

    # TODO maybe move it to the CoreTask? Issue #2428
    def set_defaults(self, defaults: RunFDefaults):
        self.options = deepcopy(defaults.options)


class RunFOptions(Options):
    def __init__(self):
        super().__init__()
        self.environment = RunFEnvironment()
        self.queue_host = "localhost"
        self.queue_port = 6397