import os
import tempfile
from copy import deepcopy

from apps.core.task.coretaskstate import (TaskDefinition,
                                          TaskDefaults, Options)
from apps.dummy2.dummy2environment import Dummy2TaskEnvironment
from golem.core.common import get_golem_path
from golem.resource.dirmanager import symlink_or_copy, list_dir_recursive


class Dummy2TaskDefaults(TaskDefaults):
    """ Suggested default values for dummy2 task"""

    def __init__(self):
        super(Dummy2TaskDefaults, self).__init__()
        self.options = Dummy2TaskOptions()
        self.options.difficulty = 0xffff0000  # magic number
        self.options.output_file = "result.out"
        self.result_size = None

        self.shared_data_files = ["in.data"]
        self.out_file_basename = "out"
        self.subtask_data = "0 1"
        self.default_subtasks = 5
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps", "dummy2", "resources", "code_dir")


# pylint: disable=too-many-instance-attributes
class Dummy2TaskDefinition(TaskDefinition):
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = Dummy2TaskOptions()
        self.task_type = 'DUMMY2'

        # subtask data
        self.shared_data_files = []

        # subtask code
        self.code_dir = os.path.join(get_golem_path(),
                                     "apps", "dummy2", "resources", "code_dir")
        self.code_files = []

        self.result_size = 3  # length of result hex number
        self.out_file_basename = "out"

        if defaults:
            self.set_defaults(defaults)

    def add_to_resources(self):
        super().add_to_resources()

        # TODO create temp in task directory
        # but for now TaskDefinition doesn't know root_path. Issue #2427
        # task_root_path = ""
        # self.tmp_dir = DirManager().get_task_temporary_dir(self.task_id, True)

        # pylint: disable=attribute-defined-outside-init
        self.tmp_dir = tempfile.mkdtemp()

        self.shared_data_files = list(self.resources)
        self.code_files = list(list_dir_recursive(self.code_dir))

        symlink_or_copy(self.code_dir, os.path.join(self.tmp_dir, "code"))

        # makes sense when len(..) > 1
        # common_data_path = os.path.commonpath(self.shared_data_files)
        # but we only have 1 file here
        data_path = os.path.join(self.tmp_dir, "data")
        data_file = list(self.shared_data_files)[0]
        if os.path.exists(data_path):
            raise FileExistsError("Error adding to resources: "
                                  "data path: {} exists."
                                  .format(data_path))

        os.mkdir(data_path)
        symlink_or_copy(data_file,
                        os.path.join(data_path, os.path.basename(data_file)))

        self.resources = set(list_dir_recursive(self.tmp_dir))

    # TODO maybe move it to the CoreTask? Issue #2428
    def set_defaults(self, defaults: Dummy2TaskDefaults):
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.out_file_basename = defaults.out_file_basename
        self.code_dir = defaults.code_dir
        self.result_size = defaults.result_size
        self.subtask_data = defaults.subtask_data
        self.total_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-few-public-methods
class Dummy2TaskOptions(Options):
    def __init__(self):
        super(Dummy2TaskOptions, self).__init__()
        self.environment = Dummy2TaskEnvironment()
        self.subtask_data_size = 128  # # length of subtask-specific hex number

        # The difficulty is a 4 byte int; 0xffffffff is the greatest
        # and 0x00000000 is the least difficulty.
        # For example difficulty 0xffff0000 requires
        # 0xffffffff /(0xffffffff - 0xffff0000) = 65537
        # hash computations on average.
        self.difficulty = 0xffff0000
        self.output_file = ""
