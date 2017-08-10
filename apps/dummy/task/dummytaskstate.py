import tempfile
from copy import deepcopy
import os

from apps.core.task.coretaskstate import (TaskDefinition,
                                          CoreTaskDefaults,
                                          Options)
from apps.dummy.dummyenvironment import DummyTaskEnvironment
from golem.core.common import get_golem_path


class DummyTaskDefaults(CoreTaskDefaults):
    """ Suggested default values for dummy task"""
    def __init__(self):
        super(DummyTaskDefaults, self).__init__()
        self.options = DummyTaskOptions()
        self.options.subtask_data_size = 2048
        self.options.result_size = 256
        self.options.difficulty = 10 # magic number

        self.shared_data_files = ["in.data"]
        self.out_file_basename = "out"
        self.default_subtasks = 5
        self.code_dir = "code_dir"
        self.result_size = 256 # size of subtask result in bytes

        @property
        def full_task_timeout(self):
            return self.default_subtasks * self.subtask_timeout

        @property
        def subtask_timeout(self):
            return 1200


class DummyTaskDefinition(TaskDefinition):

    #TODO put defaults switch in base class, create CoreTaskDefinition
    def __init__(self, defaults=None):
        TaskDefinition.__init__(self)

        self.options = DummyTaskOptions()
        # subtask data
        self.shared_data_files = []

        # subtask code_dir
        self.code_dir =  os.path.join(get_golem_path(), "apps", "dummy", "resources", "code_dir")
        self.code_files = []
        self.result_size = 256 # size of subtask result in bytes
        self.out_file_basename = "out"

        if defaults:
            self.set_defaults(defaults)

    @staticmethod
    def ls_R(dir):
        files = []
        for dirpath, dirnames, filenames in os.walk(dir, followlinks=True):
            for name in filenames:
                files.append(os.path.join(dirpath, name))
        return files

    def add_to_resources(self):
        super().add_to_resources()
        self.shared_data_files = list(self.resources)

        self.code_files = self.ls_R(self.code_dir)

        self.tmp_dir = tempfile.mkdtemp()
        os.symlink(self.code_dir, os.path.join(self.tmp_dir, "code"))

        # common_data_path = os.path.commonpath(self.shared_data_files) # makes sense when len() > 1
        common_data_path = os.path.dirname(list(self.shared_data_files)[0])
        os.symlink(common_data_path, os.path.join(self.tmp_dir, "data"))

        self.resources = set(self.ls_R(self.tmp_dir))

    #TODO move it somewhere to the base class (or not?)
    def set_defaults(self, defaults):
        self.shared_data_files = deepcopy(defaults.shared_data_files)
        self.out_file_basename = defaults.out_file_basename
        self.default_subtasks = defaults.default_subtasks
        self.options = deepcopy(defaults.options)
        self.code_dir = defaults.code_dir
        self.result_size = defaults.result_size # size of subtask result in bytes

class DummyTaskOptions(Options):
    def __init__(self):
        super(DummyTaskOptions, self).__init__()
        self.environment = DummyTaskEnvironment() #TODO it shoudn't be there
        self.subtask_data_size = 128 # size of subtask-specific data in bytes

        # The difficulty is a 4 byte int; 0x00000001 is the greatest and 0xffffffff
        # the least difficulty. For example difficulty = 0x003fffff requires
        # 0xffffffff / 0x003fffff = 1024 hash computations on average.
        self.difficulty = 10 # 32 - log2(0x003fffff)
