from apps.core.task.coretask import CoreTaskTypeInfo
from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.shell.shellenvironment import ShellTaskEnvironment
from apps.shell.task.shelltaskstate import ShellTaskDefaults
from apps.shell.task.shelltaskstate import ShellTaskDefinition
from apps.shell.task.shelltask import ShellTaskBuilder, ShellTask

class RaspaShellTaskEnvironment(ShellTaskEnvironment):
    DOCKER_IMAGE = "golemfactory/raspa"
    DOCKER_TAG = "1.1"
    ENV_ID = "Raspa"
    SHORT_DESCRIPTION = "Raspa shell task"

class RaspaShellTaskOptions(Options):
    def __init__(self):
        super(RaspaShellTaskOptions, self).__init__()
        self.environment = RaspaShellTaskEnvironment()

class RaspaShellTaskTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__(
            "Raspa",
            ShellTaskDefinition,
            ShellTaskDefaults(),
            RaspaShellTaskOptions,
            RaspaShellTaskBuilder
        )

class RaspaShellTask(ShellTask):
    ENVIRONMENT_CLASS = RaspaShellTaskEnvironment

class RaspaShellTaskBuilder(ShellTaskBuilder):
    TASK_CLASS = RaspaShellTask
