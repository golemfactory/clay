from apps.core.task.coretask import CoreTaskTypeInfo
from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.shell.shellenvironment import ShellTaskEnvironment
from apps.shell.task.shelltaskstate import ShellTaskDefaults
from apps.shell.task.shelltaskstate import ShellTaskDefinition
from apps.shell.task.shelltask import ShellTaskBuilder, ShellTask

class FireworksShellTaskEnvironment(ShellTaskEnvironment):
    DOCKER_IMAGE = "golemfactory/fireworks"
    DOCKER_TAG = "1.0"
    ENV_ID = "Fireworks"
    SHORT_DESCRIPTION = "Fireworks shell task"

class FireworksShellTaskOptions(Options):
    def __init__(self):
        super(FireworksShellTaskOptions, self).__init__()
        self.environment = FireworksShellTaskEnvironment()

class FireworksShellTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Fireworks",
            ShellTaskDefinition,
            ShellTaskDefaults(),
            FireworksShellTaskOptions,
            FireworksShellTaskBuilder
        )

class FireworksShellTask(ShellTask):
    ENVIRONMENT_CLASS = FireworksShellTaskEnvironment

class FireworksShellTaskBuilder(ShellTaskBuilder):
    TASK_CLASS = FireworksShellTask
