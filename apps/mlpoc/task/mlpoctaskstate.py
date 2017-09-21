import os
import tempfile
from copy import deepcopy

from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment
from golem.core.common import get_golem_path
from golem.resource.dirmanager import ls_R, symlink_or_copy


class MLPOCTaskDefaults(TaskDefaults):
    """ Suggested default values for mlpoc task"""

    def __init__(self):
        super(MLPOCTaskDefaults, self).__init__()
        self.options = MLPOCTaskOptions()
        self.options.steps_per_epoch = 10
        self.options.number_of_epochs = 5
        self.input_data_file = "IRIS.csv"
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
        self.input_data_file = ""

        # subtask code
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps",
                                     "mlpoc",
                                     "resources",
                                     "code_pytorch")
        self.code_files = []

        if defaults:
            self.set_defaults(defaults)

    def add_to_resources(self):
        super().add_to_resources()

        self.tmp_dir = tempfile.mkdtemp()
        self.code_place = os.path.join(self.tmp_dir, "code")
        self.data_place = os.path.join(self.tmp_dir, "data")

        # code
        self.code_files = ls_R(self.code_dir)
        symlink_or_copy(self.code_dir, self.code_place)

        # data
        self.input_data_file = list(self.resources)[0]
        os.mkdir(self.data_place)
        symlink_or_copy(self.input_data_file,
                        os.path.join(self.data_place,
                                     os.path.basename(self.input_data_file)))
        
        self.resources = set(ls_R(self.tmp_dir))

    def set_defaults(self, defaults: MLPOCTaskDefaults):
        self.input_data_file = defaults.input_data_file
        self.code_dir = defaults.code_dir
        self.total_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)


class MLPOCTaskOptions(Options):
    def __init__(self):
        super(MLPOCTaskOptions, self).__init__()
        self.environment = MLPOCTorchEnvironment()
        self.steps_per_epoch = 0
        self.number_of_epochs = 0
        self.probability_of_save = 0
