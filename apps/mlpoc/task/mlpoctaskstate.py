import os
import tempfile
from copy import deepcopy

from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment
from golem.core.common import get_golem_path
from golem.resource.dirmanager import ls_R


class MLPOCTaskDefaults(TaskDefaults):
    """ Suggested default values for mlpoc task"""

    def __init__(self):
        super(MLPOCTaskDefaults, self).__init__()
        self.options = MLPOCTaskOptions()
        self.options.steps_per_epoch = 10
        self.options.number_of_epochs = 5
        self.shared_data_files = ["IRIS.data"]
        self.default_subtasks = 5
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps",
                                     "mlpoc",
                                     "resources",
                                     "code_pytorch")

        @property
        def full_task_timeout(self):
            return self.default_subtasks * self.subtask_timeout

        @property
        def subtask_timeout(self):
            return 1200


class MLPOCTaskDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = MLPOCTaskOptions()

        # subtask data
        self.shared_data_files = []

        # subtask code
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps",
                                     "mlpoc",
                                     "resources",
                                     "code_pytorch")
        self.code_files = []

        if defaults:
            self.set_defaults(defaults)

    # TODO abstract away
    def add_to_resources(self):
        super().add_to_resources()

        self.tmp_dir = tempfile.mkdtemp()

        self.shared_data_files = list(self.resources)
        self.code_files = ls_R(self.code_dir)

        # TODO remove symlinks when the dummytask will be merged
        # symlink_or_copy(self.code_dir, os.path.join(self.tmp_dir, "code"))
        os.symlink(self.code_dir, os.path.join(self.tmp_dir, "code"))
        common_data_path = os.path.dirname(list(self.shared_data_files)[0])
        # symlink_or_copy(common_data_path, os.path.join(self.tmp_dir, "data"))
        os.symlink(common_data_path, os.path.join(self.tmp_dir, "data"))
        self.resources = set(ls_R(self.tmp_dir))

    def set_defaults(self, defaults: MLPOCTaskDefaults):
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.code_dir = defaults.code_dir
        self.total_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)


class MLPOCTaskOptions(Options):
    def __init__(self):
        super(MLPOCTaskOptions, self).__init__()
        self.environment = MLPOCTorchEnvironment()
        self.steps_per_epoch = 0
        self.number_of_epochs = 0
        self.probability_of_save = 0 # TODO set that dynamically