import os
import tempfile
from copy import deepcopy

from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.upack.upackenvironment import UpackTaskEnvironment
from golem.core.common import get_golem_path
from golem.resource.dirmanager import symlink_or_copy, list_dir_recursive


class UpackTaskDefaults(TaskDefaults):
    """ Suggested default values for upack task"""

    def __init__(self):
        super(UpackTaskDefaults, self).__init__()
        self.options = UpackTaskOptions()
        self.out_file_basename = "out"
        self.shared_data_files = []
        self.default_subtasks = 1
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps", "upack", "resources", "code_dir")


class UpackTaskDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = UpackTaskOptions()
        self.task_type = 'UPACK'
        self.shared_data_files = []

        # subtask code
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps", "upack", "resources", "code_dir")
        self.code_files = []

        self.result_size = 256  # length of result hex number
        self.out_file_basename = "out"

        if defaults:
            self.set_defaults(defaults)

    def add_to_resources(self):
        super().add_to_resources()

        # TODO create temp in task directory
        # but for now TaskDefinition doesn't know root_path. Issue #2427
        # task_root_path = ""
        # self.tmp_dir = DirManager().get_task_temporary_dir(self.task_id, True)

        self.tmp_dir = tempfile.mkdtemp()
        self.shared_data_files = list(self.resources)
        self.code_files = list(list_dir_recursive(self.code_dir))

        symlink_or_copy(self.code_dir, os.path.join(self.tmp_dir, "code"))

        data_path = os.path.join(self.tmp_dir, "data")
        if os.path.exists(data_path):
            raise FileExistsError("Error adding to resources: "
                                "data path: {} exists."
                                .format(data_path))

        os.mkdir(data_path)
        for data_file in self.shared_data_files:
            symlink_or_copy(data_file,
                            os.path.join(data_path, os.path.basename(data_file)))

        self.resources = set(list_dir_recursive(self.tmp_dir))

    # TODO maybe move it to the CoreTask? Issue #2428
    def set_defaults(self, defaults: UpackTaskDefaults):
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.code_dir = defaults.code_dir
        self.total_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)


class UpackTaskOptions(Options):
    def __init__(self):
        super(UpackTaskOptions, self).__init__()
        self.environment = UpackTaskEnvironment()